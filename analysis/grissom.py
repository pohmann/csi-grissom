#!/usr/bin/env python

from argparse import ArgumentParser
from os.path import expanduser
from sys import stdout, stderr, argv

from FsaExecutionSolver import FsaExecutionSolver
from UtlExecutionSolver import UtlExecutionSolver
from SvpaExecutionSolver import SvpaExecutionSolver
from PexpectSvpaExecutionSolver import PexpectSvpaExecutionSolver

from JSONFailureReport import JSONFailureReport
from TextFailureReport import TextFailureReport

from csilibs.clock import CSIClock
from csilibs.graphlibs import collapse_BB_nodes, collapsed_nodes_from_node, \
                              function_id, lines_from_node, read_graph, \
                              restrict_to_function

##########################################################
# Analysis Options
##########################################################
ANALYSIS_OPTIONS = {"FSA" : FsaExecutionSolver, \
                    "UTL" : UtlExecutionSolver, \
                    "SVPA" : SvpaExecutionSolver, \
                    "Pexpect" : PexpectSvpaExecutionSolver}
RESULT_STYLES = ["none", "compact", "full", "csiclipse", "standard"];
MARKER_FOR_RESULTS_START = "--- Begin results";


def nodeSortKey(n):
  key = [];
  for part in n.split(':'):
    try:
      key.append(abs(int(part)));
    except:
      key.append(part);
  return(tuple(key));
#end: nodeSortKey

def printResult(data, full=False, outStream=stdout):
  (defYes, defNo, maybe) = data;
  totalSize = len(defYes) + len(defNo) + len(maybe);
  defYesPercent = 100 * (1.0 * len(defYes)) / (1.0 * totalSize);
  defNoPercent = 100 * (1.0 * len(defNo)) / (1.0 * totalSize);
  maybePercent = 100 * (1.0 * len(maybe)) / (1.0 * totalSize);

  print >> outStream, (MARKER_FOR_RESULTS_START);
  print >> outStream, ("defYes (" + str(len(defYes)) + " " + \
                       str(defYesPercent) + "%) " + \
                       ("= " + str(sorted(defYes, key=nodeSortKey)) if full \
                                                                    else ""));
  print >> outStream, ("defNo (" + str(len(defNo)) + " " + \
                       str(defNoPercent) + "%) " + \
                       ("= " + str(sorted(defNo, key=nodeSortKey)) if full \
                                                                   else ""));
  print >> outStream, ("maybe (" + str(len(maybe)) + " " + \
                       str(maybePercent) + "%) " + \
                       ("= " + str(sorted(maybe, key=nodeSortKey)) if full \
                                                                   else ""));
#end: printResult

def lineSetToString(lineSet):
  return ",".join([str(x) for x in sorted(list(lineSet)) if x not in ["0", 0]]);
#end: lineSetToString

def printLinesResult(data, G, csiclipse=False, intraprocedural=False, outStream=stdout):
  (defYes, defNo, maybe) = data;
  fileToResults = {};  # {file : (yesLines, noLines, maybeLines)}

  # create a mapping from function ids to the file that contains them
  funcToFileMapping = {};  # {funcId : (file, procedureName)}
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "") == "entry"):
      thisEntryFuncId = function_id(n);
      if(thisEntryFuncId in funcToFileMapping):
        print >> stderr, ("ERROR: duplicate function entry in graph");
        exit(1);
      #end if

      thisEntryFile = attr.get("file", None);
      thisEntryProcedure = attr.get("procedure", None);
      funcToFileMapping[thisEntryFuncId] = (thisEntryFile, thisEntryProcedure);
      if(not thisEntryFile):
        procedureToPrint = thisEntryProcedure if thisEntryProcedure \
                                              else str(thisEntryFuncId);
        print >> stderr, ("WARNING: missing file information in CFG for " + \
                          "function '" + procedureToPrint + "'");
      #end if
    #end if
  #end for

  # verify that intraprocedural graphs have only one function
  if(intraprocedural and len(funcToFileMapping) != 1):
    print >> stderr, ("ERROR: wrong number of functions (" + \
                      str(len(funcToFileMapping)) + ") in intraprocedural " + \
                      "graph");
    exit(1);
  #end if

  # for each node in yes, no, and maybe...add its lines to the results map
  allDataNodes = set([]);
  allDataNodes.update(defYes);
  allDataNodes.update(defNo);
  allDataNodes.update(maybe);
  for n in allDataNodes:
    nodeFile = funcToFileMapping.get(function_id(n), (None, None))[0];
    if(nodeFile != None):
      fileToResults[nodeFile] = fileToResults.get(nodeFile, \
                                                  (set([]), set([]), set([])));
      thisNodeLines = lines_from_node(G, n);
      if(not thisNodeLines):
        continue;

      if(n in defYes):
        fileToResults[nodeFile][0].update(thisNodeLines);
      if(n in defNo):
        fileToResults[nodeFile][1].update(thisNodeLines);
      if(n in maybe):
        fileToResults[nodeFile][2].update(thisNodeLines);
    #end if
  #end for

  fileToResults.pop(None, None);
  if(intraprocedural and len(fileToResults) != 1):
    print >> stderr, ("ERROR: multiple functions in intraprocedural graph!");
    exit(1);
  #end if

  print(MARKER_FOR_RESULTS_START);
  for (fileName, fileData) in fileToResults.iteritems():
    writeThisFile = "";

    if(csiclipse):
      funcName = "unused";
      if(intraprocedural):
        funcName = funcToFileMapping[next(iter(funcToFileMapping))][1];
        if(funcName == None):
          funcName = "???";
      #end if
      writeThisFile += funcName;

      writeThisFile += ";" + fileName;

      writeThisFile += ";" + ("local" if intraprocedural else "global");

      # tricky: this iterates over "yes", then "no", then "maybe" for the file
      for thisSet in fileData:
        writeThisFile += ";" + lineSetToString(thisSet);
      #end for
    else:
      writeThisFile += fileName + "\n==========\n";
      (yesLines, noLines, maybeLines) = fileData;
      writeThisFile += "Yes: " + lineSetToString(yesLines) + "\n";
      writeThisFile += "No: " + lineSetToString(noLines) + "\n";
      writeThisFile += "Maybe: " + lineSetToString(maybeLines) + "\n";
    #end if

    print(writeThisFile);
  #end for
#end: printLinesResult

# Add all collapsed nodes from nodes in nodeSet into nodeSet.
def addCollapsedToSet(nodeSet, G):
  for n in nodeSet.copy():
    nodeSet.update(collapsed_nodes_from_node(G, n));
  return(nodeSet);
#end: addCollapsedToSet

def getResult(solver, G, crashStack, obsYes, obsNo):
  print("Adding crash constraint...");
  solver.encodeCrash(crashStack);
  print("Adding obsNo constraints...");
  i = 0;
  for obs in obsNo:
    i+=1;
    solver.encodeObsNo(obs);
  #end for
  print("Adding obsYes constraints...");
  i = 0;
  for obs in obsYes:
    i+=1;
    print(str(i) + "/" + str(len(obsYes)));
    solver.encodeObsYes(obs);
  #end for
  assert(solver.isSat());
  
  print("Getting defYes/No information...");
  (defYes, defNo, maybe) = solver.findKnownExecution();
  defYes = addCollapsedToSet(defYes, G);
  defNo = addCollapsedToSet(defNo, G);
  maybe = addCollapsedToSet(maybe, G);
  return(defYes, defNo, maybe);
#end: getResult

# Compare results, return True if they compare as expected.  If "eq" is true,
# they should be the same.  Otherwise, we expect firstResult to be "better" than
# secondResult (i.e., have less "maybe").
def compareResults(firstResult, secondResult, eq=True):
  if(eq):
    return(firstResult == secondResult);
  else:
    (firstYes, firstNo, firstMaybe) = firstResult;
    (secondYes, secondNo, secondMaybe) = secondResult;
    return(firstYes.issuperset(secondYes) and \
           firstNo.issuperset(secondNo) and \
           firstMaybe.issubset(secondMaybe));
  #end if
  assert(False);
#end: compareResults

def getFuncIdForCrashes(G, crashNodes):
  funcId = None;
  for n in crashNodes:
    newFuncId = function_id(n);
    if(funcId == None):
      funcId = newFuncId;
    elif(newFuncId != funcId):
      print >> stderr, ("ERROR: crashes in multiple functions!");
      exit(1);
    #end if
  #end for
  
  if(not funcId):
    print >> stderr, ("ERROR: no function id for crashes!");
    exit(1);
  #end if
  
  return(funcId);
#end: getFuncIdForCrashes

# An unfortunate necessity: the crashing location might be a bit ambiguous, so
# we'll just make up a new final statement.
def cleanStackAndGraph(G, crashStack):
  assert(len(crashStack) > 0 and len(crashStack[-1]) == 2);
  finalLocations = set(crashStack[-1][0]);

  finalFnId = getFuncIdForCrashes(G, finalLocations);
  newFinalNodeId = 1000;
  while(("n:" + str(finalFnId) + ":" + str(newFinalNodeId)) in G):
    newFinalNodeId += 1;
  newFinalNode = "n:" + str(finalFnId) + ":" + str(newFinalNodeId);

  for loc in finalLocations:
    G.add_edge(loc, newFinalNode);
  #end for

  G.node[newFinalNode]["kind"] = "crash";
  crashStack[-1] = (set([newFinalNode]), crashStack[-1][1]);
  return(crashStack);
#end: cleanStackAndGraph

def parseArguments(argList):
  parser = ArgumentParser(prog="csi-grissom",
                          description="Determine (exeYes, exeNo, maybe) for " +\
                                      "the FSA and SAT formulations.  " +\
                                      "Verify that they match.");
  parser.add_argument("graph_filename", help="Path to graphml file");
  parser.add_argument("-json", "--json", action="store", dest="json",
                      help="JSON input file.  " + \
                           "Provide JSON input file for crash+yes+no data " + \
                           "(rather than specifying each on the command " + \
                            "line).  Note that this will completely " + \
                            "override options for -c, -y, and -n.");
  parser.add_argument("-c", "--crash", action="store", dest="crash_nodes",
                      default=None,
                      help="String of possible crash nodes.  " + \
                           "Ambiguity in entries is separated by ,s.\n" + \
                           "This option is deprecated.  Use -json instead.");
  parser.add_argument("-y", "--yes", action="store", dest="yes", default="",
                      help="obsYes observations.  " + \
                           "Vectors are separated by ;s.  " + \
                           "Vector entries are separated by |s.  " + \
                           "Ambiguity in entries is separated by ,s.\n" + \
                           "This option is deprecated.  Use -json instead.");
  parser.add_argument("-n", "--no", action="store", dest="no", default="",
                      help="obsNo observations.  " + \
                           "Entries are separated by ;s.  " + \
                           "Ambiguity in entries is separated by ,s.\n" + \
                           "This option is deprecated.  Use -json instead.");
  parser.add_argument("-stackonly", "--stackonly", action="store_true",
                      dest="stackonly", default=False,
                      help="Ignore obsYes and obsNo.  Only encode the stack.");
  parser.add_argument("-intra", action="store_true", dest="intraprocedural",
                      default=False, help="Perform intraprocedural analysis");
  parser.add_argument("-compare", "--comparator", action="store",
                      dest="comparator",
                      choices=["eq", "gt", "lt"], default="eq",
                      help="Method of comparing first and second analysis.  " +\
                           "You can expect them to be equal (eq), or the " +\
                           "first to be better (gt) or worse (lt).");
  parser.add_argument("-collapse", "--collapse", action="store",
                      dest="collapse",
                      choices=["first", "second", "both", "none"],
                      default="both",
                      help="Indicate which solver should collapse basic " +\
                           "blocks to speed up analysis time.  This option " +\
                           "should only be changed for debugging/testing.");
  parser.add_argument("-result-style", "--result-style", action="store",
                      dest="result_style",
                      choices=RESULT_STYLES,
                      default="compact",
                      help="Indicate how results should be written out " +\
                           "after analysis completes.");
  parser.add_argument("-first", "--first", action="store", dest="first",
                      choices=ANALYSIS_OPTIONS.keys(), default="UTL",
                      help="The first analysis version to run.");
  parser.add_argument("-second", "--second", action="store", dest="second",
                      choices=ANALYSIS_OPTIONS.keys() + ["None"],
                      default="None",
                      help="The second analysis version to run.  Use " + \
                           "\"None\" to run only one analysis and not " + 
                           "compare.");
  return(parser.parse_args(argList));
#end: parseArguments

"""
solve(): This is the main solver function (which should be called directly, if
used from an import).  It calls all the other functions for a while and then
exits.
"""
def solve(argList):
  args = parseArguments(argList);
  
  clock = CSIClock();
  print("Reading graph...");
  G = read_graph(args.graph_filename, cfgOnly=True);
  
  clock.takeSplit();
  print("Reading failure data...");
  failureData = None;
  if(args.json):
    failureData = JSONFailureReport(G, expanduser(args.json));
  elif(args.crash_nodes):
    failureData = TextFailureReport(G, args.crash_nodes, args.yes, args.no);
  else:
    print >> stderr, ("ERROR: you must specify either JSON or command-line " + \
                      "input data.  Use --help for more information.");
    exit(1);
  #end if

  if(args.stackonly):
    print("Ignoring obsYes and obsNo data...");
    failureData.clearObsYesAndNo();
  #end if

  if(args.intraprocedural):
    print("Restricting graph to crash function...");
    crashStack = failureData.getCrashStack();
    if(len(crashStack) < 1 or len(crashStack[-1]) != 2):
      print >> stderr, ("ERROR: missing/invalid crash location");
      exit(1);
    #end if
    crashNodes = crashStack[-1][0];

    funcId = getFuncIdForCrashes(G, crashNodes);
    G = restrict_to_function(G, funcId);
  #end if

  # get (and fix up) failure data
  # NOTE: this could also modify the graph (G) as necessary for matching!
  crashStack = failureData.getCrashStack();
  cleanStackAndGraph(G, crashStack);
  obsYes = failureData.getObsYes();
  obsNo = failureData.getObsNo();

  # collapse as much as possible into basic blocks
  uncollapsedG = G;
  firstG = G;
  secondG = G;
  if(args.collapse != "none"):
    print("Collapsing basic blocks (excluding failure report nodes)...");
    if(args.result_style in ("csiclipse", "standard")):
      # copy the old graph, but only if we'll actually use it later
      uncollapsedG = G.copy();
    #end if
  if(args.collapse == "both"):
    collapse_BB_nodes(G, exclude=failureData.getAllNodesInFailureReport());
  elif(args.collapse == "first"):
    firstG = G.copy();
    collapse_BB_nodes(firstG, exclude=failureData.getAllNodesInFailureReport());
  elif(args.collapse == "second"):
    secondG = G.copy();
    collapse_BB_nodes(secondG, exclude=failureData.getAllNodesInFailureReport());
  #end if


  clock.takeSplit();
  print("Starting " + args.first + " version...");
  print("Exporting graph as constraints...");
  firstSolver = ANALYSIS_OPTIONS[args.first](firstG);
  firstResult = getResult(firstSolver, firstG, crashStack, obsYes, obsNo);
  
  if(args.second != "None"):
    clock.takeSplit();
    print("Starting " + args.second + " version...");
    print("Exporting graph as constraints...");
    secondSolver = ANALYSIS_OPTIONS[args.second](secondG);
    secondResult = getResult(secondSolver, secondG, crashStack, obsYes, obsNo);
  #end if
  
  clock.takeSplit();
  if(args.second != "None" and firstResult != secondResult):
    if(args.comparator == "eq"):
      compareOK = compareResults(firstResult, secondResult, True);
    elif(args.comparator == "gt"):
      compareOK = compareResults(firstResult, secondResult, False);
    else:
      compareOK = compareResults(secondResult, firstResult, False);
    #end if

    if(not compareOK):
      print >> stderr, ("ERROR: first and second results don't match!");
      print >> stderr, (args.first + ":");
      printResult(firstResult, True, stderr);
      print >> stderr, (args.second + ":");
      printResult(secondResult, True, stderr);
      exit(1);
    #end if
  #end if
  
  if(not args.result_style or args.result_style == "none"):
    pass;
  elif(args.result_style in ("compact", "full")):
    printResult(firstResult, (args.result_style == "full"));
  elif(args.result_style in ("csiclipse", "standard")):
    printLinesResult(firstResult, uncollapsedG, \
                     (args.result_style == "csiclipse"));
  else:
    print >> stderr, ("ERROR: invalid result style specified: '" + \
                      args.result_style + "'");
    exit(1);
  #end if
#end: solve

def main():
  solve(argv[1:]);
#end: main

if __name__ == '__main__':
  main()
