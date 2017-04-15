# --- settings (based on environment vars passed in) --- #
# most users should never need to mess with graph generation
ifeq ($(strip $(GRAPH_PROG)),)
GRAPHML_EXE=echo "Not building graph for: "
else
GRAPHML_EXE=$(GRAPH_PROG)
endif

# setting specific solvers or intra/interprocedural analysis
ifeq ($(strip $(FIRST_SOLVER)),)
FIRST_FLAG=
else
FIRST_FLAG=--first=$(FIRST_SOLVER)
endif
ifeq ($(strip $(SECOND_SOLVER)),)
SECOND_FLAG=
else
SECOND_FLAG=--second=$(SECOND_SOLVER)
endif
ifeq ($(strip $(SOLVER_INTRA)),)
INTRA_FLAG=
else
INTRA_FLAG=-intra
endif
SOLVER_FLAGS=$(FIRST_FLAG) $(SECOND_FLAG)

# what comparator should we use?
ifeq ($(strip $(COMPARATOR)),)
COMPARATOR_FLAG=
else
COMPARATOR_FLAG=--comparator=$(COMPARATOR)
endif

# should we do any BB collapsing?
ifeq ($(strip $(COLLAPSE)),)
COLLAPSE_FLAG=
else
COLLAPSE_FLAG=--collapse=$(COLLAPSE)
endif

# should we do profiling?
# look at stats with:
# python -c "import pstats; q = pstats.Stats('SOLVER_PROFILE'); q.sort_stats('cumulative').print_stats(10)"
ifeq ($(strip $(SOLVER_PROFILE)),)
SOLVE_PROG=../csi-grissom
else
SOLVE_PROG=python -m cProfile -o $(SOLVER_PROFILE) ../csi-grissom
endif

SOLVER=$(SOLVE_PROG) $(INTRA_FLAG) $(SOLVER_FLAGS) $(COMPARATOR_FLAG) $(COLLAPSE_FLAG)


# ------------------------------------------------------ #

# fix environment variables for reproducibility
PYTHONPATH := /p/csi/public/tools/pyfst/install:/p/csi/public/tools/networkx/1.10/install:/p/csi/public/tools/jpype/install
PATH := /s/python-2.7.1/bin:/usr/bin:/bin

all: test1 test2 test3 test4 test5 test5yes test5no test6 test7 test8 test9 test10 test11 test12 test13

test1.c.graphml: test1.c
	$(GRAPHML_EXE) test1.c
test1: test1.c.graphml
	$(SOLVER) test1.c.graphml --json=test1.json --crash="n:-3:28" --no="n:-3:32"

test2.c.graphml: test2.c
	$(GRAPHML_EXE) test2.c
test2: test2.c.graphml
	$(SOLVER) test2.c.graphml --json=test2.json --crash="n:-3:27"

test3.c.graphml: test3.c
	$(GRAPHML_EXE) test3.c
test3: test3.c.graphml
	$(SOLVER) test3.c.graphml --json=test3.json --crash="n:-3:25"

# test context-sensitivity; look for whether n:-5:14 is in maybe or defYes
test4.c.graphml: test4.c
	$(GRAPHML_EXE) test4.c
test4: test4.c.graphml
	$(SOLVER) test4.c.graphml --json=test4.json --crash="n:-4:9"

test5.c.graphml: test5.c
	$(GRAPHML_EXE) test5.c
test5: test5.c.graphml
	$(SOLVER) test5.c.graphml --json=test5.json --crash="n:-3:25"
test5yes: test5.c.graphml
	$(SOLVER) test5.c.graphml --json=test5yes.json --crash="n:-3:25" --yes="n:-3:27"
test5no: test5.c.graphml
	$(SOLVER) test5.c.graphml --json=test5no.json --crash="n:-3:25" --no="n:-3:26"

test6.c.graphml: test6.c
	$(GRAPHML_EXE) test6.c
test6: test6.c.graphml
	$(SOLVER) test6.c.graphml --json=test6.json --crash="n:-3:15" --yes="n:-3:25|n:-3:12;n:-3:11|n:-3:12" --no="n:-3:22"

test7.c.graphml: test7.c
	$(GRAPHML_EXE) test7.c
test7: test7.c.graphml
	$(SOLVER) test7.c.graphml --json=test7.json --crash="n:-3:11" --yes="n:-3:18"

# the example from the CSTVA paper
test8.c.graphml: test8.c
	$(GRAPHML_EXE) test8.c
test8: test8.c.graphml
	$(SOLVER) -intra --result-style=full test8.c.graphml --json=test8.json --crash="n:-3:13" --yes="n:-3:12|n:-3:18|n:-3:12" --no="n:-3:22"

# a counter-example to the original exeYes ordering rule
# (which assumed {<A,B>,<C,D>} implied either ABCD or CDAB)
# expected failure: SAT marks n:-3:15 as "defYes" rather than "maybe"
test9.c.graphml: test9.c
	$(GRAPHML_EXE) test9.c
test9: test9.c.graphml
	$(SOLVER) -intra --result-style=full test9.c.graphml --json=test9.json --crash="n:-3:12" --yes="n:-3:8|n:-3:10;n:-3:9|n:-3:11"

# NOTE: NOT COMPLETELY FINISHED
# another counter-example to a possible exeYes ordering fix
# (which involved something with:
#    not connected(B, C, X). not connected(D, A, X).)
test10.c.graphml: test10.c
	$(GRAPHML_EXE) test10.c
test10: test10.c.graphml
	$(SOLVER) --result-style=full test10.c.graphml --json=test10.json --crash="n:-6:20"

# a pretty basic graph checking the relationship between obsYes and obsNo (and nodes "between" them that
# should end up in "exeNo")
test11.c.graphml: test11.c
	$(GRAPHML_EXE) test11.c
test11: test11.c.graphml
	$(SOLVER) -intra test11.c.graphml --json=test11.json --crash="n:-3:13" --yes="n:-3:16|n:-3:17" --no="n:-3:10"

# a very simple (slightly hand-edited) first Java test
test12: test12.java.graphml
	$(SOLVER) --result-style=full test12.java.graphml --json=test12.json

# a second Java test (that caused a failure in the UTL solver)
test13: test13.java.graphml
	$(SOLVER) test13.java.graphml --json=test13.json

# /scratch.1/ohmann/sliver/results_trace/grep/grep-2/FAULTY_F_DG_1/grep.graphml
grep: grep.graphml
	$(SOLVER) grep.graphml --crash="n:-60:57"
	#../grissom.py grep.graphml n:-71:30
#n:-71:185, n:-71:45, n:-71:55, n:-71:74

flex: flex.graphml
	$(SOLVER) flex.graphml --json=flex.json

flexfull: flex.graphml
	$(SOLVER) flex.graphml --json=flexfull.json

# NOTE: from sliver test case: 17-core
# /scratch.1/ohmann/sliver/results_trace/ccrypt/ccrypt-1/FAULT_PROMPT_XREADLINE_NULL_CHECK/graph.pickle
ccrypt: ccrypt.graphml
	$(SOLVER) ccrypt.graphml --json=ccrypt.json --crash="n:-56:16"
ccryptfull: ccrypt.graphml
	$(SOLVER) ccrypt.graphml --json=ccryptfull.json --crash="n:-56:16" --yes="n:-18:35;n:-56:8;n:-57:8;n:-50:9;n:-31:58;n:-31:20;n:-18:28;n:-29:10;n:-56:12;n:-18:264;n:-29:18;n:-70:18;n:-18:270;n:-29:29;n:-31:16;n:-34:19;n:-53:17;n:-70:108;n:-70:106;n:-34:14;n:-53:22;n:-29:173;n:-53:20;n:-34:53;n:-34:55;n:-34:21;n:-34:57;n:-31:13;n:-51:10;n:-34:43;n:-79:10;n:-70:233" --no="n:-70:163;n:-49:39;n:-102:43;n:-102:40;n:-102:47;n:-102:45;n:-73:51;n:-50:18;n:-46:10;n:-18:56;n:-29:235;n:-17:27;n:-17:57;n:-27:12;n:-18:233;n:-91:42;n:-18:235;n:-39:18;n:-79:51;n:-29:272;n:-16:7;n:-18:136;n:-18:138;n:-98:-22;n:-98:-23;n:-5:9;n:-73:16;n:-98:-24;n:-98:-25;n:-27:9;n:-70:74;n:-39:26;n:-17:14;n:-70:244;n:-98:19;n:-64:14;n:-18:60;n:-17:52;n:-29:248;n:-17:19;n:-15:7;n:-69:17;n:-70:136;n:-79:33;n:-18:202;n:-70:40;n:-69:61;n:-29:93;n:-73:20;n:-70:139;n:-73:24;n:-79:35;n:-18:124;n:-51:18;n:-104:7;n:-64:22;n:-101:37;n:-6:13;n:-120:22;n:-31:35;n:-101:35;n:-31:32;n:-29:74;n:-69:26;n:-99:79;n:-70:256;n:-31:39;n:-102:28;n:-63:48;n:-6:9;n:-63:38;n:-70:50;n:-18:212;n:-18:198;n:-18:214;n:-69:15;n:-70:56;n:-43:13;n:-18:118;n:-73:58;n:-73:54;n:-27:17;n:-6:16;n:-18:116;n:-29:256;n:-49:21;n:-119:30;n:-29:121;n:-29:105;n:-119:-40;n:-90:18;n:-90:16;n:-13:7;n:-119:-41;n:-116:18;n:-79:37;n:-98:26;n:-17:66;n:-3:19;n:-29:240;n:-69:44;n:-70:260;n:-43:22;n:-102:38;n:-18:187;n:-70:29;n:-43:24;n:-102:32;n:-93:22;n:-102:30;n:-29:36;n:-52:22;n:-102:34;n:-93:24;n:-18:85;n:-29:147;n:-18:83;n:-17:78;n:-91:40;n:-69:36;n:-18:101;n:-18:103;n:-70:151;n:-70:153;n:-79:28;n:-9:11;n:-98:23;n:-77:16;n:-98:21;n:-38:24;n:-77:11;n:-59:15;n:-63:70;n:-70:195;n:-70:273;n:-63:14;n:-63:8;n:-29:47;n:-50:20;n:-29:41;n:-98:47;n:-17:24;n:-102:-31;n:-102:-32;n:-102:-33;n:-102:-34;n:-102:-35;n:-102:-36;n:-8:25;n:-49:24;n:-101:39;n:-93:15;n:-93:13;n:-29:131;n:-93:9;n:-99:-27;n:-99:-26;n:-29:238;n:-99:-29;n:-99:-28;n:-29:230;n:-120:14;n:-29:133;n:-51:20;n:-70:144;n:-79:16;n:-40:22;n:-120:19;n:-40:24;n:-69:9;n:-29:65;n:-119:-38;n:-70:208;n:-29:191;n:-18:243;n:-55:18;n:-18:241;n:-101:27;n:-101:20;n:-65:16;n:-101:22;n:-59:13;n:-49:36;n:-18:249;n:-108:15;n:-63:55;n:-29:202;n:-99:-30;n:-29:204;n:-116:25;n:-70:81;n:-116:22;n:-102:66;n:-108:44;n:-105:7;n:-70:170;n:-40:16;n:-46:12;n:-40:13;n:-103:9;n:-70:216;n:-29:83;n:-39:24;n:-43:19;n:-29:186;n:-70:211;n:-29:189;n:-108:10;n:-73:88;n:-119:-39;n:-70:219;n:-69:34;n:-65:24;n:-98:-21;n:-18:251;n:-99:30;n:-65:21;n:-98:28;n:-17:42;n:-102:68;n:-17:47;n:-91:20;n:-34:89;n:-91:25;n:-91:27;n:-70:284;n:-70:287;n:-99:48;n:-29:218;n:-66:22;n:-70:282;n:-29:117;n:-38:13;n:-29:262;n:-64:19;n:-79:72;n:-38:16;n:-38:19;n:-17:60;n:-43:16;n:-29:119;n:-70:186;n:-99:28;n:-40:19;n:-99:22;n:-108:23;n:-99:24;n:-69:52;n:-119:13;n:-34:91;n:-17:39;n:-63:22;n:-18:47;n:-63:64;n:-17:36;n:-73:56;n:-38:22;n:-63:31;n:-17:33;n:-114:35;n:-70:62;n:-70:64;n:-66:14;n:-114:32;n:-55:21;n:-70:114;n:-66:19;n:-55:24;n:-39:21;n:-27:27;n:-79:62;n:-29:266;n:-69:54;n:-39:15;n:-27:29"

# NOTE: from sliver test case: 1402-core
# /scratch.1/ohmann/sliver/siemens/schedule/builds/v9/singleton/none/schedule.graphml
schedule: schedule.graphml
	$(SOLVER) schedule.graphml --json=schedule.json --crash="n:-23:119"
schedulefull: schedule.graphml
	$(SOLVER) schedule.graphml --json=schedulefull.json --crash="n:-23:119" --yes="n:-23:13" --no="n:-14:12;n:-19:4;n:-14:10;n:-22:22;n:-23:88;n:-23:96;n:-11:6;n:-17:15;n:-21:10;n:-18:11;n:-19:9;n:-23:122;n:-23:72;n:-13:11;n:-23:100;n:-17:19;n:-17:23;n:-7:5;n:-23:104;n:-5:7;n:-16:29;n:-23:40;n:-23:49;n:-23:45;n:-15:14;n:-16:21;n:-23:66;n:-20:9;n:-23:59;n:-23:61;n:-14:4;n:-21:7;n:-23:86;n:-22:19;n:-23:36;n:-8:9;n:-22:11;n:-16:25;n:-18:5"

cleangraphml:
	rm -Rf *.graphml static.*

clean:
	rm -Rf static.*
