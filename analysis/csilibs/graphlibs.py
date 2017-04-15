#!/s/python-2.7.1/bin/python

from sys import stderr
import networkx
from networkx.readwrite.graphml import read_graphml
from networkx.classes.multidigraph import MultiDiGraph
from re import search
from collections import deque

from datetime import datetime
import pickle

from clock import CSIClock

# prints final path and gdb structures to stderr
FILTER_DEBUG = False;

"""
All lib functions for the graphml stuff.
"""

"""
read_graph(): Read in the graph from the filename specified.  If the graph isn't
a pickle, the graph is "fixed up," a process that takes a really long time.
@param f the path to the file to read
@param cfgOnly regardless of graphml content, keep only CFG data, and treat the
               graph as a CFG (otherwise, the decision is based on the graph
               property "nature").
               NOTE: If a CFG, we delete any PDG-only data from the graph.
                     If a PDG, we do various "fixes" to introduce ambiguity and
                     match codesurfer output.
@return a MultiDiGraph representation of the graph
"""
def read_graph(f, cfgOnly=False):
  try:
    if(f[-6:] == "pickle"):
      return pickle.load(open(f, "rb"));
    else:
      G = MultiDiGraph(read_graphml(f));
      if(cfgOnly or G.graph.get("nature", None) == "CFG"):
        print("(removing PDG data from CFG)...");
        G = _removePDGStructures(G);
      else:
        print("(fixing graph)...");
        G = fix_graph(G);
      #end if
      return G;
    #end if
  except Exception as e:
    print >> stderr, ("ERROR: could not read graphML file " + f + "!");
    print >> stderr, (str(e));
    exit(1);
#end: read_graph

"""
_removePDGStructures(): An internal function to remove PDG-only stuff to make
a combined graph into just a CFG.
@param G the graph
@return the fixed graph
"""
def _removePDGStructures(G):
  for (n, attr) in G.nodes(data=True):
    if(not is_cfg_node(G, n)):
      G.remove_node(n);
    #end if
  #end for

  for (src, target, key, attr) in G.edges(keys=True, data=True):
    if(attr.get("type", "") == "data" or \
       (attr.get("type", "") == "control" and attr.get("scope", "") != "interprocedural")):
      G.remove_edge(src, target, key=key);
    #end if
  #end for

  return(G);
#end: _removePDGStructures

"""
_isTrueCallsite(): Check if the specified node is a full-on call site (i.e., it
has the right type and has an outgoing call edge).
@param G the graph
@param n the node in question
@return True if "n" is a call-site with an outgoing call edge, False otherwise
"""
def _isTrueCallsite(G, n):
  if(G.node.get(n, {}).get("kind", "") != "call-site"):
    return(False);

  for (call, target, data) in G.out_edges_iter([n], data=True):
    if(data.get("type", "") == "control" and \
       data.get("scope", "") == "interprocedural"):
      return(True);
    #end if
  #end for

  return(False);
#end: _isTrueCallsite

"""
collapse_BB_nodes(): Collapse basic blocks into the smallest number of nodes
possible, given that any nodes in "exclude" may not be combined with others.
@param G the graph
@param exclude nodes that may not be combined with others in their basic block
@param combineCalls indicate whether or not call-site nodes may be combined with
                    others
@return the collapsed graph
"""
def collapse_BB_nodes(G, exclude=[], combineCalls=False):
  # verify that we don't start with any edges to nowhere
  for (src, target) in G.edges_iter(data=False):
    if(src not in G or target not in G):
      print >> stderr, ("ERROR: edge to/from nowhere found in the graph: ('" + \
                        str(src) + "', '" + str(target) + "'");
      exit(1);
    #end if
  #end for

  # a sadly inefficient loop.  A reverse-topological ordering of nodes in basic
  # blocks would be more efficient, but this seems fast enough for now.
  changed = True;
  while(changed):
    changed = False;
    for (src, target, attr) in G.edges(data=True):
      if(src not in G or target not in G):
        # we need this check because we can't guarantee edge iteration order, so
        # we may combine a node before processing its outgoing targets
        continue;
      #end if

      srcAttr = G.node[src];
      targetAttr = G.node[target];
      srcKind = srcAttr.get("kind", "");
      targetKind = targetAttr.get("kind", "");

      if(attr.get("type", "flow") != "flow" or \
         targetKind == "entry" or targetKind == "exit"):
        continue;
      if(src in exclude or target in exclude):
        # both for now.  I believe src is necessary because of crashes and
        # target is necessary because of True observations, but I need to think
        # more about this
        continue;
      #end if

      if(not combineCalls and (_isTrueCallsite(G, src) or \
                               _isTrueCallsite(G, target))):
        continue;
      #end if

      # make sure they are in the same basic block
      outEdges = [1 for (outS, outT, outData) \
                    in G.out_edges_iter([src], data=True) \
                    if outData.get("type", "flow") == "flow"];
      inEdges = [1 for (inS, inT, inData) \
                   in G.in_edges_iter([target], data=True) \
                   if inData.get("type", "flow") == "flow"];
      if(len(outEdges) > 1 or len(inEdges) > 1):
        continue;

      # move all edges target->N to source->N
      for (tSrc, tTarget, tAttr) in G.out_edges_iter([target], data=True):
        G.add_edge(src, tTarget, attr_dict=tAttr);
      #end for

      # add target's line numbers to source's line numbers
      sourceLines = lines_from_node(G, src);
      targetLines = lines_from_node(G, target);
      if(targetLines != None and len(targetLines) > 0):
        newLines = ([] if sourceLines == None else sourceLines) + targetLines;
        srcAttr["lines"] = "(" + " ".join(map(str, newLines)) + ")";
      #end if

      # add target to the set of nodes collapsed into src
      srcPriorNodes = collapsed_nodes_from_node(G, src);
      targetPriorNodes = collapsed_nodes_from_node(G, target);
      newNodes = srcPriorNodes + targetPriorNodes + [target];
      srcAttr["collapsed-nodes"] = "(" + " ".join(newNodes) + ")";

      G.remove_node(target);
      changed = True;
    #end for
  #end while

  # verify that we didn't create any new edges to nowhere
  for (src, target) in G.edges_iter(data=False):
    if(src not in G or target not in G):
      print >> stderr, ("ERROR: created an edge to nowhere in the graph: ('" + \
                        str(src) + "', '" + str(target) + "'");
      exit(1);
    #end if
  #end for

  return(G);
#end: collapse_BB_nodes

"""
collapsed_nodes_from_node(): Get all nodes collapsed into the specified node (via
a call to "collapse_BB_nodes()").
@param G the graph
@param n the node id (from the graphml)
@return the set of collapsed nodes.  If the node exists in the graph, return
        the collapsed nodes.  (If there are none, return an empty list.)  If the
        node is not in the graph, print an error and crash.
"""
def collapsed_nodes_from_node(G, n):
  if(n not in G):
    print >> stderr, ("ERROR: invalid node searching for collapsed nodes: " + \
                      str(n));
    exit(1);
  #end if

  collapsedAttr = G.node[n].get("collapsed-nodes", "()");
  if(collapsedAttr[0] != '(' or collapsedAttr[-1] != ')'):
    print >> stderr, ("ERROR: invalid collapsed nodes data for " + str(n) + \
                      ": " + str(collapsedAttr));
    exit(1);
  #end if

  return(collapsedAttr[1:-1].strip().split());
#end: collapsed_nodes_from_node

"""
lines_from_node(): Get lines information for the specified node (as a list).
@param G the graph
@param n the node id (from the graphml)
@return the list of lines if n is a CFG node with line data, otherwise None
"""
def lines_from_node(G, n):
  linesAttr = G.node[n].get("lines", "");
  if(not linesAttr or linesAttr[0] != '(' or linesAttr[-1] != ')'):
    return(None);
  return(map(int, linesAttr[1:-1].strip().split()));
#end: lines_from_node

"""
is_cfg_node(): Determine if n is a CFG node in G.
@param G the graph
@param n the node id (from the graphml)
@return True if n is in G, and has incoming or outgoing CFG edges
        False if n is either (a) not in G, or (b) a PDG-only node
"""
def is_cfg_node(G, n):
  return(next((True for (pred, cur, data) in G.in_edges_iter([n], data=True) \
                    if data.get("type", "flow") == "flow"), False) or \
         next((True for (cur, succ, data) in G.out_edges_iter([n], data=True) \
                    if data.get("type", "flow") == "flow"), False));
#end: is_cfg_node

"""
function_id(): Extract the function id from the node name provided.
@param n the node id (from the graphml)
@return the integer function id encoded in the node
"""
def function_id(node):
  try:
    return(int(node.split(':')[1]));
  except:
    print >> stderr, ("ERROR: bad graphml entry node formatting for " +
                      "node \'" + str(node) + "\'");
    exit(1);
#end: function_id

"""
exit_from_node(): Get the exit node for the function containing the provided
node.
@param G the graph
@param n the node whose function we want the exit for
@return the exit node in question
"""
def exit_from_node(G, node):
  if(node not in G):
    print >> stderr, ("ERROR: invalid data to exit_from_node: " + n);
    exit(1);
  #end if
  
  exitNode = None;
  funcId = function_id(node);
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "") == "exit" and
       function_id(n) == funcId):
      if(exitNode):
        print >> stderr, ("ERROR: multiple exit nodes match node " + node);
        exit(1);
      exitNode = n;
    #end if
  #end for
  
  if(not exitNode):
    print >> stderr, ("ERROR: exit node missing for node " + node);
    exit(1);
  #end if
  
  return(exitNode);
#end: exit_from_node

"""
nodes_from_label(): Find all nodes in G matching the specified csi-label.
Optionally, only match nodes from the specified function.
@param G the graph
@param label the expected csi-label data for the node(s)
@param funcId the integer id of the function.  Not matched if "None".
@return the set of nodes in G matching label
"""
def nodes_from_label(G, label, funcId=None):
  if(label == None):
    print >> stderr, ("ERROR: cannot search graph for None csi-label");
    exit(1);
  #end if

  result = set([]);
  for (n, attr) in G.nodes_iter(data=True):
    if((funcId == None or function_id(n) == funcId) and \
       attr.get("csi-label", None) == label):
      result.add(n);
    #end if
  #end for
  return(result);
#end: nodes_from_label

"""
entries_from_call(): Get the entry node(s) associated with a particular call
node.  Note that the returned result *may* be in an indirect function: the
caller is responsible for specially handling that case (if necessary).
@param G the graph
@param call the callsite node
@return a set of entry targets for the call
NOTE: the result is always only a singleton for the regular C-based analysis,
      but may have more, e.g., when Java programs start going through
"""
def entries_from_call(G, call):
  if(G.node[call].get("kind", "") != "call-site"):
    print >> stderr, ("ERROR: non-callsite passed to defYes_explore!" + call);
    exit(1);
  #end if
  
  entries = set([]);
  for (call, target, attr) in G.out_edges_iter([call], data=True):
    if(attr.get("type", "") == "control" and \
       attr.get("scope", "") == "interprocedural" and \
       G.node[target].get("kind", "") == "entry"):
      entries.add(target);
    #end if
  #end for
  
  # sadly, we can't do this check because csurf sometimes only adds summary
  # edges, but no model function  (e.g. for strlen, see
  # sed-3/FAULTY_F_AG_11 node n:-49:25)
  #if(not entries):
  #  print >> stderr, ("ERROR: no entry node found for call " + call);
  #  exit(1);
  ##end if
  
  return(entries);
#end: entries_from_call

"""
find_function_entry(): Find the entry node for the given function id.
@param G the graph
@param funcId the function id
@return the entry node, if found, or None otherwise
"""
def find_function_entry(G, funcId):
  entryNode = None;

  for (n, attr) in G.nodes(data=True):
    if(attr.get("kind", "") == "entry" and
       function_id(n) == funcId):
      if(entryNode):
        print >> stderr, ("ERROR: multiple entry nodes for function id '" + \
                          str(funcId) + "'");
        exit(1);
      entryNode = n;
  #end for

  return entryNode;
#end: find_function_entry

"""
find_function_data(): Determine the graphml id for the given function name, 
and whether or not the function is a library function.
@param G the graph
@param funcName the function name
@return a pair: (the integer function id--or none if not found, isLibrary)
"""
def find_function_data(G, funcName):
  theValue = None;
  isLibrary = False;
  
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "") == "entry" and
       attr.get("procedure", "") == funcName):
      if(theValue):
        print >> stderr, ("ERROR: multiple functions match function name '" + \
                          funcName + "'");
        exit(1);
      try:
        theValue = function_id(n);
      except:
        print >> stderr, ("ERROR: bad graphml entry node formatting for " +
                          "function \'" + funcName + "\'");
        exit(2);
      if("csurf/libmodels" in attr.get("file", "")):
        isLibrary = True;
  #end for
  
  return (theValue, isLibrary);
#end: find_function_data

"""
find_function_id(): Determine the graphml id for the given function name.
@param G the graph
@param funcName the function name
@return the integer function id for funcName from G or None if not found
"""
def find_function_id(G, funcName):
  return(find_function_data(G, funcName)[0]);
#end: find_function_id

"""
restrict_to_function(): Create a copy of the graph restricted to contain only
nodes from the passed function.
@param G the graph
@param funcId the integer id of the function
@return the restricted graph
"""
def restrict_to_function(G, funcId):
  if(not funcId):
    print >> stderr, ("ERROR: unable to determine graphml function id " +
                      "for \'" + str(funcId) + "\'");
    exit(1);
  #end if
  
  nodesToInclude = [];
  for n in G.nodes(False):
    thisId = 0;
    try:
      thisId = function_id(n);
    except:
      print >> stderr, ("ERROR: bad graphml expression node formatting for " +
                        "node \'" + n + "\'");
      exit(2);
    if(thisId == funcId):
      nodesToInclude += [n];
  #end for
  
  return(networkx.MultiDiGraph(G.subgraph(nodesToInclude)));
#end: restrict_to_function

"""
find_possible_match_nodes(): The public version (used by others).  Determine
all possible nodes of the graph which could represent the searchLine node based
on the line and the function in which the line occurs.  If fromNodes (which
should probably be called "toNodes") is provided, the algorithm is a bit more
complicated, and involves potentially skipping some nodes to get between.
@param G the graph
@param searchLine the line on which to match
@param funcId the function id of the function determined based on the
              graphml data (or 0 for all functions)
@param fromNodes optionally only return nodes with a successor in fromNodes
@return all possible program nodes
   => [node]
"""
def find_possible_match_nodes(G, searchLine, funcId, fromNodes=None):
  possibleNodes = [];
  for (n, attr) in G.nodes(True):
    linesAttr = attr.get("lines", "");
    if(not linesAttr or linesAttr[0] != '(' or linesAttr[-1] != ')'):
      continue;
    lines = map(int, linesAttr[1:-1].split());
    #if(attr.get("kind", "") == "expression" and searchLine in lines):
    if(searchLine in lines):
      thisId = 0;
      try:
        thisId = int(n.split(':')[1]);
      except:
        print >> stderr, ("ERROR: bad graphml expression node formatting for " +
                          "node \'" + n + "\'");
        exit(1);
      if(funcId == 0 or thisId == funcId):
        if(fromNodes):
          # if the line contains a formal-in, we must grab that node
          # because it won't be reachable via control-flow edges
          if(attr.get("kind", "") == "formal-in"):
            possibleNodes += [n];
            continue;
          #end if
          
          succEdges = G.out_edges([n], False, True);
          for (thisNode, successor, data) in succEdges:
            # qwerty: just changed...verify still works!
            if(data.get("type", "flow") != "flow"):
              continue;
            # if(successor in fromNodes and data.get("type", "flow") == "flow"):
            if(successor in fromNodes):
              possibleNodes += [n];
              #possibleNodes += [(n, attr)];
              break;
            else:
              # follow useless label,empty loop, or unconditional jump nodes
              # if they come into play
              foundHere = False;
              extraPossible = [];
              worklist = [successor];
              alreadyProcessed = set([]);
              while(worklist):
                successor = worklist.pop(0);
                if(successor in alreadyProcessed):
                  continue;
                else:
                  alreadyProcessed.add(successor);
                
                if(successor in fromNodes):
                  possibleNodes += extraPossible + [n];
                  foundHere = True;
                  break;
                #end if
                if(G.node[successor].get("kind", "") not in ["label", "jump", "switch-case"] and \
                   G.node[successor].get("label", "") not in ["for()", "for ()"] and \
                   (G.node[successor].get("kind", "") != "control-point" or G.node[successor].get("syntax", "") != "while" or G.node[successor].get("label", "") != "1")):
                  continue;
                #end if
                
                flowSuccs = [(lNode,successor,data) for (lNode,successor,data) in G.out_edges([successor], False, True) if data.get("type", "flow") == "flow"];
                if(G.node[successor].get("kind", "") in ["label", "jump", "switch-case"] and \
                   len(flowSuccs) != 1):
                  print >> stderr, ("ERROR: graphml indicates " + \
                                    str(len(flowSuccs)) +\
                                    " successors for unconditional br node "+ \
                                    successor + "." + \
                                    "They are: " + str(flowSuccs));
                  exit(2);
                #end if
                
                extraPossible += [successor];
                for (thisNode, successor, data) in flowSuccs:
                  if(data.get("type", "flow") == "flow"):
                    worklist += [successor];
                #end for
              #end while
              if(foundHere):
                break;
            #end if
          #end for
        else:
          possibleNodes += [n];
          #possibleNodes += [(n, attr)];
        #end if
      #end if(funcId)
    #end if(searchLine)
  #end for
  
  # if there are any call nodes in possibleNodes, also add their ga-in/outs
  toAdd = [];
  for node in possibleNodes:
    if(G.node[node].get("kind", "") == "call-site"):
      succEdges = G.out_edges([node], False, True);
      for (thisNode, succ, data) in succEdges:
        if(data.get("type", "") == "control" and \
           G.node[succ].get("kind", "").strip() in ["global-actual-in", "global-actual-out"]):
          toAdd += [succ];
      #end for
    #end if
  #end for
  possibleNodes += toAdd;
  
  return possibleNodes;
#end: find_possible_match_nodes

"""
_compute_doms_internal(): Do most of the real dominator computation.  It could
start at either entry or exit and go forward or backward (depending on
specified direction); thus, it can be used for dominators or post-dominators.
@param G the graph
@param forwardDoms if true, do forward dominators (i.e. dominators) as opposed
                   to backward dominators (i.e. post-dominators)
@param attributeName the name to use for the dominator attribute
                     (e.g. "dominators" or "post-dominators")
"""
def _compute_doms_internal(G, forwardDoms, attributeName):
  startNodeKind = "entry" if forwardDoms else "exit";
  predEdgeFunction = G.in_edges if forwardDoms else G.out_edges;
  succEdgeFunction = G.out_edges if forwardDoms else G.in_edges;
  
  startNodes = [n for (n, attr) in G.nodes(True) \
                  if attr.get("kind", "") == startNodeKind];
  
  worklist = None;
  for start in startNodes:
    if(worklist):
      print >> stderr, ("ERROR: worklist messed up!");
      exit(1);
    worklist = deque([start]);
    
    while(worklist):
      n = worklist.popleft();
      
      # compute incoming dominators from predecessors in the CFG
      incomingDoms = None;
      for (src, target, data) in predEdgeFunction([n], False, True):
        if(data.get("type", "flow") != "flow"):
          continue;
        predData = G.node[src] if forwardDoms else G.node[target];
        
        # if dominators for predecessor aren't yet filled in, count it as "all
        # nodes" (by just skipping it in the intersection)
        predDoms = predData.get(attributeName, "").strip();
        if(not predDoms):
          continue;
        if(predDoms[0] != '(' or predDoms[-1] != ')'):
          print >> stderr, ("ERROR: invalid dominator formatting: '" + \
                            predDoms + "' for node: " + predecessor);
          exit(1);
        domArray = predDoms[1:-1].split();
        domSet = set(domArray);
        if(len(domSet) < 1):
          print >> stderr, ("ERROR: invalid dominator set: '" + \
                            predDoms + "' for node: " + predecessor);
          exit(1);
        
        # incomingDoms should start at "all nodes" (indicated by None)
        if(incomingDoms == None):
          incomingDoms = domSet;
        else:
          incomingDoms = incomingDoms & domSet;
      #end for
      
      # add yourself into the list of dominators
      if(incomingDoms == None):
        incomingDoms = set([]);
      myDoms = incomingDoms | set([n]);
      
      # update my dominators
      previousDoms = set([]);
      previousDomString = G.node[n].get(attributeName, "");
      if(previousDomString):
        if(previousDomString[0] != "(" or previousDomString[-1] != ")"):
          print >> stderr, ("ERROR: in previous dom string for node: " + n);
          exit(1);
        previousDoms = set(previousDomString[1:-1].split());
      #end if
      G.node[n][attributeName] = "(" + " ".join(list(myDoms)) + ")";
      
      # if changed, add successor CFG nodes into the worklist
      if(myDoms != previousDoms):
        for (src, target, data) in succEdgeFunction([n], False, True):
          if(data.get("type", "flow") != "flow"):
            continue;
          if(function_id(src) != function_id(target)):
            print >> stderr, ("ERROR: Unexpected departure from function in " +\
                              "dominators: " + src + " != " + target);
            exit(1);
          if(forwardDoms):
            worklist.append(target);
          else:
            worklist.append(src);
        #end for
      #end if
    #end while
  #end for
#end: _compute_doms_internal

"""
compute_doms(): Given a graph, compute the dominators and post-dominators for
each node.  The subroutine _compute_doms_internal() does most of the actual
computation.
@param G the graph
"""
def compute_doms(G):
  _compute_doms_internal(G, True, "dominators");
  _compute_doms_internal(G, False, "post-dominators");
#end: compute_doms

"""
fix_graph(): Perform various fix-up operations on the graph to make it match
llvm's version better.  Do each of the following:
1. Add use/def data for global-formal/actuals so they use or def ALL variables.
2. Explode all auxiliary nodes into their fully-enumerated data dependence edges
3. Combine all line numbers for multi-line function calls.  This is done simply
   by taking any node with any line number in the call node and making it all
   closed.  I hate to do this, but it seems the only reasonable solution...
4. Combine all lines together for multi-line statements.  Clang debug data
   assigns the first line after the keyword as the line, so we need to extend
   that ambiguity to the graphml graph.
5. Add in unmapped lines to the line numbers for the condition of a do-while
   loop.  Clang maps these to the }, so a \n messes up the analysis for the
   while(condition) on the following line.
6. Check for nodes with no control parent. (Why am I doing this so early?)
7. Remove all "false" control edges out of jump nodes (these don't represent
   real flow and are, frankly, stupid).  Also, delete all decl nodes.  They
   don't mean anything and are hard to deal with.
8. Check for nodes with (still) no control parent.
9. Combine basic blocks which are separated in the graphml despite being
   single-entry single-exit.
10. Compute dominator/post-dominator information.
11. Mark implicit returns

PREVIOUSLY:
-  Remove all "exceptional-return" nodes (we know we didn't take them).
-  Add control dependence edges for all global-formal-in's missing them.  Also
   add "speculative" control dependence edges for all global-actual-in/outs with
   no control parents to all possible parents: AMBIGUITY.

@param G the graph
@return the corrected graph
"""
def fix_graph(G):
  global FILTER_DEBUG;
  """
  print >> stderr, ("SPECIAL PHASE");
  delIds = [];
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "") == "entry" and \
       attr.get("label", "")[:14] in ["entry: #System", "entry: #Global", "entry: #File_I"]):
      delIds += [function_id(n)];
  #end for
  
  print >> stderr, ("the ids: " + str(delIds));
  
  for (n, attr) in G.nodes(True):
    if(function_id(n) in delIds):
      G.remove_node(n);
  #end for
  """
  
  ############################################################################
  # PHASE 1: add some missing data (e.g. uses and defs for
  # global-formals/actuals)
  ############################################################################
  clock = CSIClock();
  print("PHASE 1");
  for (n, attr) in G.nodes(True):
    if(not attr.get("kind", "") in ["global-actual-in", "global-actual-out", \
                                    "global-formal-in", "global-formal-out"]):
      continue;
    if(attr.get("kind", "") in ["global-formal-in", "global-actual-out"]):
      attr["alocs-mayd"] = "PP_ALL";
    elif(attr.get("kind", "") in ["global-formal-out", "global-actual-in"]):
      attr["alocs-used"] = "PP_ALL";
  #end for
  
  
  ############################################################################
  # PHASE 2: explode all auxiliary nodes
  ############################################################################
  clock.takeSplit();
  print("PHASE 2");
  print("Starting at: " + str(datetime.now()));
  
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "").strip() != "auxiliary"):
      continue;
    
    predNodes = set([]);
    succNodes = set([]);
    
    predEdges = G.in_edges([n], False, True);
    for (predecessor, thisNode, data) in predEdges:
      if(data.get("type", "") != "data"):
        print >> stderr, ("WARNING: non-data edge into auxiliary node " + n);
        continue;
      #end if
      
      predNodes.add(predecessor);
    #end for
    
    succEdges = G.out_edges([n], False, True);
    for (thisNode, successor, data) in succEdges:
      if(data.get("type", "") != "data"):
        print >> stderr, ("WARNING: non-data edge out of auxiliary node " + n);
        continue;
      #end if
      
      succNodes.add(successor);
    #end for
    
    if(len(predNodes) * len(succNodes) > 1000):
      print >> stderr, ("NOTE: exploding auxiliary node " + n + " " + \
                        "with (bad due to) large cross-product (" + \
                        str(len(predNodes)*len(succNodes)) + ")");
      #continue;
    #end if
    
    for pred in predNodes:
      for succ in succNodes:
        G.add_edge(pred, succ, attr_dict={"type" : "data"});
    #end for
    G.remove_node(n);
  #end for
  
  
  ############################################################################
  # PHASE 3: close all line numbers for nodes within call node line numbers and
  # ternary expressions
  ############################################################################
  clock.takeSplit();
  print("PHASE 3");
  print("Starting at: " + str(datetime.now()));
  
  lineUpdates = {}; # (funcId,line) : {lines}
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "").strip() != "call-site" and \
       not search(".*[?].*[:].*", attr.get("label", "").strip())):
      continue;
    
    lines = attr.get("lines", "");
    if(not lines or lines[0] != '(' or lines[-1] != ')'):
      continue;
    linesArray = map(int, lines[1:-1].split());
    linesSet = set(linesArray);
    if(len(linesSet) < 2):
      continue;
    linesSet |= set(range(min(linesSet), max(linesSet)));
    
    functionId = function_id(n);
    
    for line in linesSet:
      lineUpdates[(functionId, line)] = \
         lineUpdates.get((functionId, line), set([])) | linesSet;
    #end for
  #end for
  if(FILTER_DEBUG):
    print >> stderr, ("lineUpdates: \n" + str(lineUpdates));
  for (n, attr) in G.nodes(True):
    lines = attr.get("lines", "");
    if(not lines or lines[0] != '(' or lines[-1] != ')'):
      continue;
    linesArray = map(int, lines[1:-1].split());
    linesSet = set(linesArray);
    
    functionId = function_id(n);
    
    finalLines = set(linesArray[:]);
    for line in linesSet:
      finalLines |= lineUpdates.get((functionId, line), set([]));
    if(finalLines != linesSet):
      attr["lines"] = "(" + " ".join(map(str, list(finalLines))) + ")";
  #end for
  
  
  ############################################################################
  # PHASE 4: combine line numbers for multi-line statements (AMBIGUITY)
  ############################################################################
  clock.takeSplit();
  print("PHASE 4");
  print("Starting at: " + str(datetime.now()));
  
  didChanges = True;
  while(didChanges):
    didChanges = False;
    for (n, attr) in G.nodes(True):
      nodeSyntax = attr.get("syntax", "").strip();
      if(nodeSyntax not in ["if", "while", "for", "do", "switch"]):
        continue;
      succEdges = G.out_edges([n], False, True);
      for (thisNode, successor, data) in succEdges:
        if(data.get("type", "flow") != "flow"):
          continue;
        succData = G.node[successor];
        succSyntax = succData.get("syntax", "");
        #if(nodeSyntax == "switch"):
        #  if(succSyntax not in ["switch", "case"]):
        #    continue;
        #elif(succSyntax != nodeSyntax):
        if(succSyntax != nodeSyntax):
          continue;
        
        # qwerty: should also verify that there is a control dependence between
        # them...i think (not true for multi-line function arguments--not even
        # being handled right now...)
        
        linesAttr = attr.get("lines", "");
        succLinesAttr = succData.get("lines", "");
        if(not linesAttr or linesAttr[0] != '(' or linesAttr[-1] != ')' or \
           not succLinesAttr or succLinesAttr[0] != '(' or succLinesAttr[-1] != ')'):
          continue;
        nodeLines = set(linesAttr[1:-1].split());
        succLines = set(succLinesAttr[1:-1].split());
        if(nodeLines != succLines):
          combinedLines = " ".join(list(nodeLines.union(succLines)));
          attr["lines"] = "(" + combinedLines + ")";
          succData["lines"] = "(" + combinedLines + ")";
          didChanges = True;
        #end if
      #end for
    #end for
  #end while
  
  
  ############################################################################
  # PHASE 5: add in unused lines for do-while conditions (and their } )
  # (AMBIGUITY)
  # qwerty: what app:version:line and fault:test-case is this from?
  ############################################################################
  clock.takeSplit();
  print("PHASE 5");
  print("Starting at: " + str(datetime.now()));
  
  # originallyEmpty: store line numbers which originally matched to no nodes
  # (so we don't give one node the line number and nobody else can join the fun)
  originallyEmpty = set([]); # : set((funcId, line-num))
  # qwerty: or just do this...figure out all (fnid, line#) pairs that exist
  
  for (n, attr) in G.nodes(True):
    nodeSyntax = attr.get("syntax", "").strip();
    if(nodeSyntax != "do"):
      continue;
    
    lines = attr.get("lines", "");
    if(not lines or lines[0] != '(' or lines[-1] != ')'):
      continue;
    functionId = function_id(n);
    try:
      linesArray = lines[1:-1].split();
      smallestLine = min(map(int, linesArray));
    except Exception, e:
      print >> stderr, ("ERROR: bad graphml lines formatting for node " + \
                        n + " -> " + str(e));
      exit(2);
    #end try
    
    # always include at least one extra line -- bug #36 -- 
    attr["lines"] = "(" + " ".join(linesArray) + " " + \
                    str(smallestLine-1) + ")";
    linesArray += [str(smallestLine-1)];
    smallestLine -= 1;
    
    while((functionId, (smallestLine-1)) in originallyEmpty or \
          not find_possible_match_nodes(G, smallestLine-1, functionId)):
      attr["lines"] = "(" + " ".join(linesArray) + " " + \
                      str(smallestLine-1) + ")";
      originallyEmpty.add((functionId, smallestLine-1));
      linesArray += [str(smallestLine-1)];
      
      if(FILTER_DEBUG):
        print >> stderr, ("node: " + n + "\nlines: " + attr["lines"]);
      
      smallestLine -= 1;
    #end while
  #end for
  
  
  ############################################################################
  # PHASE 6: check for any nodes that have no control parent
  # there should be none
  ############################################################################
  clock.takeSplit();
  print("PHASE 6");
  print("Starting at: " + str(datetime.now()));
  
  for (n, attr) in G.nodes(True):
    if(next((True for (pred, cur, data) in G.in_edges_iter([n], data=True) if data.get("type", "") == "control"), False)):
      continue;
    
    if(attr.get("kind", "").strip() not in ["entry", "auxiliary"]):
      print >> stderr, ("ERROR: found a node with no control parent that should!");
      print >> stderr, ("node: " + n + "  attr: " + str(attr));
      #exit(1);
      print >> stderr, ("FOR THIS TEST: I won't exit.  But something needs to be done!");
  #end for
  
  
  ############################################################################
  # PHASE 7: remove all "false" edges out of jump, return, and case nodes.
  # Remove all decl nodes.
  ############################################################################
  clock.takeSplit();
  print("PHASE 7");
  print("Starting at: " + str(datetime.now()));
  
  for(n, attr) in G.nodes(True):
    if(attr.get("kind", "").strip() not in ["jump", "return", "switch-case"]):
      continue;
    
    succEdges = G.out_edges([n], True, True);
    for (thisNode, successor, key, data) in succEdges:
      if(data.get("type", "") == "control" and data.get("when", "") == "false"):
        G.remove_edge(thisNode, successor, key);
    #end for
  #end for
  
  # then, delete all decl nodes
  for (n, attr) in G.nodes(True):
    # decl nodes have no "kind"
    if(attr.get("kind", "").strip() or attr.get("label", "").strip()[:5] != "decl:"):
      continue;
    
    G.remove_node(n);
  #end for
  
  
  ############################################################################
  # PHASE 8: check for any nodes that still have no control parent
  # this is AMBIGUITY and BAD because we don't know what to do about these!
  # we could also consider deleting any chains they start...whatever, dumb
  # TODO: perhaps we need to verify that these only correspond to dead code?
  ############################################################################
  clock.takeSplit();
  print("PHASE 8");
  print("Starting at: " + str(datetime.now()));
  
  for (n, attr) in G.nodes(True):
    if(next((True for (pred, cur, data) in G.in_edges_iter([n], data=True) if data.get("type", "") == "control"), False)):
      continue;
    
    if(attr.get("kind", "").strip() not in ["entry", "auxiliary"]):
      print >> stderr, ("WARNING: found a node with no control parent after " +\
                        "\"false\" control deletion.");
      print >> stderr, ("node: " + n + "  attr: " + str(attr));
      #exit(1);
      print >> stderr, ("NOTE: we expect this should be dead code.  " +\
                        "Otherwise, this is a problem.");
  #end for
  
  
  ############################################################################
  # PHASE 9: combine basic blocks
  ############################################################################
  clock.takeSplit();
  print("PHASE 9");
  print("Starting at: " + str(datetime.now()));
  
  basicBlocks = {};
  for (n, attr) in G.nodes(True):
    blockData = attr.get("basic-block", "").strip();
    basicBlocks[blockData] = basicBlocks.get(blockData, set([]));
    basicBlocks[blockData].add(n);
  #end for
  
  for (src, target, attr) in G.edges_iter(data=True):
    if(attr.get("type", "flow") != "flow"):
      continue;
    
    srcBB = G.node[src].get("basic-block");
    targetBB = G.node[target].get("basic-block");
    if(not srcBB or not targetBB or srcBB == targetBB):
      continue;
    
    outCount = 0;
    inCount = 0;
    for (outSrc, outTarget, outAttr) in G.out_edges_iter([src], data=True):
      if(outAttr.get("type", "flow") == "flow"):
        outCount += 1;
    for (inSrc, inTarget, inAttr) in G.in_edges_iter([target], data=True):
      if(inAttr.get("type", "flow") == "flow"):
        inCount += 1;
    if(inCount < 1 or outCount < 1):
      print >> stderr, ("ERROR: problem in computation of new basic " +
                        "block for edge " + str((src, target)));
      exit(2);
    elif(inCount == 1 and outCount == 1):
      if(len(srcBB.strip().split()) != 2 or len(targetBB.strip().split()) != 2):
        print >> stderr, ("ERROR: invalid BB name formatting " +
                          src + "=(" + srcBB + ") -> " +
                          target + "=(" + targetBB + ")");
        exit(1);
      newBB = srcBB.strip().split()[0] + " " + targetBB.strip().split()[1];
      for n in basicBlocks[srcBB]:
        G.node[n]["basic-block"] = newBB;
      for n in basicBlocks[targetBB]:
        G.node[n]["basic-block"] = newBB;
      basicBlocks[newBB] = basicBlocks[srcBB] | basicBlocks[targetBB];
    #end if
  #end for
  
  ############################################################################
  # PHASE 10: compute dominator/post-dominator information
  ############################################################################
  clock.takeSplit();
  print("PHASE 10");
  print("Starting at: " + str(datetime.now()));
  
  compute_doms(G);
  
  
  ############################################################################
  # PHASE 11: mark implicit return nodes
  ############################################################################
  clock.takeSplit();
  print("PHASE 11");
  print("Starting at: " + str(datetime.now()));
  
  # first, get all exits
  # exits : {line : {functionId}}
  exits = {};
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "").strip() != "exit"):
      continue;
    
    lines = attr.get("lines", "");
    if(not lines or lines[0] != '(' or lines[-1] != ')'):
      continue;
    try:
      lines = map(int, lines[1:-1].split());
    except Exception, e:
      print >> stderr, ("ERROR: bad graphml lines formatting for exit node " + \
                        n + " -> " + str(e));
      exit(2);
    #end try
    
    functionId = function_id(n);
    
    for line in lines:
      if(functionId in exits.get(line, set([]))):
        print >> stderr, ("ERROR: multiple identical exits: " + n);
        exit(1);
      exits[line] = exits.get(line, set([]));
      exits[line].add(functionId);
    #end for
  #end for
  
  # then, look for returns with lines matching the exit
  # AMBIGUITY slightly, but this is a reasonable way to identify implicit
  # returns
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "").strip() != "return"):
      continue;
    
    lines = attr.get("lines", "");
    if(not lines or lines[0] != '(' or lines[-1] != ')'):
      continue;
    try:
      lines = map(int, lines[1:-1].split());
    except Exception, e:
      print >> stderr, ("ERROR: bad graphml lines formatting for ret node " + \
                        n + " -> " + str(e));
      exit(2);
    #end try
    
    functionId = function_id(n);
    
    allMatch = True;
    for line in lines:
      if(functionId not in exits.get(line, set([]))):
        allMatch = False;
        break;
    #end for
    
    if(allMatch):
      G.node[n]["implicit"] = "True";
  #end for
  
  
  clock.takeSplit();
  return G;
#end: fix_graph
