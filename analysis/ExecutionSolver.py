#!/s/python-2.7.1/bin/python

class ExecutionSolver:
  """
  __init__(): Process the graph, encoding its structure as constraints.
  @param G the graph
  """
  def __init__(self, G):
    raise NotImplementedError("must be implemented in subclass");
  #end: __init__
  
  """
  isSat(): Check whether at least one legal execution exists based on encoded
  constraints.
  @return whether or not the current constraints are satisfiable
  """
  def isSat(self):
    raise NotImplementedError("must be implemented in subclass");
  #end: isSat
  
  """
  encodeCrash(): Encode the constraint for the crashing location.
  @param crashStack a representation of possible crashes in the stack trace,
                    ending in the final possible crashing nodes
            => [({G.nodes}, {G.nodes}), ..., ({G.nodes})]
  """
  def encodeCrash(self, crashStack):
    raise NotImplementedError("must be implemented in subclass");
  #end: encodeCrash
  
  """
  encodeObsYes(): Encode the constraint for a yes-executed observation.
  @param possibleYes a set of possible matches to the true entry
                    (usually a singleton)
            => {G.nodes}
  """
  def encodeObsYes(self, possibleYes):
    raise NotImplementedError("must be implemented in subclass");
  #end: encodeObsYes
  
  """
  encodeObsNo(): Encode the constraint for a not-executed observation.
  @param possibleYes a set of possible matches to the true entry
                    (usually a singleton)
            => {G.nodes}
  """
  def encodeObsNo(self, possibleNo):
    raise NotImplementedError("must be implemented in subclass");
  #end: encodeObsNo
  
  """
  findKnownExecution(): Figure out which nodes in the CFG (a) are known to have
  executed at least once, (b) are known to have not executed, and (c) may or may
  not have executed given the crash location.
  @return (defYes, defNo, maybe)
             => ({G.nodes}, {G.nodes}, {G.nodes})
  """
  def findKnownExecution(self):
    raise NotImplementedError("must be implemented in subclass");
  #end: findKnownExecution
#end: class ExecutionSolver
