from sys import stderr
import json
from collections import Sequence

from FailureReport import FailureReport

"""
_isString(): Check if the provided variable is a string.
@param var the variable to check
@return true if "var" is some type of string; false otherwise
"""
def _isString(var):
  return(isinstance(var, (str, unicode)));
#end: _isString

"""
_isSequence(): Check if the provided variable is a list (or other
               appropriate sequential type).
@param var the variable to check
@return true if "var" is a sequence; false otherwise
"""
def _isSequence(var):
  return(isinstance(var, Sequence) and \
         not _isString(var));
#end: _isSequence

"""
_isDict(): Check if the provided variable is a dictionary.
@param var the variable to check
@return true if "var" is a dictionary; false otherwise
"""
def _isDict(var):
  return(isinstance(var, dict));
#end: _isDict

"""
_isBool(): Check if the provided variable is a boolean.
@param var the variable to check
@return true if "var" is a boolean; false otherwise
"""
def _isBool(var):
  return(isinstance(var, bool));
#end: _isBool

class JSONFailureReport(FailureReport):
  __slots__ = "__graph";

  """
  __init__(): Read a JSON file as input, and parse it into the failure report
              format.
  @param G the graph
  @param file the JSON file containing the failure report
  """
  def __init__(self, G, file):
    self.__graph = G;

    with open(file, 'r') as openFile:
      data = json.load(openFile)
    #end with

    if("crash" in data):
      self._crashStack = self.__extractCrashStack(data.get("stack", None), \
                                                  data.get("crash", None));
    elif("crashstack" in data):
      self._crashStack = self.__extractCrashStack(data.get("crashstack", None));
    else:
      print >> stderr, ("ERROR: missing crash stack data in JSON failure " + \
                        "report");
      exit(1);
    #end if
    self._obsYes = self.__extractObsYes(data.get("obsYes", None));
    self._obsNo = self.__extractObsNo(data.get("obsNo", None));
  #end: __init__

  """
  __dataToSet(): Turn the sequence in parameter "data" into a set of nodes,
  validating them along the way.
  @param data the data to convert
  @param nodeType the string name of the type of data (e.g., "call" or "entry")
  @return data converted to a set([string])
  """
  @staticmethod
  def __dataToSet(data, nodeType):
    nodes = set([]);
    for ambEntry in data:
      if(not _isString(ambEntry)):
        print >> stderr, ("ERROR: invalid " + nodeType + \
                          " node in JSON failure report");
        exit(1);
      #end if
      nodes.add(ambEntry);
    #end for
    return(nodes);
  #end: __dataToSet

  """
  __isValidStackData(): Check if the provided data is of an appropriate format
  to indicate a list of nodes from the graph.
  @param data the data to check
  @return true if the data is a valid sequence; false otherwise
  """
  @staticmethod
  def __isValidStackData(data):
    return(data != None and _isSequence(data));
  #end: __isValidStackData

  """
  __processStackFrame(): Given a stack frame, extract out the pair of possible
  crash points in the frame's function, and entry nodes for the next frame in
  the stack.  Naturally, crashing (top-of-stack) frames will not have a next
  function.
  @param frame the frame to process
  @return a pair of the crashing nodes in this function and next frame's entries
     => (callOrCrashNodes, entryNodes)
  NOTE: for the final crashing stack frame, entryNodes will be None
  """
  def __processStackFrame(self, frame):
    if(not _isDict(frame)):
      print >> stderr, ("ERROR: invalid stack frame in JSON.  Must be a " + \
                        "JSON object");
      exit(1);
    #end if

    entryData = frame.get("entry", None);
    callData = frame.get("call", None);
    crashData = frame.get("crash", None);

    validEntry = JSONFailureReport.__isValidStackData(entryData);
    validCall = JSONFailureReport.__isValidStackData(callData);
    validCrash = JSONFailureReport.__isValidStackData(crashData);

    if(validEntry and validCall and validCrash):
      print >> stderr, ("ERROR: frame is both internal and final crash frame");
      exit(1);
    elif(validEntry and validCall):
      return((JSONFailureReport.__dataToSet(callData, "call"), \
              JSONFailureReport.__dataToSet(entryData, "entry")));
    elif(validCrash):
      return((JSONFailureReport.__dataToSet(crashData, "crash"), None));
    else:
      print >> stderr, ("ERROR: frame missing/invalid entry, call, and/or " + \
                        "crash information");
      exit(1);
    #end if
  #end: __processStackFrame

  """
  __extractCrashStack(): Extract data in appropriate format for the "crash"
                         observation (along with associated stack trace) from
                         JSON data.  Validate the data along the way.
  @param stackTrace the JSON list object for the crashing stack trace.  Each
                    entry consists of a callsite and a called entry node in the
                    old format.  In the new format, the final entry should have
                    a list of possible crash points.
  @param crashSites If provided (only for the old format!), the JSON list object
                    associated with the crash data (a list because of possible
                    ambiguity)
  @return the crashing stack, as a list of pairs of sets representing in-stack
          possible crash locations
  """
  def __extractCrashStack(self, stackTrace, crashSites=None):
    # stack trace must be a list, unless we are processing an old-style JSON
    # report and crashSites is provided
    if(stackTrace != None and not _isSequence(stackTrace)):
      print >> stderr, ("ERROR: invalid stack trace in JSON.  " + \
                        "Must be an array of objects with entries and calls.");
      exit(1);
    #end if

    # embed crashSites into the stackTrace if using an old-style JSON report
    if(crashSites is not None):
      if(not _isSequence(crashSites)):
        print >> stderr, ("ERROR: invalid crash site list in JSON.  " + \
                          "Must be an array");
        exit(1);
      elif(len(crashSites) < 1):
        print >> stderr, ("ERROR: invalid crash data in JSON failure report");
        exit(1);
      #end if

      crashNodes = set([]);
      for ambCrash in crashSites:
        if(not _isString(ambCrash)):
          print >> stderr, ("ERROR: invalid crash node in JSON failure report");
          exit(1);
        #end if
        crashNodes.add(ambCrash);
      #end for
      
      if(stackTrace == None):
        stackTrace = [];
      stackTrace.append({"crash" : list(crashNodes)});
    #end if

    if(stackTrace == None):
      print >> stderr, ("ERROR: missing stack trace in JSON falure report");
      exit(1);
    #end if
    assert(len(stackTrace) > 0);


    stackData = [];
    for (i, frame) in enumerate(stackTrace):
      (callNodes, entryNodes) = self.__processStackFrame(frame);
      if(callNodes == None):
        print >> stderr, ("ERROR: missing call/crash nodes in frame");
        exit(1);
      elif(i != len(stackTrace)-1 and entryNodes == None):
        print >> stderr, ("ERROR: missing entry nodes for internal stack " + \
                          "frame");
        exit(1);
      elif(i == len(stackTrace)-1 and entryNodes != None):
        print >> stderr, ("ERROR: invalid crash frame contains entry nodes " + \
                          "for unexpected next stack frame");
        exit(1);
      #end if
      stackData.append((callNodes, entryNodes));
    #end for

    return(stackData);
  #end: __extractCrashStack

  """
  __extractObsYes(): Extract data in appropriate format for "obsYes"
                     observations from JSON data.  Validate the data
                     along the way.
  @param obsYesEntries the JSON list object associated with the obsYes data
  @return the set of obsYes entries
  """
  def __extractObsYes(self, obsYesEntries):
    if(not obsYesEntries):
      return([]);

    result = set([]);

    if(not _isSequence(obsYesEntries)):
      print >> stderr, ("ERROR: invalid obsYes array in JSON");
      exit(1);
    #end if

    for trace in obsYesEntries:
      if(not _isDict(trace)):
        print >> stderr, ("ERROR: each obsYes entry in JSON must be an " + \
                          "object {...}");
        exit(1);

      reliable = trace.get("reliable", None);
      if(reliable == None or not _isBool(reliable)):
        print >> stderr, ("ERROR: must specify reliability of obsYes vector " +\
                          " in JSON");
        exit(1);
      elif(reliable):
        print >> stderr, ("ERROR: can't currently handle reliable traces");
        exit(1);
      #end if

      entries = trace.get("entries", None);
      if(not entries or not _isSequence(entries) or len(entries) < 1):
        print >> stderr, ("ERROR: invalid or missing entries for obsYes " + \
                          "vector in JSON");
        exit(1);
      #end if

      vector = [];
      for entry in entries:
        if(not _isSequence(entry)):
          print >> stderr, ("ERROR: invalid obsYes vector entry in JSON.  " + \
                            "Must be an array");
          exit(1);
        elif(len(entry) < 1):
          print >> stderr, ("ERROR: empty obsYes data for a vector in " + \
                            "JSON failure report");
          exit(1);
        #end if

        nodes = set([]);
        for ambYes in entry:
          if(not _isString(ambYes)):
            print >> stderr, ("ERROR: invalid obsYes node in JSON " + \
                              "failure report");
            exit(1);
          #end if
          nodes.add(ambYes);
        #end for

        vector += [tuple(nodes)];
      #end for

      result.add(tuple(vector));
    #end for

    return(result);
  #end: __extractObsYes

  """
  __extractObsNo(): Extract data in appropriate format for "obsNo" observations
                    from JSON data.  Validate the data along the way.
  @param obsNoEntries the JSON list object associated with the obsNo data
  @return the set of obsNo entries
  """
  def __extractObsNo(self, obsNoEntries):
    if(not obsNoEntries):
      return([]);

    result = set([]);

    if(not _isSequence(obsNoEntries)):
      print >> stderr, ("ERROR: invalid obsNo array in JSON");
      exit(1);
    #end if

    for entry in obsNoEntries:
      if(not _isSequence(entry)):
        print >> stderr, ("ERROR: invalid obsNo entry in JSON.  " + \
                          "Must be an array");
        exit(1);
      elif(len(entry) < 1):
        print >> stderr, ("ERROR: invalid obsNo data in JSON failure report");
        exit(1);
      #end if

      nodes = set([]);
      for ambNo in entry:
        if(not _isString(ambNo)):
          print >> stderr, ("ERROR: invalid obsNo node in JSON failure report");
          exit(1);
        #end if
        nodes.add(ambNo);
      #end for

      result.add(tuple(nodes));
    #end for

    return(result);
  #end: __extractObsNo
#end: class JSONFailureReport
