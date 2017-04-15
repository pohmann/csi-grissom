#!/usr/bin/env python

from sys import stdin, stdout, stderr

# prints all output to stderr as well as stdout
FILTER_DEBUG = False;

"""
Filter gdb's output for the local coverage data to work with the rest of the
analysis.  This is known to work with
GNU gdb (GDB) Red Hat Enterprise Linux (7.0.1-42.el5) and
GNU gdb (GDB) 7.9
The input is formatted:
  ~~func-name:lineNum:fileName:pathFinalIdx:pathArr:pathFinalValue:ccArr:bbcArr
The output is formatted:
  #func-name|file-path:line:pathFinalValue
  %cc%cc%cc%...% OR @
  ^bb^bb^bb^...^ OR @
  $path$path$path$...$   OR   @
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

      tokens = line[2:].split(':');
      if(len(tokens) != 8):
        print >> stderr, ("ERROR: unexpected gdb formatting. abort.");
        print >> stderr, ("line: " + line);
        exit(1);

      funcName = tokens[0];
      lineNum = 0;
      try:
        if(tokens[1].strip() == "?"):
          lineNum = -1;
        else:
          lineNum = int(tokens[1]);
      except:
        print >> stderr, ("ERROR: unexpected gdb (line#) formatting. abort.");
        print >> stderr, ("line: " + line);
        exit(2);

      filePath = tokens[2];

      arrIndex = 0;
      try:
        if(tokens[3].strip() == "?"):
          arrIndex = -1;
        else:
          arrIndex = int(tokens[3]);
      except:
        print >> stderr, ("ERROR: unexpected gdb (idx) formatting. abort.");
        print >> stderr, ("line: " + line);
        exit(3);
      arrValues = [];
      try:
        if(tokens[4].strip() == "?"):
          arrValues = [];
        elif(tokens[4][0] != '{' or tokens[4][-1] != '}'):
          raise Exception;
        else:
          arrValues = map(int, tokens[4][1:-1].split(", "));
      except:
        print >> stderr, ("ERROR: unexpected gdb (arr) formatting. abort.");
        print >> stderr, ("line: " + line);
        exit(4);
      curPath = 0;
      try:
        if(tokens[5].strip() == "?"):
          curPath = -1;
        else:
          curPath = int(tokens[5]);
      except:
        print >> stderr, ("ERROR: unexpected gdb (curpath) formatting. abort.");
        print >> stderr, ("line: " + line);
        exit(5);

      ccValues = [];
      try:
        tokens[6] = tokens[6].strip();
        if(tokens[6] == "?"):
          ccValues = [];
        elif(tokens[6][0] != '{' or tokens[6][-1] != '}'):
          raise Exception;
        else:
          ccValues = map(lambda x: False if (x.strip() == "false") \
                                         else True if (x.strip() == "true") \
                                         else None,
                         tokens[6][1:-1].split(','));
      except:
        print >> stderr, ("ERROR: unexpected gdb (cc) formatting. abort.");
        print >> stderr, ("line: " + tokens[6]);
        exit(6);

      bbcValues = [];
      try:
        tokens[7] = tokens[7].strip();
        if(tokens[7] == "?"):
          bbcValues = [];
        elif(tokens[7][0] != '{' or tokens[7][-1] != '}'):
          raise Exception;
        else:
          bbcValues = map(lambda x: False if (x.strip() == "false") \
                                          else True if (x.strip() == "true") \
                                          else None,
                          tokens[7][1:-1].split(','));
      except:
        print >> stderr, ("ERROR: unexpected gdb (bbc) formatting. abort.");
        print >> stderr, ("line: " + tokens[7]);
        exit(6);

      print("#" + funcName + "|" + filePath + ":" + str(lineNum) + ":" + \
            str(curPath));
      if(FILTER_DEBUG):
        print >> stderr, ("#" + funcName + "|" + filePath + ":" + \
                          str(lineNum) + ":" + str(curPath));

      # print the entire call coverage array
      if(len(ccValues) == 0):
        stdout.write("@");
        if(FILTER_DEBUG):
          stderr.write("@");
      else:
        stdout.write("%");
        if(FILTER_DEBUG):
          stderr.write("%");
        for entry in ccValues:
          stdout.write(str(entry) + "%");
          if(FILTER_DEBUG):
            stderr.write(str(entry) + "%");
      print("");
      if(FILTER_DEBUG):
        print >> stderr, ("");

      # print the entire basic block coverage array
      if(len(bbcValues) == 0):
        stdout.write("@");
        if(FILTER_DEBUG):
          stderr.write("@");
      else:
        stdout.write("^");
        if(FILTER_DEBUG):
          stderr.write("^");
        for entry in bbcValues:
          stdout.write(str(entry) + "^");
          if(FILTER_DEBUG):
            stderr.write(str(entry) + "^");
      print("");
      if(FILTER_DEBUG):
        print >> stderr, ("");

      # set up to print the path trace array
      if(arrIndex == -1):
        stdout.write("@");
        if(FILTER_DEBUG):
          stderr.write("@");
        arrIndex = 0;
      else:
        stdout.write("$");
        if(FILTER_DEBUG):
          stderr.write("$");

      # check for setinal value--if we've wrapped around
      if(arrValues and arrValues[-1] != -1):
        for path in arrValues[arrIndex:]:
          stdout.write(str(path) + "$");
          if(FILTER_DEBUG):
            stderr.write(str(path) + "$");
      # then do the first part of the array
      for path in arrValues[:arrIndex]:
        stdout.write(str(path) + "$");
        if(FILTER_DEBUG):
          stderr.write(str(path) + "$");
      print("");
      if(FILTER_DEBUG):
        print >> stderr, ("");
    #end if
  #end while
#end: main

if __name__ == '__main__':
  main()
