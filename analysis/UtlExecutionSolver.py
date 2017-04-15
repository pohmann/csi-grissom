#!/s/python-2.7.1/bin/python

from sys import stderr, stdout
from collections import deque

from ExecutionSolver import ExecutionSolver
from utils import findEntryForNode, findGraphEntry
from csilibs.graphlibs import is_cfg_node

from networkx.classes.multidigraph import MultiDiGraph
from networkx import condensation

class UtlExecutionSolver(ExecutionSolver):
  __slots__ = "__graph, __entryNode, __crashNode, __yesVectors, __allYes, __allNo";
  
  """
  @override
  __init__(): Process the graph, making our own CFG-only, massaged copy.
  @param G the graph
  """
  def __init__(self, G):
    self.__graph = MultiDiGraph();
    nodesToKeep = {n for n in G.nodes_iter(False) if is_cfg_node(G, n)};
    self.__graph.add_nodes_from(nodesToKeep);
    
    # mark the entry node
    (self.__entryNode, isInterprocedural) = findGraphEntry(G);
    assert(self.__entryNode in self.__graph);
    
    # then, copy all CFG edges
    for n in self.__graph.nodes_iter(False):
      if(isInterprocedural and G.node[n].get("kind", "") == "call-site"):
        foundOne = False;
        for (source, target, attr) in G.out_edges_iter([n], data=True):
          if(attr.get("type", "flow") == "control" and \
             attr.get("scope", "") == "interprocedural"):
            self.__graph.add_edge(n, target);
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
            self.__graph.add_edge(n, target);
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
                self.__graph.add_edge(n, callTarget);
              #end if
            #end for
          #end if
        #end for
      else:
        for (source, target, attr) in G.out_edges_iter([n], data=True):
          if(attr.get("type", "flow") == "flow" and \
             attr.get("scope", "") != "interprocedural"):
            self.__graph.add_edge(n, target);
          #end if
        #end for
      #end if
    #end for

    # setup for yes, no, maybe, and crash constraints
    self.__crashNode = None;
    self.__yesVectors = set([]);
    self.__allYes = set([]);
    self.__allNo = set([]);
  #end: __init__

  """
  __findSCCFromNode(): Find the SCC in G that contains n.
  @param G the graph
  @param nodeToFind the node to find
  @return the node in G that contains n within its SCC (throws an exception if
          not found)
  """
  def __findSCCFromNode(self, G, nodeToFind):
    for (n, data) in G.nodes_iter(data=True):
      if(nodeToFind in data.get("members", [])):
        return(n);
    #end for
    raise KeyError("Node " + str(nodeToFind) + " not found.");
  #end: __findSCCFromNode


  """
  __isDAG(): Verify that the graph is a DAG (i.e., has no cycles).
  @param G the graph
  @return true if G is a DAG, otherwise false
  """
  def __isDAG(self, G):
    # TODO: efficiency (this could be O(n))
    for n in G.nodes_iter(data=False):
      visited = set([]);
      worklist = deque([target for (source, target) in G.out_edges_iter([n])]);
      while(worklist):
        current = worklist.popleft();
        if(current == n):
          return(False);
        elif(current in visited):
          continue;
        else:
          visited.add(current);
        #end if

        for (source, target) in G.out_edges_iter([current]):
          worklist.append(target);
        #end for
      #end while
    #end for

    return(True);
  #end: __isDAG

  """
  __clearNodeFacts(): Clear old before- and after-facts from all nodes in the
                      SCC graph.
  @param G the graph
  NOTE: modifies G in-place
  """
  def __clearNodeFacts(self, G):
    for (n, data) in G.nodes_iter(data=True):
      data["afterFact"] = None;
      data["beforeFact"] = None;
    #end for
  #end: __clearNodeFacts

  """
  __isPrefix(): Check if the first list is a prefix of the second.
  @param first the first list
  @param second the second list
  @return true if first is a prefix of second, false otherwise
  """
  def __isPrefix(self, first, second):
    if(len(second) < len(first)):
      return(False);
    #end if

    for (i, val) in enumerate(first):
      if(second[i] != val):
        return(False);
      #end if
    #end for

    return(True);
  #end: __isPrefix

  """
  __getSCCEntryCrash(): Get the SCC for the entry and the crash node.  It is an
                        error if either is not found because G is not a SCC DAG.
  @param G the graph
  @return a tuple: (entrySCC, crashSCC)
  """
  def __getSCCEntryCrash(self, G):
    sccEntry = self.__findSCCFromNode(G, self.__entryNode);
    sccCrash = self.__findSCCFromNode(G, self.__crashNode);

    return(sccEntry, sccCrash);
  #end: __getSCCEntryCrash

  """
  __backwardReachableFrom(): Get all nodes in G backward-reachable from n.
  @param G the graph
  @param n the node to reach backward from
  @return the set of nodes (including n itself)
  """
  def __backwardReachableFrom(self, G, n):
    reachable = set([]);

    worklist = [n];
    while(worklist):
      current = worklist.pop();
      if(current in reachable):
        continue;
      reachable.add(current);

      for (source, target) in G.in_edges_iter([current]):
        worklist.append(source);
      #end for
    #end while

    return(reachable);
  #end: __backwardReachableFrom

  """
  __recReverseTopo(): A recursive sub-procedure for __reverseTopoOrdering().
  @param G the graph, must be a DAG (i.e., SCC collapsed)
  @param n the node (from G) to recurse backward from
  @param ordering a deque that will hold the final ordering
  @param temporaryMark internal marking for "in-progress" nodes
  @param doneMark internal marking for completely processed nodes
  """
  def __recReverseTopo(self, G, n, ordering, temporaryMark, doneMark):
    if(n in doneMark):
      return;
    elif(n in temporaryMark):
      print >> stderr, ("ERROR: graph for rev topo is not a DAG!");
      exit(1);
    #end if

    temporaryMark.add(n);
    for (source, target) in G.in_edges_iter([n]):
      self.__recReverseTopo(G, source, ordering, temporaryMark, doneMark);
    #end for

    assert(n not in doneMark);
    doneMark.add(n);
    ordering.appendleft(n);
  #end: __recReverseTopo

  """
  __reverseTopoOrdering(): Get a reverse topological ordering of the nodes in
                           G, including only those nodes backward-reachable from
                           crash.  Note that G must be an acyclic graph.
                           Further, this ordering may not include all of G's
                           nodes, meaning that some nodes WON'T have all
                           decendants processed before themselves...but they
                           will only exclude those nodes that are not
                           backward-reachable from crash.
  @param G the graph, must be a DAG (i.e., SCC collapsed)
  @param crash the ending point to use for the reverse ordering
  @return a reverse topological ordering of G's nodes, starting with crash.
          Crashes with error if G is not a DAG.
  """
  def __reverseTopoOrdering(self, G, crash):
    ordering = deque();
    temporaryMark = set([]);
    doneMark = set([]);

    self.__recReverseTopo(G, crash, ordering, temporaryMark, doneMark);
    return(ordering);
  #end: __reverseTopoOrdering

  """
  __entryCrashPath(): Check if there exists a path in the DAG from the
                      entry node's SCC, to the crash node's SCC.  The path must
                      also meet all the obsYes (__yesVectors) conditions.
  @param G the graph, must be a DAG (i.e., SCC collapsed)
  @return true if a consistent path entry->crash exists, otherwise false
  """
  def __entryCrashPath(self, G):
    # an empty graph clearly has no path from entry->crash
    if(not G):
      return(False);
    #end if

    self.__clearNodeFacts(G);

    # get the SCC for the entry and the crash
    (realEntry, realCrash) = self.__getSCCEntryCrash(G);
    # get those nodes backward-reachable from the crash
    crashReachable = self.__backwardReachableFrom(G, realCrash);
    # get a reverse topological order of nodes in G (up to and including the
    # crash)
    revTopoOrdering = self.__reverseTopoOrdering(G, realCrash);
    assert(set(revTopoOrdering) == crashReachable);

    for processing in revTopoOrdering:
      # ---------------------------------------------------------------------
      # compute this node's "after-fact" from the union of all incoming nodes
      # (i.e., the incoming fact from children)
      # ---------------------------------------------------------------------
      afterFact = None;
      for (source, target) in G.out_edges_iter([processing]):
        childFact = G.node[target].get("beforeFact", None);
        if(childFact == None):
          assert(target not in crashReachable);
          continue;
        else:
          assert(len(childFact) == len(self.__yesVectors));
        #end if

        if(afterFact == None):
          afterFact = childFact;
          continue;
        else:
          assert(len(childFact) == len(afterFact));
        #end if

        # the hard case: in order to be a consistent path, one child must have
        # the smallest vector across all obsYes entries
        newIsSmaller = False;
        oldIsSmaller = False;
        for (i, obsYesVector) in enumerate(childFact):
          thisNewSmaller = self.__isPrefix(obsYesVector, afterFact[i]);
          thisOldSmaller = self.__isPrefix(afterFact[i], obsYesVector);
          assert(thisNewSmaller or thisOldSmaller);

          # update which is the smaller vector (more obsYes entries eaten)
          if(thisNewSmaller and thisOldSmaller):
            # they are the same: always OK
            continue;
          elif(thisNewSmaller):
            if(oldIsSmaller):
              # KABOOM!
              return(False);
            #end if
            newIsSmaller = True;
          else:
            if(newIsSmaller):
              # KABOOM!
              return(False);
            #end if
            oldIsSmaller = True;
          #end if
        #end for
        assert(not newIsSmaller or not oldIsSmaller);
        if(newIsSmaller):
          afterFact = childFact;
        #end if
      #end for

      # generate the "base" after-fact (for starting at the crash)
      if(afterFact == None):
        assert(processing == realCrash);
        afterFact = [];
        for obsYesVector in self.__yesVectors:
          # NOTE: don't need to do a deep copy here, because we will copy and
          # update the vector later (when computing the before-fact.  Keep an
          # eye on this for future changes!
          afterFact += [list(obsYesVector)];
        #end for
      #end if

      # ---------------------------------------------------------------------
      # compute this node's "before-fact"
      # ---------------------------------------------------------------------
      beforeFact = [];

      # build the new before-fact
      for vector in afterFact:
        # create our own copy of the fact, remove any nodes from our SCC from
        # the end of the vector
        newVector = vector[:];
        while(newVector and newVector[-1] in G.node[processing]["members"]):
          newVector.pop();
        #end while
        beforeFact.append(newVector);
      #end for

      # TODO: if any nodes from this SCC still in any vectors, KABOOM!

      # update the before-fact
      assert(G.node[processing].get("beforeFact", None) == None);
      G.node[processing]["beforeFact"] = beforeFact;
    #end for

    # check the fact at the entry
    entryBeforeFact = G.node[realEntry].get("beforeFact", None);
    if(entryBeforeFact == None):
      return(False);
    assert(len(entryBeforeFact) == len(self.__yesVectors));
    for vector in entryBeforeFact:
      if(len(vector) > 0):
        return(False);
      #end if
    #end for
    return(True);
  #end: __entryCrashPath

  """
  __removeDeadNodes(): Remove all nodes that are either
                       (1) not forward-reachable from entry, or
                       (2) not backward-reachable from the crash site
  @param G the graph (may be either a standard graph or an SCC DAG)
  NOTE: G is updated in-place
  """
  def __removeDeadNodes(self, G):
    assert(self.__entryNode);
    assert(self.__crashNode);

    if(self.__entryNode in G and self.__crashNode in G):
      entryNode = self.__entryNode;
      crashNode = self.__crashNode;
    else:
      (entryNode, crashNode) = self.__getSCCEntryCrash(G);
    #end if

    fwdNodes = set([]);
    worklist = set([entryNode]);
    while(worklist):
      current = worklist.pop();
      fwdNodes.add(current);

      for (source, target) in G.out_edges_iter([current]):
        if(target not in fwdNodes):
          worklist.add(target);
      #end for
    #end while

    bwdNodes = set([]);
    worklist = set([crashNode]);
    while(worklist):
      current = worklist.pop();
      bwdNodes.add(current);

      for (source, target) in G.in_edges_iter([current]):
        if(source not in bwdNodes):
          worklist.add(source);
      #end for
    #end while

    oldNodes = set(G.nodes());
    newNodes = oldNodes & fwdNodes & bwdNodes;
    G.remove_nodes_from(oldNodes - newNodes);
  #end: __removeDeadNodes

  """
  __buildSCCGraph(): Build a new graph with SCCs from the input graph collapsed.
  NOTE: the created graph contains only SCCs backward-reachable from the crash
  node (which must be set before calling this function).
  @param G the graph
  @return the new SCC graph
  """
  def __buildSCCGraph(self, G):
    newGraph = condensation(G);
    self.__removeDeadNodes(newGraph);
    return(newGraph);
  #end: __buildSCCGraph

  """
  @override
  isSat(): Check if there is a path from entry to crash.
  @return whether or not any such path exists
  """
  def isSat(self):
    assert(self.__entryNode != None);
    assert(self.__crashNode != None);

    return(self.__entryCrashPath(self.__buildSCCGraph(self.__graph)));
  #end: isSat
  
  """
  @override
  encodeObsYes(): Encode the constraint for a yes-executed observation.
  @param possibleYes a set of possible matches to the true entry
                    (NOTE: currently only supports a singleton)
            => [{G.nodes}]
  """
  def encodeObsYes(self, possibleYes):
    thisEntry = [];
    for group in possibleYes:
      assert(len(group) == 1);
      n = next(iter(group));
      self.__allYes.add(n);
      thisEntry.append(n);
    #end for
    self.__yesVectors.add(tuple(thisEntry));
  #end: encodeObsYes
  
  """
  @override
  encodeCrash(): Encode the constraint for the crashing location.
  @param crashStack a representation of possible crashes in the stack trace,
                    ending in the final possible crashing nodes
            => [({G.nodes}, {G.nodes}), ..., ({G.nodes}, None)]
  """
  def encodeCrash(self, crashStack):
    assert(self.__crashNode is None);

    obsCrash = [];
    for (callNodes, entryNodes) in crashStack:
      obsCrash.append(callNodes);
      if(entryNodes):
        obsCrash.append(entryNodes);
    #end for
    self.encodeObsYes(obsCrash);

    assert(len(crashStack[-1]) == 2);
    crashNodes = crashStack[-1][0];
    assert(len(crashNodes) == 1);
    self.__crashNode = next(iter(crashNodes));
  #end: encodeCrash
  
  """
  @override
  encodeObsNo(): Encode the constraint for a not-executed observation.
  @param possibleNo a set of possible matches to the true entry
                    (NOTE: currently only supports a singleton)
            => {G.nodes}
  """
  def encodeObsNo(self, possibleNo):
    assert(len(possibleNo) == 1);
    # remove node from the graph
    n = next(iter(possibleNo));
    self.__graph.remove_node(n);
    self.__allNo.add(n);
    # TODO: remove all now-disconnected nodes in the graph?
    # it's probably better to just do this once, after all "no" observations
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
    defNo = self.__allNo.copy();
    maybe = set([]);

    # build the base SCC graph (which is re-used for each exeNo check)
    baseSCCGraph = self.__buildSCCGraph(self.__graph);
    
    total = len(self.__graph);
    soFar = 0;
    for n in self.__graph.nodes_iter(False):
      prevInYesVectors = (tuple([n]) in self.__yesVectors);
      self.__yesVectors.add(tuple([n]));
      possibleYes = self.__entryCrashPath(baseSCCGraph);
      if(not prevInYesVectors):
        self.__yesVectors.remove(tuple([n]));
      #end if

      if(n in [self.__entryNode, self.__crashNode]):
        possibleNo = False;
      else:
        # make a shallow copy (so we can remove a node without wrecking the
        # original)
        noTestG = self.__graph.subgraph(self.__graph.nodes());
        noTestG.remove_node(n);
        noTestSCCGraph = self.__buildSCCGraph(noTestG);
        possibleNo = self.__entryCrashPath(noTestSCCGraph);
      #end if
      
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
#end: class UtlExecutionSolver
