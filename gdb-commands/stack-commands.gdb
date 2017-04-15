set height 0
set width 0
set print repeats 0
set print address off
set print elements 0

python
frame = gdb.selected_frame();
while(frame and frame.is_valid()):
  fnName = frame.name();
  if(not fnName):
    fnName = "?";
  sal = frame.find_sal();
  lineNum = "?";
  fileName = "?";
  if(sal and sal.symtab):
    lineNum = sal.line;
    fileName = sal.symtab.fullname();
  if(not lineNum):
    lineNum = "?";
  if(not fileName):
    fileName = "?";

  counterIdx = "?";
  counterArr = "?";
  currentPath = "?";
  try:
    counterIdx = frame.read_var("__PT_counter_idx");
    counterArr = frame.read_var("__PT_counter_arr");
  except:
    counterIdx = "?";
    counterArr = "?";
  try:
    currentPath = frame.read_var("__PT_current_path");
  except:
    currentPath = "?";

  ccArr = "?";
  try:
    ccArr = frame.read_var("__CC_arr");
  except:
    ccArr = "?";

  bbcArr = "?";
  try:
    bbcArr = frame.read_var("__BBC_arr");
  except:
    bbcArr = "?";

  print("~~" + fnName + ":" + str(lineNum) + ":" + fileName + ":" + \
        str(counterIdx) + ":" + str(counterArr) + ":" + \
        str(currentPath) + ":" + str(ccArr) + ":" + str(bbcArr));
  frame = frame.older();
end
