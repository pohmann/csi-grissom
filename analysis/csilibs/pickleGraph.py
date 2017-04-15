#!/s/python-2.7.1/bin/python
"""
----
This program will read in a graphml file, do necessary fixing on the graph, and
then pickle it out.
----
"""

from sys import stderr, argv

import pickle

from graphlibs import read_graph
from clock import CSIClock

"""
main(): This is main.  It calls all the other functions for a while and then
exits.
"""
def main():
  if(len(argv) != 3):
    print >> stderr, ("Usage: " + argv[0] + " graph-filename pickle-filename");
    exit(1);
  clock = CSIClock();
  print("Reading (and fixing) graph...");
  G = read_graph(argv[1]);
  clock.takeSplit();
  
  print("Pickling graph..."),;
  pickle.dump(G, open(argv[2],"wb"));
  clock.takeSplit();
#end: main

if __name__ == '__main__':
  main()
