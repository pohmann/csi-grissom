#!/s/python-2.7.1/bin/python
"""
----
This program is just a skeleton used to check any interesting property over a
CSI graphml graph.  I basically use it to verify that transformations to the
graph do sensible things.  (Normal consumers of the CSI analysis libs can just
ignore this file.)
----
"""

from sys import stderr, argv

from graphlibs import read_graph
from clock import CSIClock

"""
Check whatever property you want...
"""
def check(G):
  for (src, target, key, attr) in G.edges(None, True, True):
    if(attr.get("type", "") != "data"):
      continue;
    if(G.node[src].get("kind", "") in ["global-actual-in", \
                                       "global-formal-in", "actual-in"] or \
       G.node[target].get("kind", "") in ["global-actual-out", \
                                          "global-formal-out", "actual-out"]):
      continue;
    defs = G.node[src].get("alocs-defd", None);
    mays = G.node[src].get("alocs-mayd", None);
    uses = G.node[target].get("alocs-used", None);
    if(defs == None and mays == None):
      print >> stderr, ("bad source for edge = " + str((src, target)));
    if(uses == None):
      print >> stderr, ("bad target for edge = " + str((src, target)));
  #end for
  
  for (n, attr) in G.nodes(True):
    if(next((True for (pred, cur, data) in G.in_edges_iter([n], data=True) if data.get("type", "") == "control"), False)):
      continue;
    
    if(attr.get("kind", "").strip() not in ["entry", "global-actual-in",  "global-actual-out"]):
      print >> stderr, ("ERROR: found a node with no control parent that isn't an actual!");
      print >> stderr, ("node: " + n + "  attr: " + str(attr));
      exit(1);
    
    if(attr.get("kind", "").strip() != "entry"):
      print >> stderr, ("removing strange control-parent-less node: " + n);
  #end for
#end: check

"""
main(): This is main.  It calls all the other functions for a while and then
exits.
"""
def main():
  if(len(argv) != 2):
    print >> stderr, ("Usage: " + argv[0] + " graph-filename");
    exit(1);
  
  clock = CSIClock();
  print("Reading graph...");
  G = read_graph(argv[1]);
  clock.takeSplit();

  print("Checking graph...");
  G = check(G);
  clock.takeSplit();
  
  print("Done.");
#end: main

if __name__ == '__main__':
  main()
