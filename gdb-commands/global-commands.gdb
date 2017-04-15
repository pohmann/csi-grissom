set height 0
set width 0
set print repeats 0
set print address off
set print elements 0

python
from __future__ import print_function
from os import environ
from sys import stderr

ccData = environ.get("CC_FILE", "");
fcFile = environ.get("FC_FILE", "");
bbcFile = environ.get("BBC_FILE", "");

fcData = {};
bbcData = {};

fc_fp = None;
try:
  fc_fp = open(fcFile, "r");
except IOError:
  print("ERROR: could not open FC file " + fcFile, file=stderr);
  exit(1);
#end try
line = fc_fp.readline();
while True:
  if(not line):
    break;
  elif(not line.strip() or line.strip()[0] != '#'):
    line = fc_fp.readline();
    continue;

  lineParts = line.strip()[1:].split('|');
  if(len(lineParts) != 2):
    print("ERROR: incorrect formatting in FC file " + fcFile, file=stderr);
    exit(1);

  funcName = lineParts[0].strip();
  arrName = lineParts[1].strip();
  fcData[funcName] = arrName;
  line = fc_fp.readline();
#end while

bbc_fp = None;
try:
  bbc_fp = open(bbcFile, "r");
except IOError:
  print("ERROR: could not open BBC file " + bbcFile, file=stderr);
  exit(1);
#end try
line = bbc_fp.readline();
while True:
  if(not line):
    break;
  elif(not line.strip() or line.strip()[0] != '#'):
    line = bbc_fp.readline();
    continue;

  lineParts = line.strip()[1:].split('|');
  if(len(lineParts) != 2):
    print("ERROR: incorrect formatting in BBC file " + bbcFile, file=stderr);
    exit(1);

  funcName = lineParts[0].strip();
  arrName = lineParts[1].strip();
  bbcData[funcName] = arrName;
  line = bbc_fp.readline();
#end while

fp = None;
try:
  fp = open(ccData, "r");
except IOError:
  print("ERROR: could not open CC file " + ccData, file=stderr);
  exit(1);
#end try

line = fp.readline();
while True:
  if(not line):
    break;
  elif(not line.strip() or line.strip()[0] != '#'):
    line = fp.readline();
    continue;

  lineParts = line.strip()[1:].split('|');
  if(len(lineParts) != 2):
    print("ERROR: incorrect formatting in CC file " + ccData, file=stderr);
    exit(1);

  funcName = lineParts[0].strip();
  arrName = lineParts[1].strip();

  ccArray = "{}";
  fcVal = "?";
  bbcArray = "{}";
  try:
    ccArray = gdb.parse_and_eval(arrName);
  except:
    pass;
  if(fcData.get(funcName, None)):
    try:
      fcVal = gdb.parse_and_eval(fcData[funcName]);
    except:
      pass;
  #end if
  if(bbcData.get(funcName, None)):
    try:
      bbcArray = gdb.parse_and_eval(bbcData[funcName]);
    except:
      pass;
  #end if

  print("~~" + funcName + "|" + str(ccArray) + "|" + str(fcVal) + "|" + \
        str(bbcArray));
  line = fp.readline();
#end while

fp.close();
end
