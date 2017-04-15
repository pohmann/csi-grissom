#!/usr/bin/env python

"""
Read in failure data and the necessary metadata to produce appropriate a JSON
input file for the exe data recovery analysis.
"""

import json
from sys import argv, stderr

from clock import CSIClock
from dynamicdatalibs import read_global_data, read_local_data
from graphlibs import find_function_entry, find_function_id, \
                      find_possible_match_nodes, function_id, \
                      nodes_from_label, read_graph
from metadatalibs import read_bbc_metadata, read_cc_metadata, read_pt_metadata


# prints various computed structures to stderr as the algorithm progresses
FILTER_DEBUG = False;

# exclude certain extracted data (for experiments)
EXTRACT_CC = True;
EXTRACT_FC = True;
EXTRACT_BBC = True;
EXTRACT_PT = True;

"""
_filterToCalls(): Filter a set down to just those nodes that are calls;
optionally only calls to the specified entry node(s).
@param G the graph
@param nodes the node set to filter
@param targets the legal targets, one of which must be called by each acceptable
               member of "nodes".  If None, do not perform target matching.
@return the subset of "nodes" that are call-sites calling a target in "targets"
"""
def _filterToCalls(G, nodes, targets=None):
  filteredNodes = set([]);
  for n in nodes:
    if(G.node.get(n, {}).get("kind", "") != "call-site"):
      continue;

    for (call, target, data) in G.out_edges_iter([n], data=True):
      if((targets == None or target in targets) and \
         data.get("type", "") == "control" and \
         data.get("scope", "") == "interprocedural"):
        filteredNodes.add(n);
        break;
      #end if
    #end for
  #end for

  return(filteredNodes);
#end: _filterToCalls

"""
matchStackData(): Match local failure data to the graphml.  This function
provides the information necessary for the "stack" and "crash" fields of the
JSON input file.
@param G the graph
@param localData the local failure data
   => [(func-name, line-num, [path], finalPathValue, [cc-bool], [bbc-bool])]
@param bbcMetadata metadata for basic block coverage
   => {func-name : {index : (csi-label, [line-num])}}
@param ccMetadata metadata for call-site coverage
   => {func-name : {index : (csi-label, line-num, call-name)}}
@param ptMetadata currently unused for this analysis
@return a final crash point and a list of stack frames in terms of G.ndoes:
   => [({crashNode}, None), ({callNode}, {entryNode}), ...]
        Note that everything is a set: in the case of ambiguity, we return all
        possible nodes that match each piece of data.
"""
def matchStackData(G, localData, bbcMetadata, ccMetadata, ptMetadata):
  if(len(localData) < 1):
    print >> stderr, ("ERROR: completely missing local data");
    exit(1);
  #end if

  started = False; # have we seen at least one matchable frame so far?
  expectCall = False; # regardless of "started", should we expect to match
                      # a call?  (This happens when we abort due to bad output
                      # data, so we want to match the call to "printf" though
                      # we don't have graph data for "printf" itself.)
  finalCrash = True; # are we still looking for the final crash?
  frames = [];
  prevEntry = None;
  for (func, line, paths, finalPath, cc, bbc) in localData:
    if(line < 0):
      if(started):
        print >> stderr, ("ERROR: missing stack data after first data frame");
        exit(1);
      else:
        expectCall = True;
        continue;
      #end if
    #end if
    started = True;

    fId = find_function_id(G, func);
    if(fId == None):
      print >> stderr, ("Unable to find graphml id for function '" + \
                        func + "'");
      exit(1);
    #end if

    possibleFailNodes = set(find_possible_match_nodes(G, line, fId));
    if(len(possibleFailNodes) == 0):
      print >> stderr, ("ERROR: unable to match failure point for line '" + \
                        str(line) + "'");
      exit(1);
    #end if

    toStore = None;
    if(finalCrash == True):
      # if we've skipped over some frames that we don't plan to match on, we
      # expect to match a call site
      # however, even then we don't have a graphml id for the call target, so
      # we match any call site
      crashNodes = _filterToCalls(G, possibleFailNodes) if expectCall \
                                                        else possibleFailNodes;

      toStore = (crashNodes, None);
      finalCrash = False;
    else:
      if(prevEntry == None or not expectCall):
        print >> stderr, ("ERROR: internal error tracking entry nodes for " + \
                          "previous stack frame.  Line: " + str(line));
        exit(1);
      #end if

      # since it's not the final crashing location, the match should be a call
      # to the appropriate function
      realFailNodes = _filterToCalls(G, possibleFailNodes, prevEntry);
      if(len(realFailNodes) < 1):
        print >> stderr, ("ERROR: nodes but no call matches crashing line: " + \
                          str(line));
        exit(1);
      #end if

      toStore = (realFailNodes, prevEntry);
    #end if

    # get local CC and BBC data for this frame
    frameBBCmetadata = bbcMetadata.get(func, {});
    frameCCmetadata = ccMetadata.get(func, {});
    (yesBBC, noBBC) = _matchCSILabelMetadata(frameBBCmetadata, bbc, "BBC") \
                      if EXTRACT_BBC else (set([]), set([]));
    (yesCC, noCC) = _matchCSILabelMetadata(frameCCmetadata, cc, "CC") \
                    if EXTRACT_CC else (set([]), set([]));
    yesLabels = yesBBC | yesCC;
    noLabels = noBBC | noCC;
    if(len(yesLabels & noLabels) != 0):
      print >> stderr, ("ERROR: a local label is both 'yes' and 'no'!  " + \
                        str(yesLabels & noLabels));
      exit(1);
    #end if

    # translate CSI labels into graphml nodes
    funcMap = {fId : (None, yesLabels, noLabels)};
    (yesNodeSets, noNodeSets) = _funcYesNoDataToNodes(G, funcMap);

    assert(toStore and len(toStore) == 2);
    frames.append((toStore[0], toStore[1], yesNodeSets, noNodeSets));

    prevEntry = set([find_function_entry(G, fId)]);
    expectCall = True;
  #end for

  if(finalCrash == None):
    print >> stderr, ("ERROR: can't match stack with no failure data");
    exit(1);
  #end if

  return(frames);
#end: matchStackData

"""
_matchCSILabelMetadata(): Extract metadata for a specific function, and print a
warning if it is not found.
@param metadataMap the mapping from indices to metadata (i.e., already at
                   function level).  Only the first part of the mapped-to tuple
                   (the csi label in the graphml) is accessed.
   => {index : (csi-label, ...)}
@param dynamicVals the dynamic values read from failure data
   => [bool]
@param mdType the name of the metadata type (for printing error messages)
@return two sets of matching labels (each possibly empty)
   => ({yesNode}, {noNode})
NOTE: this function will exit the whole program prematurely if the metadataMap
      is not of the same size as dynamicVals
"""
def _matchCSILabelMetadata(metadataMap, dynamicVals, mdType):
  yesLabels = set([]);
  noLabels = set([]);

  for i in range(len(dynamicVals)):
    dynamicVal = dynamicVals[i];
    if(dynamicVal not in [True, False]):
      continue;

    indexMetadata = metadataMap.get(i, None);
    if(indexMetadata == None or \
       len(indexMetadata) < 1 or \
       indexMetadata[0] == None):
      print >> stderr, ("ERROR: size of dynamic data and metadata " + \
                        mdType + "mismatch:");
      print >> stderr, ("dynamic (" + str(len(dynamicVals)) + ")");
      print >> stderr, ("metadata: " + str(metadataMap.keys()));
      exit(1);
    #end if

    (yesLabels if dynamicVal else noLabels).add(indexMetadata[0]);
  #end for

  return(yesLabels, noLabels);
#end: _matchCSILabelMetadata

"""
_getDynamicDataFuncMap(): Match dynamic data to metadata and reformat into a
nicer form for matching with graph nodes.
@param G the graph
@param globalData the global failure data
   => {func-name : (fn-cov-bool, [call-cov-bool], [bb-cov-bool])}
@param bbcMetadata metadata for basic block coverage
   => {func-name : {index : (csi-label, [line-num])}}
@param ccMetadata metadata for call-site coverage
   => {func-name : {index : (csi-label, line-num, call-name)}}
@return a function-to-global-data mapping
   => {func-id : (fnCovValue, {yesLabels}, {noLabels})}
"""
def _getDynamicDataFuncMap(G, globalData, bbcMetadata, ccMetadata):
  funcMap = {};

  for (funcName, (fcVal, ccVals, bbcVals)) in globalData.items():
    funcBBCmetadata = bbcMetadata.get(funcName, {});
    funcCCmetadata = ccMetadata.get(funcName, {});
    fId = find_function_id(G, funcName);
    if(fId == None):
      print >> stderr, ("ERROR: Unable to find graphml id for function '" + \
                        funcName + "'");
      exit(1);
    elif(fId in funcMap):
      print >> stderr, ("ERROR: duplicate function name in global data '" + \
                        funcName + "'");
      exit(1);
    #end if

    (yesBBC, noBBC) = _matchCSILabelMetadata(funcBBCmetadata, bbcVals, "BBC") \
                      if EXTRACT_BBC else (set([]), set([]));
    (yesCC, noCC) = _matchCSILabelMetadata(funcCCmetadata, ccVals, "CC") \
                    if EXTRACT_CC else (set([]), set([]));

    yesLabels = yesBBC | yesCC;
    noLabels = noBBC | noCC;
    if(len(yesLabels & noLabels) != 0):
      print >> stderr, ("ERROR: a label is both 'yes' and 'no'!  " + \
                        str(yesLabels & noLabels));
      exit(1);
    #end if
    funcMap[fId] = (fcVal if EXTRACT_FC else None,
                    yesLabels,
                    noLabels);
  #end for

  return(funcMap);
#end: _getDynamicDataFuncMap

"""
_funcYesNoDataToNodes(): Translate the obsYes/No data in funcMap (currently at
the level of CSI labels) into graph nodes.
@param G the graph
@param funcMap the mapping from function id to obsYes/No data
   => {funcId : (fcVal, trueCovLabels, falseCovLabels)}
@return a pair of set of sets indicating the "yes" and "no" nodes from G
   => (({yesNode}, ...), ({noNode}, ...))
        Note that everything is a set: in the case of ambiguity, we return all
        possible nodes that match each piece of data.
NOTE: For local data, use just a single funcId in the map, and fcVal=None (this
will make fcVal be ignored, and only match to the provided function's nodes)
"""
def _funcYesNoDataToNodes(G, funcMap):
  yesNodeSets = [];
  noNodeSets = [];

  # stash already-seen pairings to notice duplication and/or ambiguity in labels
  # {(fId, label)}
  alreadySeen = set([]);

  for (n, attr) in G.nodes_iter(data=True):
    nFuncId = function_id(n);
    nFuncDynamicData = funcMap.get(nFuncId, None);
    if(nFuncDynamicData == None):
      continue;
    (nFuncFC, nFuncTrueLabels, nFuncFalseLabels) = nFuncDynamicData;

    if(attr.get("kind", "") == "entry" and nFuncFC in [True, False]):
      (yesNodeSets if nFuncFC else noNodeSets).append(set([n]));

    nLabel = attr.get("csi-label", None);
    if(nLabel == None):
      continue;
    if((nFuncId, nLabel) in alreadySeen):
      print >> stderr, ("ERROR: ambiguity/duplication for label '" + \
                        nLabel + "'");
      exit(1);
    else:
      alreadySeen.add((nFuncId, nLabel));
    #end if

    # we should have already verified that the label sets are disjoint, but, for
    # safety, we'll check against both, so we get an "unsat" during later
    # analysis if a node is both 'yes' and 'no'
    if(nLabel in nFuncTrueLabels):
      yesNodeSets.append(set([n]));
    if(nLabel in nFuncFalseLabels):
      noNodeSets.append(set([n]));
  #end for

  return(tuple(yesNodeSets), tuple(noNodeSets));
#end: _funcYesNoDataToNodes

"""
matchGlobalData(): Match global failure data to the graphml.  This function
provides the information necessary for the "obsYes" and "obsNo" fields of the
JSON input file.
@param G the graph
@param globalData the global failure data
   => {func-name : (fn-cov-bool, [call-cov-bool], [bb-cov-bool])}
@param bbcMetadata metadata for basic block coverage
   => {func-name : {index : (csi-label, [line-num])}}
@param ccMetadata metadata for call-site coverage
   => {func-name : {index : (csi-label, line-num, call-name)}}
@return all of the global data in terms of G.ndoes:
   => (({yesNode}, ...), ({noNode}, ...))
        Note that everything is a set: in the case of ambiguity, we return all
        possible nodes that match each piece of data.
"""
def matchGlobalData(G, globalData, bbcMetadata, ccMetadata):
  # funcMap type is {funcId : (fcVal, trueCovLabels, falseCovLabels)}
  funcMap = _getDynamicDataFuncMap(G, globalData, bbcMetadata, ccMetadata);
  return(_funcYesNoDataToNodes(G, funcMap));
#end: matchGlobalData

"""
appendYesNoToJson(): Add obsYes and obsNo data to an existing to-be-json
dictionary.
@param yesSets a list of sets of obsYes entries
@param noSets a list of sets of obsNo entries
@param jsonStructure a dictionary in which to add the yesSets and noSets
NOTE: jsonStructure is *modified* by this call
"""
def appendYesNoToJson(yesSets, noSets, jsonStructure):
  if(len(yesSets) > 0):
    yesData = [];
    for nodeSet in yesSets:
      yesData.append({"reliable" : False, \
                      "entries" : [list(nodeSet)]});
    #end for
    jsonStructure["obsYes"] = yesData;
  #end if

  if(len(noSets) > 0):
    noData = [];
    for nodeSet in noSets:
      noData.append(list(nodeSet));
    #end for
    jsonStructure["obsNo"] = noData;
  #end if
#end: appendYesNoToJson

"""
writeJSON(): Write out the local and global failure data as JSON for the
execution recovery analysis.
@param localData the local failure data, as extracted by matchStackData()
@param globalData the global failure data, as extracted by matchGlobalData()
@param outFile the output JSON file (created or overwritten)
"""
def writeJSON(localData, globalData, outFile):
  jsonData = {};

  if(len(localData) < 1):
    print >> stderr, ("ERROR: internal: no crash information in local data!");
    exit(1);
  elif(localData[0][0] == None or localData[0][1] != None):
    print >> stderr, ("ERROR: invalid crash information in local data:");
    print >> stderr, (localData[0]);
    exit(1);
  #end if
  stackData = [];
  for (callNodes, entryNodes, yesSets, noSets) in reversed(localData[1:]):
    thisFrame = {"call"  : list(callNodes), "entry" : list(entryNodes)};
    appendYesNoToJson(yesSets, noSets, thisFrame);
    stackData.append(thisFrame);
  #end for

  (crashNodes, crashEntries, crashYes, crashNo) = localData[0];
  assert crashNodes and len(crashNodes) > 0 and not crashEntries;
  crashFrame = {"crash" : list(crashNodes)};
  appendYesNoToJson(crashYes, crashNo, crashFrame);
  stackData.append(crashFrame);
  jsonData["crashstack"] = stackData;

  (yesNodeSets, noNodeSets) = globalData;
  appendYesNoToJson(yesNodeSets, noNodeSets, jsonData);

  with open(outFile, "w") as fp:
    json.dump(jsonData, fp);
#end: writeJSON


"""
main(): This is main.  It calls all the other functions for a while and then
exits.
"""
def main():
  if(len(argv) != 8):
    print >> stderr, ("Usage: " + argv[0] + " graph local-data global-data cc-metadata bb-metadata pt-metadata output-file");
    exit(1);
  #end if
  clock = CSIClock();
  print("Reading graph...");
  G = read_graph(argv[1]);

  clock.takeSplit();
  print("Reading dynamic failure data files...");
  localData = read_local_data(argv[2]);
  globalData = read_global_data(argv[3]);
  if(FILTER_DEBUG):
    print >> stderr, ("local data = " + str(localData));
    print >> stderr, ("global data = " + str(globalData));
  #end if

  clock.takeSplit();
  print("Reading metadata files...");
  bbcMetadata = read_bbc_metadata(argv[5]);
  ccMetadata = read_cc_metadata(argv[4]);
  ptMetadata = read_pt_metadata(argv[6]);
  if(FILTER_DEBUG):
    print >> stderr, ("BBC metadata = " + str(bbcMetadata));
    print >> stderr, ("CC metadata = " + str(ccMetadata));
    print >> stderr, ("PT metadata = " + str(ptMetadata));
  #end if

  clock.takeSplit();
  print("Matching local failure data...");
  matchedLocalData = matchStackData(G, localData, \
                               bbcMetadata, ccMetadata, ptMetadata);
  if(FILTER_DEBUG):
    print >> stderr, ("matched local data = " + str(matchedLocalData));

  clock.takeSplit();
  print("Matching global failure data...");
  matchedGlobalData = matchGlobalData(G, globalData, bbcMetadata, ccMetadata);
  if(FILTER_DEBUG):
    print >> stderr, ("matched global data = " + str(matchedGlobalData));

  clock.takeSplit();
  print("Writing failure data as JSON...");
  writeJSON(matchedLocalData, matchedGlobalData, argv[7]);

  clock.takeSplit();
#end: main

if __name__ == '__main__':
  main()
