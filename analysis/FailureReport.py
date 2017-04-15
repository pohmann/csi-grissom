class FailureReport:
  __slots__ = "_crashStack", "_obsYes", "_obsNo";

  def __init__(self):
    raise NotImplementedError("FailureReport cannot be instantiated directly");
  #end: __init__

  # current format: [({G.nodes}, {G.nodes}), ..., ({G.nodes})]
  # TODO: use a class, rather than a rickety data structure mess
  def getCrashStack(self):
    return(self._crashStack);
  #end: getCrashNodes

  # current format: {[{G.nodes}]}
  # TODO: use a class, rather than a rickety data structure mess
  def getObsYes(self):
    return(self._obsYes);
  #end: getObsYes

  # current format: {{G.nodes}}
  # TODO: use a class, rather than a rickety data structure mess
  def getObsNo(self):
    return(self._obsNo);
  #end: getObsNo

  def clearObsYesAndNo(self):
    self._obsNo = set([]);
    self._obsYes = set([]);
  #end: clearObsYesAndNo

  def getAllNodesInFailureReport(self):
    allNodes = set([]);

    for (callNodes, entryNodes) in self._crashStack:
      if(callNodes != None):
        allNodes |= callNodes;
      if(entryNodes != None):
        allNodes |= entryNodes;
    #end for

    # NOTE: we need to use "update" for both obsNo and obsYes because of
    # differences in Text vs JSON failure reports: sometimes it's actually a
    # set, and sometimes it's a tuple (since lists and sets are not hashable)
    for noSet in self._obsNo:
      allNodes.update(noSet);
    #end for

    for yesVector in self._obsYes:
      for yesSet in yesVector:
        allNodes.update(yesSet);
      #end for
    #end for

    return(allNodes);
  #end: getAllNodesInFailureReport
#end: class FailureReport
