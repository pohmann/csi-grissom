# CSI: Grissom

An analysis framework for answering user control-flow queries. The techniques were
originally proposed in

> P. Ohmann, A. Brooks, L. D'Antoni, and B. Liblit.
"[Control-Flow Recovery from Partial Failure Reports](http://pages.cs.wisc.edu/~liblit/pldi-2017/)."
PLDI, 2017.  ACM.

## Current Release

[`csi-grissom` v0.1.0](../../releases/tag/v0.1.0)

## Building

The dependencies for CSI-Grissom are:
* [csi-cc](https://github.com/liblit/csi-cc)
* [JPype](https://jpype.readthedocs.io/en/latest)
* [NetworkX](https://networkx.github.io) 1.10+
* [Python](https://www.python.org) 2.7.x
* [PyFST](http://pyfst.github.io)
* [SymbolicAutomata](https://github.com/lorisdanto/symbolicautomata)

To build Grissom, run `make`.  You will need to specify the installation
location of the
[SymbolicAutomata](https://github.com/lorisdanto/symbolicautomata) library and
the [csi-cc](https://github.com/liblit/csi-cc) instrumenting compiler on
your system (if not in your PATH).  To do so, run `make` as follows:
```
make SVPA_LIB_DIR=/path/to/symbolicautomata/SVPAlib CSI_CC=/path/to/csi-cc/Release/csi-cc
```

This will generate two executables.  The first, `csi-grissom`, is contained
within the `analysis` subdirectory, and is the underlying analysis engine for
all available solvers.  The second, `do-csi-analysis`, is a frontend that will
run `csi-grissom` on a provided executable (produced by `csi-cc`) and core dump
from a failing run of that executable.

## Running

The above build will generate two executables.  The first, `csi-grissom`, is
contained within the `analysis` subdirectory, and is the underlying analysis
engine for all available solvers.  The second, `do-csi-analysis`, is a frontend
that will run `csi-grissom` on a provided executable (produced by `csi-cc`) and
core dump from a failing run of that executable. In both cases, the analysis
will run one query for each basic block in the program, and output the Yes, No,
and Maybe sets as discussed in section 6 of the PLDI paper.

### Running Analysis Directly with `csi-grissom`

To run analysis on a control-flow graph and failure report, the basic command
is:
```
csi-grissom -json path_to_json path_to_graphml
```
Here, the JSON file is the extracted failure data for the failing run, and the
GraphML file is the control-flow graph of the program (with appropriate
annotations as added by `csi-cc`).

The `csi-grissom` script takes a number of arguments to configure which solver
is run (UTL, FSA, or SVPA) and how results are formatted.  Run
```
csi-grissom --help
```
for the full listing of options.  Some commonly useful options include:

* `-first <UTL,FSA,SVPA>` indicates which solver to run. (default: UTL)
* `-result-style <none,compact,full,csiclipse,standard>` indicates how to
  display the results.  The two most useful options are `compact`, which simply
  displays the sizes of the Yes, No, and Maybe sets, and `standard`, which
  displays the list of lines in each file that have at least one expression
  marked as Yes, No, and Maybe. (default: compact)
* `-stackonly` tells the analysis to ignore all failure data except the crashing
  stack trace (e.g., ignore `csi-cc` call coverage data).

less common options that may be useful include:

* `-second <UTL,FSA,SVPA,None>` indicates a second solver to run (if any) whose
  output will be compared to the first solver.  This is useful to verify that
  all solvers produce expected results. (default: None)
* `-compare <eq,gt,lt>` indicates how the analysis should compare the results of
  the first and second solvers.  If `eq`, they should produce exactly the same
  Yes, No, and Maybe sets.  If `gt`, the first solver is expected to be more
  precise, and should classify no less statements as Yes and/or No than the
  second solver (i.e., it's Maybe set should be a subset of the second solver's
  Maybe set).  If `lt`, the second solver should be more precise.

### Running Analysis on an Executable and Core Dump

The script `do-csi-analysis` takes an executable file and a core dump (produced
from a failing run of that executable) as input, extracts the failure data from
the core dump, and runs `csi-grissom` on the extracted data.  The basic usage is
```
do-csi-analysis executable corefile
```

The script supports a number of options, and the full list is available by
running:
```
do-csi-analysis --help
```
The `-solver` and `-result-style` options are identical to those from
`csi-grissom`, as described above.  The `-save-temps` option instructs the
solver to not use a temporary directory, and instead store extracted failure
data in a new subdirectory of `cwd`.  The `-debug` flag allows all output to
flow directly from `csi-grissom` to the user, rather than hiding progress
updates and internal log messages printed by `csi-grissom`.

Note that the executable *must* be produced by the `csi-cc` instrumenting C
compiler.  The `csi-cc` compiler is
[extensively documented](https://rawgit.com/liblit/csi-cc/master/doc/index.html).
We recommend the following command to compile for testing:
```
csi-cc --trace=/path/to/csi-cc/schemas/cc.schema -csi-opt=2 -opt-style=simple my_file.c
```
This command compiles `my_file.c` with optimized call-site coverage
instrumentation, precisely as done for the experiments in section 6 of the PLDI
paper.  Note that `csi-cc` is a near drop-in replacement for `gcc`, so it also
nearly all standard `gcc` options (such as `-c`).

Be sure to configure your operating system to produce core dumps for failing
native applications; see the `ulimit` command for details. If the application
`a.out` (compiled and linked by `csi-cc`) produced file `core.123` from a
failing run, a basic launch of the analysis would look like:
```
do-csi-analysis a.out core.123
```

## Changelog

### [v. 0.1.0](../../releases/tag/v0.1.0)

Initial release.
