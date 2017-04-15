#!/usr/bin/env python

from sys import stdin, stdout, stderr

# prints all output to stderr as well as stdout
FILTER_DEBUG = False;

"""
Filter gdb's output for the global coverage data to work with the rest of the
analysis.  This is known to work with
GNU gdb (GDB) Red Hat Enterprise Linux (7.2.?-??.el6) and
GNU gdb (GDB) 7.9
The input is formatted:
  ~~func-name|ccArr|fcVal|bbcArr
The output is formatted:
  #func-name1:fc-bool
  |bool-entry|bool-entry|...| OR   @   (for CC)
  |bool-entry|bool-entry|...| OR   @   (for BBC)
  #func-name2:fc-bool
  |bool|bool|...| OR   @   (for CC)
  |bool|bool|...| OR   @   (for BBC)
NOTE: here, @ means that the type of instrumentation was not found.
"""

def main():
  global FILTER_DEBUG;

  while True:
    line = stdin.readline().strip();
    if(not line):
      break;
    elif(line[:5].lower() == "error"):
      print >> stderr, ("ERROR: error during gdb:");
      print >> stderr, (line);
      exit(1);
    elif(line[0] == '~' and line[1] == '~'):
      if(FILTER_DEBUG):
        print >> stderr, (line);

      tokens = line[2:].split('|');
      if(len(tokens) != 4):
        print >> stderr, ("ERROR: unexpected gdb global data formatting");
        print >> stderr, ("line: " + line);
        exit(1);

      funcName = tokens[0].strip();

      ccArr = tokens[1].strip();
      if(not ccArr or ccArr[0] != '{' or ccArr[-1] != '}'):
        print >> stderr, ("ERROR: unexpected gdb (cc-arr) formatting. abort.");
        print >> stderr, ("Line: " + line);
        exit(2);
      ccValues = [];
      try:
        ccValues = map(lambda x: False if (x.strip() == "false") \
                                       else True if (x.strip() == "true") \
                                       else None,
                       ccArr[1:-1].split(','));
      except:
        print >> stderr, ("ERROR: unexpected gdb (cc-vals) formatting. abort.");
        print >> stderr, ("line: " + line);
        exit(3);

      fcValue = True;
      try:
        fcValue = tokens[2].strip();
      except:
        print >> stderr, ("ERROR: unexpected gdb (fc) formatting. abort.");
        print >> stderr, ("line: " + line);
        exit(4);

      bbcArr = tokens[3].strip();
      if(not bbcArr or bbcArr[0] != '{' or bbcArr[-1] != '}'):
        print >> stderr, ("ERROR: unexpected gdb (bbc-arr) formatting. abort.");
        exit(2);
      bbcValues = [];
      try:
        bbcValues = map(lambda x: False if (x.strip() == "false") \
                                        else True if (x.strip() == "true") \
                                        else None,
                        bbcArr[1:-1].split(','));
      except:
        print >> stderr, ("ERROR: unexpected gdb (bbc-vals) formatting.abort.");
        print >> stderr, ("line: " + line);
        exit(3);

      print("#" + funcName + ":" + str(fcValue));
      if(ccValues):
        print("|" + "|".join(map(str, ccValues)) + "|");
      else:
        print("@");
      if(bbcValues):
        print("|" + "|".join(map(str, bbcValues)) + "|");
      else:
        print("@");
  #end while
#end: main

if __name__ == '__main__':
  main()
