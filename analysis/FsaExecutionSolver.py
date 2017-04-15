#!/s/python-2.7.1/bin/python

from sys import stderr, stdout

from fst import Acceptor

from ExecutionSolver import ExecutionSolver
from utils import findEntryForNode, findGraphEntry
from csilibs.graphlibs import is_cfg_node

"""
fsaIsEmpty(): Check if the language recognized by the FSA is empty.
@param fsa the Finite-State Automaton
@param safeCopy whether or not the FSA needs to be preserved after this call
@return whether or not the language accepted by the FSA is empty
"""
def fsaIsEmpty(fsa, safeCopy=True):
  #empty if it has no states
  if(len(fsa) == 0):
    return(True);
  
  # or if there are no connected states on paths initial->final
  # (according to http://www.openfst.org/twiki/bin/view/FST/ConnectDoc
  # the complexity is O(N+E) where N = # of states and E = # of edges.  The
  # fastest possible is O(E), so this is close enough)
  if(safeCopy):
    cFsa = fsa.copy();
  else:
    cFsa = fsa;
  cFsa.connect();
  return(len(cFsa) == 0);
#end: fsaIsEmpty

"""
getComplementFsm(): Return the FSA that is the complement of the provided FSA.
The function will not determinize the FSA; you must do that first.
@param fsm the automaton
@return the complement automaton of fsm
"""
def getComplementFsm(fsm):
  assert(fsm.input_deterministic);
  
  fsm = fsm.copy();
  for state in range(len(fsm)):
    fsm[state].final = False if fsm[state].final else True;
  #end for
  
  return(fsm);
#end: getComplementFsm

class FsaExecutionSolver(ExecutionSolver):
  __slots__ = "__solver, __solverVars, __nextCompact";
  
  """
  @override
  __init__(): Process the graph, encoding its structure as a Finite-State
  Automata (FSA).
  @param G the graph
  """
  def __init__(self, G):
    self.__solver = Acceptor();
    self.__nextCompact = 0;
    
    # first, create the node dictionary
    self.__solverVars = {};
    
    # begin with the entry node; also create the special "pre-entry" node
    # (necessary prior to entry because we put labels on edges)
    (entryNode, isInterprocedural) = findGraphEntry(G);
    self.__solver[0].initial = True;
    self.__solverVars[entryNode] = 1;
    self.__solver[1].final = True;
    self.__solver.add_arc(0, 1, entryNode);
    
    i = 2;
    for (n, attr) in G.nodes(True):
      # don't export SDG-only nodes
      if(n == entryNode or not is_cfg_node(G, n)):
        continue;
      #end if
      
      self.__solverVars[n] = i;
      
      # initially, all nodes are legal stopping points
      self.__solver[i].final = True;
      
      i += 1;
    #end for
    
    # then, encode all edges in the CFG
    for (n, nodeId) in self.__solverVars.iteritems():
      if(isInterprocedural and G.node[n].get("kind", "") == "call-site"):
        foundOne = False;
        for (source, target, attr) in G.out_edges_iter([n], data=True):
          if(attr.get("type", "flow") == "control" and \
             attr.get("scope", "") == "interprocedural"):
            self.__solver.add_arc(nodeId, self.__solverVars[target], target);
            foundOne = True;
          #end if
        #end for
        
        # add appropriate intraprocedural edges: only if
        # (a) the called function is not in the graphml, or
        # (b) the target is a crash point (which is essentially ambiguity
        #     nonsensemeaning that we crashed trying to make the call itself)
        for (source, target, attr) in G.out_edges_iter([n], data=True):
          if(attr.get("type", "flow") == "flow" and \
             attr.get("scope", "") != "interprocedural" and \
             (not foundOne or G.node[target].get("kind", "") == "crash")):
            self.__solver.add_arc(nodeId, self.__solverVars[target], target);
          #end if
        #end for
      elif(isInterprocedural and G.node[n].get("kind", "") == "exit"):
        entryForExit = findEntryForNode(G, n);
        for (source, target, attr) in G.in_edges_iter([entryForExit], data=True):
          if(attr.get("type", "flow") == "control" and \
             attr.get("scope", "") == "interprocedural"):
            # edge from exit -> all successors of the call to this function
            for (call, callTarget, attr) in G.out_edges_iter([source], data=True):
              if(attr.get("type", "flow") == "flow" and \
                 attr.get("scope", "") != "interprocedural" and \
                 G.node[callTarget].get("kind", "") != "crash"):
                self.__solver.add_arc(nodeId, self.__solverVars[callTarget], callTarget);
              #end if
            #end for
          #end if
        #end for
      else:
        for (source, target, attr) in G.out_edges_iter([n], data=True):
          if(attr.get("type", "flow") == "flow" and \
             attr.get("scope", "") != "interprocedural"):
            self.__solver.add_arc(nodeId, self.__solverVars[target], target);
          #end if
        #end for
      #end if
    #end for
    
    # assert that the encoded CFG has legal executions
    assert(self.isSat());
  #end: __init__
  
  """
  @override
  isSat(): Check if the language recognized by the FSA is empty.
  @return whether or not the language accepted by the FSA is empty
  """
  def isSat(self):
    return(not fsaIsEmpty(self.__solver));
  #end: isSat
  
  """
  getObsYesFsa: Get the FSA for encoding the yes-executed observation.
  @param possibleYes a sequence of sets of possible matches to the true entry
                    (usually a singleton)
            => [{G.nodes}]
  @param crash a boolean specifying whether this is a crashing observation
  @return the FSA representing the execution constraint
  """
  def getObsYesFsa(self, possibleYes, crash=False):
    fsm = Acceptor(self.__solver.isyms);
    
    # at least one each of the possibleYes executed in order
    totalNodes = 0;
    for group in possibleYes:
      # verify that all nodes are in the graph
      for n in group:
        if(n not in self.__solverVars):
          print >> stderr, ("ERROR: invalid YES observation: " + str(n));
          exit(1);
        #end if
      #end for
      
      # add outgoing edges for this entry=node
      for n in self.__solverVars:
        if(n in group):
          fsm.add_arc(totalNodes, totalNodes+1, n);
        else:
          fsm.add_arc(totalNodes, totalNodes, n);
      #end for
      totalNodes += 1;
    #end for
    
    if(crash):
      # if we crashed here: need to end on crash node
      for n in self.__solverVars:
        if(n in possibleYes[-1]):
          fsm.add_arc(totalNodes, totalNodes, n);
        else:
          fsm.add_arc(totalNodes, totalNodes-1, n);
        #end if
      #end for
    else:
      # if we didn't crash here: after that, no constraints
      for n in self.__solverVars:
        fsm.add_arc(totalNodes, totalNodes, n);
      #end for
    #end if
    
    # sort the arcs (this is required for intersecting FSMs)
    fsm[totalNodes].final = True;
    fsm.arc_sort_input();
    fsm.arc_sort_output();
    return(fsm);
  #end: getObsYesFsa
  
  """
  @override
  encodeObsYes(): Encode the constraint for a yes-executed observation.
  @param possibleYes a sequence of sets of possible matches to the true entry
                    (usually a singleton)
            => [{G.nodes}]
  @param crash a boolean specifying whether this is a crashing observation
  """
  def encodeObsYes(self, possibleYes, crash=False):
    fsm = self.getObsYesFsa(possibleYes, crash);
    
    # check if the inverse is impossible (i.e. if this observation is redundant)
    #invFsm = getComplementFsm(fsm);
    #if(fsaIsEmpty(self.__solver & invFsm)):
    #  return;
    
    # intersect in the observation FSM
    self.__solver &= fsm;
    
    # if the FSA is getting really big, trade off some time to save space
    self.__nextCompact -= 1;
    if(self.__nextCompact < 0 and len(self.__solver) > 1000000):
      self.__solver = self.__solver.determinize();
      self.__solver.minimize();
      self.__nextCompact = 2;
    #end if
  #end: encodeObsYes
  
  """
  @override
  encodeCrash(): Encode the constraint for the crashing location.
  @param crashStack a representation of possible crashes in the stack trace,
                    ending in the final possible crashing nodes
            => [({G.nodes}, {G.nodes}), ..., ({G.nodes}, None)]
  """
  def encodeCrash(self, crashStack):
    obsCrash = [];
    for (callNodes, entryNodes) in crashStack:
      obsCrash.append(callNodes);
      if(entryNodes):
        obsCrash.append(entryNodes);
    #end for

    self.encodeObsYes(obsCrash, True);

    # assert that the encoded CFG still has legal executions (i.e. the crash
    # is reachable)
    assert(self.isSat());
  #end: encodeCrash
  
  """
  getObsNoFsa: Get the FSA for encoding the not-executed observation.
  @param possibleNo a set of possible matches to the true entry
                    (NOTE: currently only supports a singleton)
            => {G.nodes}
  @return the FSA representing the execution constraint
  """
  def getObsNoFsa(self, possibleNo):
    # we currently only handle singleton "no" observations
    if(len(possibleNo) != 1):
      print >> stderr, ("ERROR: FSA solver can currently only handle " + \
                        "unambiguous FALSE observations");
      exit(1);
    #end if
    obsNo = list(possibleNo)[0];
    
    fsm = Acceptor(self.__solver.isyms);
    
    # all nodes except obsNo are fine
    for n in self.__solverVars:
      if(n == obsNo):
        continue;
      fsm.add_arc(0, 0, n);
    #end for
    
    # sort the arcs (this is required for intersecting FSMs)
    fsm[0].final = True;
    fsm.arc_sort_input();
    fsm.arc_sort_output();
    return(fsm);
  #end: getObsNoFsa
  
  """
  @override
  encodeObsNo(): Encode the constraint for a not-executed observation.
  @param possibleNo a set of possible matches to the true entry
                    (NOTE: currently only supports a singleton)
            => {G.nodes}
  """
  def encodeObsNo(self, possibleNo):
    fsm = self.getObsNoFsa(possibleNo);
    
    # intersect in the observation FSM
    self.__solver &= fsm;
  #end: encodeObsNo
  
  """
  @override
  findKnownExecution(): Figure out which nodes in the CFG (a) are known to have
  executed at least once, (b) are known to have not executed, and (c) may or may
  not have executed given the crash location.
  @return (defYes, defNo, maybe)
             => ({G.nodes}, {G.nodes}, {G.nodes})
  """
  def findKnownExecution(self):
    defYes = set([]);
    defNo = set([]);
    maybe = set([]);
    
    total = len(self.__solverVars);
    soFar = 0;
    for (n, nodeId) in self.__solverVars.iteritems():
      testSolve = self.__solver & self.getObsYesFsa([[n]]);
      possibleYes = not fsaIsEmpty(testSolve, False);
      
      testSolve = self.__solver & self.getObsNoFsa([n]);
      possibleNo = not fsaIsEmpty(testSolve, False);
      
      if(not possibleYes and not possibleNo):
        print >> stderr, ("ERROR: graph node " + n + " neither executed nor " +\
                          "didn't execute!");
        exit(1);
      elif(possibleYes and possibleNo):
        maybe.add(n);
      elif(possibleYes):
        defYes.add(n);
      else:
        defNo.add(n);
      
      soFar += 1;
      if(soFar % 10 == 0):
        stdout.write("\r" + ("%.2f" % ((1.0*soFar)/(1.0*total)*100)) + "%: " + \
                     str(soFar) + " / " + str(total));
        stdout.flush();
      #end if
    #end for
    print("");
    
    return(defYes, defNo, maybe);
  #end: findKnownExecution
  
  """
  printFsa(): Print the FSA as a list of edges
  The format is:   from -> to / label / isFinal
  """
  def printFsa(self):
    for state in self.__solver.states:
      for arc in state.arcs:
          print("{} -> {} / {} / {}".format(state.stateid, arc.nextstate,
                                        self.__solver.isyms.find(arc.ilabel),
                                        self.__solver[arc.nextstate].final));
      #end for
    #end for
  #end: printFsa
  
  """
  printExecutions(): Print up to 10 accepted executions from the current FSA
  """
  def printExecutions(self):
    q = 0
    for path in self.__solver.paths():
      if(q > 10):
        break;
      else:
        q += 1;
      path_istring = ','.join(self.__solver.isyms.find(arc.ilabel) \
                              for arc in path);
      print("[{}]".format(path_istring));
    #end for
  #end: printExecutions
#end: class FsaExecutionSolver
