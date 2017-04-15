#!/s/python-2.7.1/bin/python

from sys import stderr

# prints lots of debugging output to stderr
FILTER_DEBUG = False;

"""
All lib functions for filtered gdb failure data from CSI-instrumented crashes.
"""

def _strToBool(s):
  return(False if (s.lower() == "false") \
               else True if (s.lower() == "true") \
               else None);
#end: _strToBool

def _emptyData(s, delimiter):
  return(s in ["@", delimiter]);
#end: _emptyData

def _abortBadFormatting(formatType, fileType, line, inputFile, exitCode):
  print >> stderr, ("ERROR: bad " + formatType + " formatting in " + \
                    fileType + " data file " + inputFile);
  print >> stderr, ("error code: " + str(exitCode));
  print >> stderr, ("line was: " + line);
  exit(exitCode);
#end: _abortBadFormatting

"""
read_global_data(): Read in the global failure data from the file specified.
The file must be in a very specific format:
  #func-name1:fc-bool
  |bool|bool|...| OR   @   (for CC)
  |bool|bool|...| OR   @   (for BBC)
  #func-name2:fc-bool
  |bool|bool|...| OR   @   (for CC)
  |bool|bool|...| OR   @   (for BBC)
where '@' indicates no traced data for the indicated type.  In the returned
result, each function is mapped to its (fn-cov, [call-cov], [bb-cov]).
@param f the path to the file to read
@return a dictionary of: {func-name : (bool, [bool], [bool])}
"""
def read_global_data(f):
  global FILTER_DEBUG;
  if(FILTER_DEBUG):
    print >> stderr, ("reading global failure data...");

  try:
    fp = open(f, "r");

    funcData = {};

    line = fp.readline().strip();
    while True:
      if(not line):
        break;
      elif(not line.strip()):
        line = fp.readline().strip();
        continue;
      elif(line[0] != '#'):
        _abortBadFormatting("", "global", line, f, 1);

      lineParts = line[1:].strip().split(':');
      if(len(lineParts) != 2):
        _abortBadFormatting("", "global", line, f, 2);
      funcName = lineParts[0];
      funcCovered = _strToBool(lineParts[1].strip());

      # read the call-site coverage data for this function
      line = fp.readline().strip();
      if(_emptyData(line, '|')):
        callSites = [];
      elif(not line or line[0] != '|' or line[-1] != '|'):
        _abortBadFormatting("CC", "global", line, f, 1);
      else:
        callSites = [_strToBool(x.strip()) for x in line[1:-1].split('|')];

      # read the basic block coverage data for this function
      line = fp.readline().strip();
      if(_emptyData(line, '|')):
        bbs = [];
      elif(not line or line[0] != '|' or line[-1] != '|'):
        _abortBadFormatting("BBC", "global", line, f, 1);
      else:
        bbs = [_strToBool(x.strip()) for x in line[1:-1].split('|')];

      if(funcName in funcData):
        print >> stderr, ("ERROR: duplicate dynamic global function data " + \
                          " for function " + str(funcName));
        exit(3);

      funcData[funcName] = (funcCovered, callSites, bbs);
      line = fp.readline().strip();
    #endWhile
    if(FILTER_DEBUG):
      print >> stderr, ("global data result: " + str(funcData));
    return funcData;
  except IOError:
    print >> stderr, ("ERROR: could not read from global data file " + f);
    exit(8);
  except ValueError, e:
    print >> stderr, ("ERROR: line number conversion error in global data " + \
                      "file " + f);
    print >> stderr, (str(e));
    exit(9);
  except:
    print >> stderr, ("ERROR: unexpected fault reading from global data " + \
                      "file " + f);
    raise;
#end: read_global_data

"""
read_local_data(): Read in the local failure data from the file specified.
The file must be in a very specific format:
  #innermost-func-name|file-path:line:pathFinalValue
  %bool%bool%bool%...% OR   @   (for CC)
  ^bool^bool^bool^...^ OR   @   (for BBC)
  $path$path$path$...$ OR   @   (for PT)
  ...
  #outermost-func-name|file-path:line:pathFinalValue
  %bool%bool%bool%...% OR   @   (for CC)
  ^bool^bool^bool^...^ OR   @   (for BBC)
  $path$path$path$...$ OR   @   (for PT)
where '@' indicates no traced data for the indicated type.  The returned result
is a list, reflecting the above stack frame structure.
@param f the path to the file to read
@return a list of frames, each formatted:
  (func-name, line-num, [path], finalPathValue, [cc-bool], [bbc-bool])
"""
def read_local_data(f):
  global FILTER_DEBUG;
  if(FILTER_DEBUG):
    print >> stderr, ("reading local failure data...");

  try:
    fp = open(f, "r");

    frames = [];

    line = fp.readline().strip();
    while True:
      if(not line):
        break;
      elif(not line.strip()):
        line = fp.readline().strip();
        continue;
      elif(line[0] != '#'):
        _abortBadFormatting("", "local", line, f, 1);

      lineParts = line[1:].split('|');
      if(len(lineParts) != 2):
        _abortBadFormatting("", "local", line, f, 2);
      funcName = lineParts[0];

      lineSp = lineParts[1].split(':');
      if(len(lineSp) != 3):
        _abortBadFormatting("", "local", line, f, 3);
      filePath = lineSp[0];
      try:
        lineNum = int(lineSp[1]);
        finalPathValue = int(lineSp[2]);
      except:
        _abortBadFormatting("", "local", line, f, 4);

      # read the call-site coverage data for this frame
      line = fp.readline().strip();
      if(_emptyData(line, '%')):
        callSites = [];
      elif(not line or line[0] != '%' or line[-1] != '%'):
        _abortBadFormatting("CC", "local", line, f, 1);
      else:
        callSites = [_strToBool(x.strip()) for x in line[1:-1].split('%')];

      # read the basic block coverage data for this frame
      line = fp.readline().strip();
      if(_emptyData(line, '^')):
        bbs = [];
      elif(not line or line[0] != '^' or line[-1] != '^'):
        _abortBadFormatting("BBC", "local", line, f, 1);
      else:
        bbs = [_strToBool(x.strip()) for x in line[1:-1].split('^')];

      # read the path trace data for this frame
      line = fp.readline().strip();
      if(_emptyData(line, '$')):
        paths = [];
      elif(not line or line[0] != '$' or line[-1] != '$'):
        _abortBadFormatting("PT", "local", line, f, 1);
      else:
        try:
          paths = [int(x.strip()) for x in line[1:-1].split('$')];
        except:
          _abortBadFormatting("PT", "local", line, f, 2);

      frames += [(funcName, lineNum, paths, finalPathValue, callSites, bbs)];
      line = fp.readline().strip();
    #end while

    if(FILTER_DEBUG):
      print("local data result:\n" + str(frames));
    return frames;
  except IOError:
    print >> stderr, ("ERROR: could not read from local data file " + f);
    exit(8);
  except ValueError, e:
    print >> stderr, ("ERROR: line number conversion error in local data " + \
                      "file " + f);
    print >> stderr, (str(e));
    exit(9);
  except:
    print >> stderr, ("ERROR: unexpected fault reading from local data " + \
                      "file " + f);
    raise;
#end: read_local_data
