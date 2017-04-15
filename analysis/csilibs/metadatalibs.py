#!/s/python-2.7.1/bin/python

from sys import stderr
from networkx.classes.digraph import DiGraph

# prints lots of debugging output to stderr
FILTER_DEBUG = False;

"""
All lib functions for reading/processing our CSI metadata.
"""

"""
__entryLineStart(): Internal function to test if a line is of the appropriate
format to start a new CC/BBC/PT entry.  Specifically, it needs to start with
an integer when separated by '|' characters.
@param line the line to check
@return a boolean specifying whether the line has the appropriate structure (at
        its beginning, at least) to be a new data entry, rather than the start
        of a new function's list
"""
def __entryLineStart(line):
  if(not line):
    return(False);

  try:
    int(line.split("|")[0]);
    return(True);
  except ValueError:
    return(False);
#end: __entryLineStart

"""
read_bbc_metadata(): Read in the basic block coverage data file specified.  The
file must be in a very specific format specified by the .debug_BBC section
produced by the LLVM instrumentation.
@param f the path to the file to read
@return a dictionary of functions mapping each index to a basic block
   => {func-name : {index : (csi-label, [line-num])}}
"""
def read_bbc_metadata(f):
  global FILTER_DEBUG;
  if(FILTER_DEBUG):
    print >> stderr, ("reading bbc...");

  try:
    fp = open(f, "r");

    funcBBs = {};
    toSkip = []; # for duplicate function names, conservatively don't include

    line = fp.readline();
    while True:
      if(not line):
        break;
      elif(not line.strip()):
        line = fp.readline();
        continue;
      elif(line[0] != '#'):
        print >> stderr, ("ERROR 1: incorrect formatting in bbc file " + f);
        exit(1);

      lineParts = line[1:].strip().split('|');
      if(len(lineParts) != 2):
        print >> stderr, ("ERROR 2: incorrect formatting in bbc file " + f);
        exit(2);
      funcName = lineParts[0];

      # read the line number entries for this function
      bbs = {}; # index : (label, [line])
      line = fp.readline();
      while(line):
        if(not line or not __entryLineStart(line)):
          break;
        else:
          # empty line#s = NULL (or line#-less) basic block
          lineNums = [x.strip() for x in line.split("|")];
          if(len(lineNums) < 3):
            print >> stderr, ("ERROR: incorrect formatting for bbc entry line"+\
                              " for line: " + line);
            exit(3);
          index = int(lineNums[0]);
          if (index in bbs):
            print >> stderr, ("ERROR: multiple entries for bbc index " + \
                              str(index) + ".  Function " + funcName);
            exit(4);
          label = lineNums[1];
          if(len(lineNums) == 3 and lineNums[2].strip() == "NULL"):
            storeLines = [];
          else:
            storeLines = map(int, lineNums[2:]);
          #end if
          bbs[index] = (label, storeLines);
          line = fp.readline();
        #endIf
      #endWhile

      if(len(bbs) == 0):
        print >> stderr, ("ERROR: missing basic blocks for function " + \
                          funcName.strip() + " in bbc file " + f);
        exit(1);
      if(funcName in toSkip or funcName in funcBBs):
        print >> stderr, ("WARNING: duplicate function bbc for function " + \
                          str(funcName) + ".  Skipping all instances.");
        toSkip += [funcName];
        funcBBs.pop(funcName);
      else:
        funcBBs[funcName.strip()] = bbs;
    #endWhile
    if(FILTER_DEBUG):
      print >> stderr, ("bbc result: " + str(funcBBs));
    return funcBBs;
  except IOError:
    print >> stderr, ("ERROR: could not read from bbc file " + f);
    exit(8);
  except ValueError, e:
    print >> stderr, ("ERROR: line number conversion error in bbc file " + f);
    print >> stderr, (str(e));
    exit(9);
  except:
    print >> stderr, ("ERROR: unexpected fault reading from bbc file " + f);
    raise;
#end: read_bbc_metadata

"""
read_cc_metadata(): Read in the call coverage data file specified.  The file
must be in a very specific format specified by the .debug_CC section produced by
the LLVM instrumentation.
@param f the path to the file to read
@return a dictionary of functions mapping each index to a call
   => {func-name : {index : (csi-label, line-num, call-name)}}
"""
def read_cc_metadata(f):
  global FILTER_DEBUG;
  if(FILTER_DEBUG):
    print >> stderr, ("reading cc...");

  try:
    fp = open(f, "r");

    funcData = {};

    line = fp.readline();
    while True:
      if(not line):
        break;
      elif(not line.strip()):
        line = fp.readline();
        continue;
      elif(line[0] != '#'):
        print >> stderr, ("ERROR 1: incorrect formatting in cc file " + f);
        exit(1);

      lineParts = line[1:].strip().split('|');
      if(len(lineParts) != 2):
        print >> stderr, ("ERROR 2: incorrect formatting in cc file " + f);
        exit(2);
      funcName = lineParts[0];

      # read the call-site entries for this function
      callSites = {}; # index : (label, line, name)
      line = fp.readline();
      while(line):
        if(not line or not __entryLineStart(line)):
          break;
        else:
          lineParts = [x.strip() for x in line.split('|')];
          if(len(lineParts) != 4):
            print >> stderr, ("ERROR: incorrect formatting for cc entry line" +\
                              " for line: " + line);
            exit(3);
          index = int(lineParts[0]);
          if (index in callSites):
            print >> stderr, ("ERROR: multiple entries for index " + \
                              str(index) + ".  Function " + funcName);
            exit(4);
          callSites[index] = (lineParts[1], int(lineParts[2]), lineParts[3]);
          line = fp.readline();
        #endIf
      #endWhile
      if(funcName in funcData):
        print >> stderr, ("ERROR: duplicate function cc for function " + \
                          str(funcName));
        exit(5);
      funcData[funcName] = callSites;
    #endWhile
    if(FILTER_DEBUG):
      print >> stderr, ("cc result: " + str(funcData));
    return funcData;
  except IOError:
    print >> stderr, ("ERROR: could not read from cc file " + f);
    exit(8);
  except ValueError, e:
    print >> stderr, ("ERROR: line number conversion error in cc file " + f);
    print >> stderr, (str(e));
    exit(9);
  except:
    print >> stderr, ("ERROR: unexpected fault reading from cc file " + f);
    raise;
#end: read_cc_metadata

"""
read_pt_metadata(): Read in the path trace data file specified.  The file must
be in a very specific format specified by the .debug_PT section produced by the
LLVM instrumentation.
@param f the path to the file to read
@return three dictionaries of: ({func-name : {bb-num : [line-nums]}},
                                {func-name : entry-bb-num},
                                {func-name : networkx_graph(cfg)})
"""
def read_pt_metadata(f):
  global FILTER_DEBUG;
  if(FILTER_DEBUG):
    print >> stderr, ("reading PT metadata...");

  basic_blocks = {};
  entry_basic_blocks = {};
  cfgs = {};
  try:
    fp = open(f, "r");
    line = fp.readline();
    while True:
      if(not line):
        break;
      elif(line == "\n"):
        line = fp.readline();
        continue;
      elif(line != "#\n"):
        print >> stderr, ("ERROR 1: incorrect formatting in pt file " + f);
        exit(1);

      funcName = fp.readline();
      if(not funcName):
        print >> stderr, ("ERROR 2: incorrect formatting in pt file " + f);
        exit(2);

      # first, read the basic blocks for this function
      bbs = {};
      line = fp.readline();
      while(line):
        if(not line or not line[0].isdigit()):
          break;
        else:
          # add the basic block as (bb#, [line#s])
          # empty line#s = NULL (or line#-less) basic block
          lineNums = [x.strip() for x in line.split("|")];
          if(len(lineNums) == 2 and (lineNums[1].strip() == "NULL" or \
                                     lineNums[1].strip() == "EXIT")):
            # could do something special here for exit if necessary in future
            bbs[int(lineNums[0])] = [];
          else:
            bb_id = int(lineNums[0]);
            if(lineNums[1] == "ENTRY"):
              entry_basic_blocks[funcName.strip()] = bb_id;
              bbs[bb_id] = map(int, lineNums[2:]);
            else:
              bbs[bb_id] = map(int, lineNums[1:]);
          #end if
          line = fp.readline();
        #endIf
      #endWhile
      basic_blocks[funcName.strip()] = bbs;

      if(line != "$\n"):
        print >> stderr, ("ERROR 3: incorrect formatting in pt file " + f);
        exit(3);

      # then, build the cfg based on edge increments
      cfg = DiGraph();
      line = fp.readline();
      while(line):
        if(not line or not line[0].isdigit()):
          break;

        # throw away end-of-line comments
        strippedLine = [x.strip() for x in line.split("#")][0];

        # lineParts : [#->#, increment$weight]
        lineParts = [x.strip() for x in strippedLine.split("|")];
        if(len(lineParts) != 2):
          print >> stderr, ("ERROR 4: incorrect formatting in pt file " + f);
          exit(4);
        #endIf
        attrs = {};
        edgeNodes = lineParts[0].split("->");
        if(len(edgeNodes) == 2):
          attrs["isBackedge"] = False;
        else:
          edgeNodes = lineParts[0].split("~>");
          if(len(edgeNodes) != 2):
            print >> stderr, ("ERROR 5: incorrect formatting in pt file " + f);
            exit(5);
          attrs["isBackedge"] = True;
        #endIf

        edgeParts = [x.strip() for x in lineParts[1].strip().split("$")];
        if(len(edgeParts) != 2):
          print >> stderr, ("ERROR 6: incorrect formatting in pt file " + f);
          exit(6);
        attrs["increment"] = int(edgeParts[0]);
        attrs["weight"] = int(edgeParts[1]);

        cfg.add_edge(int(edgeNodes[0]), int(edgeNodes[1]), attrs);
        line = fp.readline();
      #endWhile
      cfgs[funcName.strip()] = cfg;
    #endWhile
    if(FILTER_DEBUG):
      print >> stderr, ("pt result: " + str((basic_blocks, cfgs)));
    return (basic_blocks, entry_basic_blocks, cfgs);
  except IOError:
    print >> stderr, ("ERROR: could not read from pt file " + f);
    exit(8);
  except ValueError, e:
    print >> stderr, ("ERROR: line number conversion error in pt file " + f);
    print >> stderr, (str(e));
    exit(9);
  except:
    print >> stderr, ("ERROR: unexpected fault reading from pt file " + f);
    raise;
#end: read_pt_metadata
