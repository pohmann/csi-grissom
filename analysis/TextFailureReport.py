from sys import stderr

from FailureReport import FailureReport

from csilibs.graphlibs import is_cfg_node

class TextFailureReport(FailureReport):
  __slots__ = "__graph";

  """
  __init__(): Parse each failure-data-string (crash, yes, no) into the failure
              report format.  Also verify that each node is in the graph.
  @param G the graph
  @param crashString a comma-separated list of crash nodes
                     TODO: make them more expressive
  @param obsYesString a semi-colon-separated list of obsYes entries
  @param obsNoString a semi-colon-separated list of obsNo entries
  NOTE: the format here is quite complex.  Semi-colons separate top-level vector
  entries; pipes separate second-level vector entries (for obsYes); commas
  separate ambiguitities (i.e., the exact node observed is not known).
  """
  def __init__(self, G, crashString, obsYesString, obsNoString):
    self.__graph = G;

    self._crashStack = [(self.__extractCommaNodes(crashString),None)] ;
    self._obsYes = self.__extractSemicolonNodes(obsYesString);
    self._obsNo = [];
    for no in self.__extractSemicolonNodes(obsNoString):
      if(len(no) != 1):
        print >> stderr, ("ERROR: invalid obsNo data");
        exit(1);
      #end if
      self._obsNo += [no[0]];
    #end for
  #end: __init__

  def __extractCommaNodes(self, nodeString):
    nodes = set([x.strip() for x in nodeString.split(",")]);
    nodes.discard("");

    # verify all provided nodes are in the graph
    for n in nodes:
      if(not is_cfg_node(self.__graph, n)):
        print >> stderr, ("ERROR: invalid comma node (" + n + ") provided");
        exit(1);
      #end if
    #end for

    return(nodes);
  #end: __extractCrashNodes

  def __extractBarNodes(self, nodeString):
    nodeSets = [];

    nodeLists = [x.strip() for x in nodeString.split("|")];
    while(nodeLists.count("") > 0):
      nodeLists.remove("");
    for aList in nodeLists:
      nodeSets += [self.__extractCommaNodes(aList)];
    #end for

    return(nodeSets);
  #end: __extractBarNodes

  def __extractSemicolonNodes(self, nodeString):
    nodeSets = [];

    # process each ;-separated entry
    stringSet = set([x.strip() for x in nodeString.split(";")]);
    stringSet.discard("");
    for aSet in stringSet:
      nodeSets += [self.__extractBarNodes(aSet)];
    #end for

    return(nodeSets);
  #end: __extractSemicolonNodes
#end: class TextFailureReport
