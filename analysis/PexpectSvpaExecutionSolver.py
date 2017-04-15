#!/s/python-2.7.1/bin/python

from pexpect import spawn, EOF
from sys import stderr, stdout

from ExecutionSolver import ExecutionSolver
from utils import findEntryForNode, findGraphEntry
from csilibs.graphlibs import is_cfg_node

import os

EXPECTED_PROMPT = ">> ";
ENTRY_PREFIX="entry_"
RETURN_PREFIX="ret_"

class PexpectSvpaExecutionSolver(ExecutionSolver):
  __slots__ = "__server", "__graphNodes";

  """
  __findEntry(): Search through the graph for its "entry" node.  If the graph is
  intraprocedural, this is the entry of that function.  If the graph is
  interprocedural, this is the entry of "main"
  @param G the graph
  @return (entry, isInterprocedural)
  """
  def __findEntry(self, G):
    entries = set([]);
    for (n, attr) in G.nodes(True):
      if(attr.get("kind", "") == "entry"):
        entries.add((n, attr.get("procedure", "")));
      #end if
    #end for

    # if intraprocedural, return the lone entry node
    if(len(entries) == 1):
      return(entries.pop()[0], False);

    # otherwise, return main's entry
    mainEntry = None;
    for (n, proc) in entries:
      if(proc == "main"):
        if(mainEntry != None):
          print >> stderr, ("ERROR: multiple \"main\" functions!");
          exit(1);
        #end if
        mainEntry = n;
      #end if
    #end for
    if(mainEntry == None):
      print >> stderr, ("ERROR: no \"main\" entry in interprocedural graph!");
      exit(1);
    #end if
    return(mainEntry, True);
  #end: __findEntry

  """
  __expect(): Wrapper for pexpect's expect() function.  Automatically adds EOF
              as a possible expectation, and prints the (optional) error message
              if it encounters EOF.
  @param values a list of expected values to pass to expect()
  @param errorMessage the message to print before termination of EOF is found
  @return the index from "values" that is first matched
  """
  def __expect(self, values, errorMessage):
    if(not self.__server.isalive()):
      print >> stderr, ("ERROR: server is already dead: " + errorMessage);
      exit(1);
    #end if

    result = self.__server.expect(values + [EOF]);
    if(result == len(values) or result < 0):
      print >> stderr, ("ERROR: EOF reached while checking SVPA output:" + \
                        errorMessage);
      print >> stderr, ("Full data read:");
      print >> stderr, self.__server.before;
      print >> stderr, self.__server.after;
      exit(1);
    #end if

    return(result);
  #end: __expect

  """
  @override
  __init__(): Start up a process for the Java SVPA server.  Then, process the
              graph, encoding its structure as appropriate commands to the
              server.
  @param G the graph
  """
  def __init__(self, G):
    # maxMemory is in MegaBytes.
    # We need to set this here (if used in experiments), because OS-level
    # rlimit settings mess up the JVM memory allocator
    try:
      maxMemory = int(os.environ.get("MAX_MEMORY", 32768));
      maxMemory = max(maxMemory, 1024);
    except:
      maxMemory = 32768;

    self.__server = spawn("java", \
                          args=["-Xmx" + str(int(maxMemory * 0.65625)) + "m", \
                                "-jar", \
                                "../SVPAServer/SVPAServer.jar"], \
                          timeout=None);
    self.__server.setecho(False);
    self.__graphNodes = set([]);

    self.__expect([EXPECTED_PROMPT], "server could not be started");

    # special extraction/encoding for entry node
    (entryNode, isInterprocedural) = findGraphEntry(G);
    toSend = "cfg\n";
    toSend += "e," + entryNode + "\n";

    # then, encode all edges in the CFG
    for (n, attr) in G.nodes(True):
      # don't export SDG-only nodes
      if(not is_cfg_node(G, n)):
        continue;
      self.__graphNodes.add(n);

      if(isInterprocedural and attr.get("kind", "") == "call-site"):
        foundOne = False;
        for (source, target, eAttr) in G.out_edges_iter([n], data=True):
          if(eAttr.get("type", "flow") == "control" and \
             eAttr.get("scope", "") == "interprocedural"):
            # add special automata state for the "entry site":
            # allows constraints to ignore call edges for matching
            entrySite = ENTRY_PREFIX+target;
            toSend += "c," + n + "," + entrySite + "\n";
            toSend += "i," + entrySite + "," + target + "\n";
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
            toSend += "i," + n + "," + target + "\n";
          #end if
        #end for
      elif(isInterprocedural and attr.get("kind", "") == "exit"):
        entryForExit = findEntryForNode(G, n);
        for (source, target, eAttr) in G.in_edges_iter([entryForExit], data=True):
          if(eAttr.get("type", "flow") == "control" and \
             eAttr.get("scope", "") == "interprocedural"):
            # edge from exit -> all successors of the call to this function
            for (call, callTarget, eAttr) in G.out_edges_iter([source], data=True):
              if(eAttr.get("type", "flow") == "flow" and \
                 eAttr.get("scope", "") != "interprocedural" and \
                 G.node[callTarget].get("kind", "") != "crash"):
                # add special automata state for the "return site":
                # allows constraints to ignore return edges for matching
                retSite = RETURN_PREFIX+call;
                toSend += "r," + n + "," + retSite + "," + call + "\n";
                toSend += "i," + retSite + "," + callTarget + "\n";
              #end if
            #end for
          #end if
        #end for
      else:
        for (source, target, eAttr) in G.out_edges_iter([n], data=True):
          if(eAttr.get("type", "flow") == "flow" and \
             eAttr.get("scope", "") != "interprocedural"):
            toSend += "i," + n + "," + target + "\n";
          #end if
        #end for
      #end if
    #end for

    toSend += "END";

    self.__server.sendline(toSend);

    # assert that the server didn't fail, and that the encoded CFG has
    # legal executions
    self.__expect([EXPECTED_PROMPT], "failure on generated CFG input");
    assert(self.isSat());
  #end: __init__

  """
  __del__(): We do explicit clean-up of the opened stream to the Java-based
             SVPA server.  While using __del__ is frowned-upon in Python, cyclic
             references shouldn't be a problem, so we should be OK.
  """
  def __del__(self):
    self.__server.sendeof();
    self.__server.terminate(force=True);
  #end: __del__

  """
  checkEmptyResult(): Parse the output for an emptiness query to the SVPA
                      server.  Should be called after sending the appropriate
                      query.
  @return whether or not the SVPA's language is empty
  """
  def checkEmptyResult(self):
    result = self.__expect(["true", "false"],
                           "unexpected result for emptiness query");
    assert(0 <= result <= 1);

    self.__expect([EXPECTED_PROMPT], "no prompt after emptiness query");
    return(result == 0);
  #end: checkEmptyResult

  """
  @override
  isSat(): Check if the language recognized by the SVPA is empty.
  @return whether or not the language accepted by the SVPA is empty
  """
  def isSat(self):
    self.__server.sendline("empty");
    return(not self.checkEmptyResult());
  #end: isSat

  """
  genObsYesSVPA: Generate the appropriate commands to encode an obsYes SVPA.
  @param possibleYes a sequence of sets of possible matches to the true entry
                    (usually a singleton)
            => [{G.nodes}]
  @return a string representing the commands to send to the SVPA server
  """
  def genObsYesSVPA(self, possibleYes):
    toSend = "i,0\n";

    # at least one each of the possibleYes executed in order
    currentState = 0;
    for group in possibleYes:
      # verify that all nodes are in the graph
      for n in group:
        if(n not in self.__graphNodes):
          print >> stderr, ("ERROR: invalid YES observation node: " + str(n));
          exit(1);
        #end if
      #end for

      # add outgoing edges for this entry=node
      toSend += "t,i," + str(currentState) + "," + str(currentState) + ",*\n";
      toSend += "t,c," + str(currentState) + "," + str(currentState) + ",*\n";
      toSend += "t,r," + str(currentState) + "," + str(currentState) + ",*\n";
      for n in group:
        # only need internal edges because we add special nodes for return
        # targets and entry nodes in the graphml
        toSend += "t,i," + str(currentState) + "," + \
                  str(currentState+1) + "," + str(n) + "\n";
      #end for
      currentState += 1;
    #end for

    # no constraints after the final obsYes entry
    toSend += "t,i," + str(currentState) + "," + str(currentState) + ",*\n";
    toSend += "t,c," + str(currentState) + "," + str(currentState) + ",*\n";
    toSend += "t,r," + str(currentState) + "," + str(currentState) + ",*\n";
    toSend += "f," + str(currentState) + "\n";

    return(toSend);
  #end: genObsYesSVPA

  """
  @override
  encodeObsYes(): Encode the constraint for a yes-executed observation.
  @param possibleYes a sequence of sets of possible matches to the true entry
                    (usually a singleton)
            => [{G.nodes}]
  """
  def encodeObsYes(self, possibleYes):
    self.__server.sendline("constraint\n" + \
                           self.genObsYesSVPA(possibleYes) + \
                           "END");

    self.__expect([EXPECTED_PROMPT], "error encoding obsYes entry");
  #end: encodeObsYes

  """
  @override
  encodeCrash(): Encode the constraint for the crashing location.
  @param crashStack a representation of possible crashes in the stack trace,
                    ending in the final possible crashing nodes
            => [({G.nodes}, {G.nodes}), ..., ({G.nodes}, None)]
  """
  def encodeCrash(self, crashStack):
    toSend = "stack\n";

    for (callNodes, entryNodes) in crashStack:
      if(len(callNodes) != 1):
        print >> stderr, ("ERROR: SVPA solver can currently only handle " + \
                          "unambiguous crash data");
        exit(1);
      #end if
      toSend += str(list(callNodes)[0]);

      if(entryNodes != None):
        if(len(entryNodes) != 1):
          print >> stderr, ("ERROR: SVPA solver can currently only handle " + \
                            "unambiguous crash data");
          exit(1);
        #end if
        toSend += "," + str(list(entryNodes)[0]);
      #end if

      toSend += "\n";
    #end for

    toSend += "END";
    self.__server.sendline(toSend);

    # assert that the encoded CFG still has legal executions (i.e. the crash
    # is reachable)
    self.__expect([EXPECTED_PROMPT], "error encoding crash stack data");
    assert(self.isSat());
  #end: encodeCrash

  """
  genObsNoSVPA(): Generate the appropriate commands to encode an obsNo SVPA.
  @param noNode the false entry (here, a singleton)
            => G.node
  @return a string representing the commands to send to the SVPA server
  """
  def genObsNoSVPA(self, noNode):
    return("obsNo," + str(noNode) + "\n");
  #end: genObsNoSVPA

  """
  @override
  encodeObsNo(): Encode the constraint for a not-executed observation.
  @param possibleNo a set of possible matches to the false entry
                    (NOTE: currently only supports a singleton)
            => {G.nodes}
  """
  def encodeObsNo(self, possibleNo):
    # we currently only handle singleton "no" observations
    if(len(possibleNo) != 1):
      print >> stderr, ("ERROR: SVPA solver can currently only handle " + \
                        "unambiguous FALSE observations");
      exit(1);
    #end if
    obsNo = list(possibleNo)[0];

    if(obsNo not in self.__graphNodes):
      print >> stderr, ("ERROR: invalid obsNo entry (not in graph)");
      exit(1);
    #end if

    self.__server.sendline("constraint\n" + \
                           self.genObsNoSVPA(obsNo) + \
                           "END");

    self.__expect([EXPECTED_PROMPT], "error encoding obsNo entry");
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

    nodeList = list(self.__graphNodes);

    # send all queries at once (saves immensely on communication time)
    toSend = "";
    for n in nodeList:
      toSend += "probe empty\n";
      toSend += self.genObsYesSVPA([[n]]);
      toSend += "END\n";
      toSend += "probe empty\n";
      toSend += self.genObsNoSVPA(n);
      toSend += "END\n";
    #end for
    self.__server.send(toSend);

    total = len(nodeList);
    soFar = 0;
    for n in nodeList:
      possibleYes = not self.checkEmptyResult();
      possibleNo = not self.checkEmptyResult();

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
  printWitness(): Print an accepted execution from the current SVPA
  """
  def printWitness(self):
    self.__server.sendline("witness");

    self.__expect([EXPECTED_PROMPT], "no prompt after witness query");
    print self.__server.before;
  #end: printWitness
#end: class PexpectSvpaExecutionSolver
