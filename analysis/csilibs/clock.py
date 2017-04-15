#!/s/python-2.7.1/bin/python

"""
A basic timer class used by the CSI analysis passes.
"""

import time
from sys import stderr

class CSIClock:
  __slots__ = "__lastTick";
  
  def tick(self):
    self.__lastTick = time.time();
  #end: tick
  
  def __init__(self):
    self.tick();
  #end: __init__
  
  def takeSplit(self):
    print("Took %0.3f s." % (time.time() - self.__lastTick));
    self.tick();
  #end: takeSplit
#end: class CSIClock
