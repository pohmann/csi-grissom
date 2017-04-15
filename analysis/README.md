# CSI-Grissom

## Building

To build, run `make` in the root directory.

### Libraries

First, you will need the following external utilities in your PATH/PYTHONPATH:
* [JPype](https://jpype.readthedocs.io/en/latest)
* [NetworkX](https://networkx.github.io) 1.10+
* [Python](https://www.python.org) 2.7.x
* [PyFST](http://pyfst.github.io)
* [SymbolicAutomata](https://github.com/lorisdanto/symbolicautomata)

If you are on the UW-Madison CSL network, these are installed for you in:
```
/p/csi/public/tools
```
Specifically, you can run the following commands:
```
PYTHONPATH=/p/csi/public/tools/pyfst/install:/p/csi/public/tools/networkx/1.10/install:/p/csi/public/tools/jpype/install
PATH=/s/python-2.7.1/bin:/usr/bin:/bin
```

You also need to tell `make` where to find your `SymbolicAutomata` library install.
If you are on the UW-Madison CSL network, this should default to the right
place.  Otherwise, you'll need to run `make` similar to:
```
make SVPA_LIB_DIR=/path/to/symbolicautomata/install/SVPAlib
```

## Running

Then, you can run all regression tests by running `make` in the `test`
subdirectory, or by running `make test` in the root directory.

If you want to run the tool on your own graphs, you will need to produce a
GraphML file (suitable for normal CSI analysis); call it `mygraph.graphml`.
Then, you'll need to convert your failure data into the appropriate JSON format.
See the `JSONFailureReport` class for formatting, and the test subdirectory for
many examples.  Suppose your JSON file is called `fail.json`.
Then, run `csi-grissom` from the root directory:
```
csi-grissom mygraph.graphml -json fail.json
```
The `csi-grissom` tool takes more arguments to use specific solvers, perform
intra vs. interprocedural analysis, etc.  See the --help output for more
details.
