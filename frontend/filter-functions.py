#!/usr/bin/env python

from sys import stdin, stdout, stderr

# prints all output to stderr as well as stdout
FILTER_DEBUG = False;

"""
input from gdb:
~~functionName1
~~functionName2
"""

def main():
  global FILTER_DEBUG;
  
  while True:
    line = stdin.readline();
    if(not line):
      break;
    elif(line[:5].lower() == "error"):
      print >> stderr, ("ERROR: error during gdb:");
      print >> stderr, (line);
      exit(1);
    elif(len(line) >= 2 and line[0] == '~' and line[1] == '~'):
      if(FILTER_DEBUG):
        print >> stderr, (line);
      print (line[2:].split(':')[0]);
  #end while
#end: main

if __name__ == '__main__':
  main()
