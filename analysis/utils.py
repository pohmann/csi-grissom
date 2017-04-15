from csilibs.graphlibs import function_id

"""
findGraphEntry(): Search through the graph for its "entry" node.  If the graph
is intraprocedural, this is the entry of that function.  If the graph is
interprocedural, this is the entry of "main" or the explicit "program-start".
@param G the graph
@return (entry, isInterprocedural)
"""
def findGraphEntry(G):
  entries = set([]);
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "") == "entry"):
      entries.add((n, attr.get("procedure", "")));
    #end if
  #end for

  # if intraprocedural, return the lone entry node
  if(len(entries) == 1):
    return(entries.pop()[0], False);

  # see if the graph specifies its entry node directly
  explicitEntry = G.graph.get("program-start", None);
  if(explicitEntry != None):
    explicitEntry = explicitEntry.strip();
    if(explicitEntry not in G):
      print >> stderr, ("ERROR: expliti entry node not present in graphml");
      exit(1);
    #end if
    return(explicitEntry, True);
  #end if

  # otherwise, return main's entry
  mainEntry = None;
  for (n, proc) in entries:
    if(proc == "main"):
      if(mainEntry != None):
        print >> stderr, ("ERROR: multiple \"main\" functions!");
        exit(1);
      #end if
      mainEntry = n;
    #end if
  #end for
  if(mainEntry == None):
    print >> stderr, ("ERROR: no \"main\" entry or explicit " +
                      "\"program-start\" in interprocedural graph!");
    exit(1);
  #end if
  return(mainEntry, True);
#end: findGraphEntry

"""
findEntryForNode(): Find the entry of the function containing the specified node
@param G the graph
@param searchNode the node
@return the entry node for the function containing searchNode
"""
def findEntryForNode(G, searchNode):
  theEntry = None;
  for (n, attr) in G.nodes(True):
    if(attr.get("kind", "") == "entry" and
       function_id(n) == function_id(searchNode)):
      if(theEntry):
        print >> stderr, ("ERROR: multiple entries found for " + searchNode +  \
                          "'");
        exit(1);
      else:
        theEntry = n;
  #end for
  
  if(not theEntry):
    print >> stderr, ("ERROR: no entry found for node " + searchNode);
    exit(1);
  #end if
  return theEntry;
#end: findEntryForNode
