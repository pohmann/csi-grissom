package svpaserver;

import java.lang.UnsupportedOperationException;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Scanner;

import com.google.common.collect.ImmutableList;
import org.apache.commons.lang3.tuple.ImmutablePair;

import automata.AutomataException;
import automata.svpa.Call;
import automata.svpa.Internal;
import automata.svpa.Return;
import automata.svpa.SVPA;
import automata.svpa.SVPAMove;
import automata.svpa.TaggedSymbol;
import automata.svpa.TaggedSymbol.SymbolTag;
import theory.BooleanAlgebra;
import theory.characters.BinaryCharPred;
import theory.characters.CharPred;
import theory.characters.ICharPred;
import theory.characters.StdCharPred;
import theory.intervals.EqualitySolver;
import theory.intervals.UnaryCharIntervalSolver;
import utilities.Pair;

public class SVPAServer {
  private static final String PROMPT = ">> ";
  private static final String[] KEYREGEXES = {"end", "true", "false",
                                              "e", "i", "c", "r", "\\*",
                                              "obsno.*", "~.*"};
  
  // the '*' predicate for returns (not present in StdCharPred)
  // TODO: consider pushing into symbolicautomata library, though I'm not sure
  //       if others would make much use of this.
  private final static CharPred TRUE_RET = new CharPred(CharPred.MIN_CHAR,
                                                        CharPred.MAX_CHAR,
                                                        true);

  // tracking the current automaton (all constraints so far are intersected in)
  // also keep a backup for probing
  private SVPA<ICharPred, Character> automaton;
  private SVPA<ICharPred, Character> stashedAutomaton;
  private EqualitySolver ba;

  // outside users talk in strings, we store nodes as Characters (due to the
  // theory we are using for the SymbolicAutomata library)
  private Map<String, Character> nodeNameMap;
  private Map<Character, String> nameNodeMap;
  private Character nextChar;

  // these are temporarily used when creating the CFG: their values are
  // meaningless outside of that context
  private Map<Character, Integer> nodeStateMap;
  private Integer nextState;

  private boolean includesCFG;
  private boolean includesCrashStack;

  /**
   * SVPAServer() is the construtor.  It constructs.
   */
  public SVPAServer(){
    automaton = null;
    stashedAutomaton = null;
    ba = new EqualitySolver();

    nodeNameMap = new HashMap<String, Character>();
    nameNodeMap = new HashMap<Character, String>();
    nextChar = Character.MIN_VALUE;

    nodeStateMap = null;
    nextState = null;

    includesCFG = false;
    includesCrashStack = false;
  }

  public static void main(String[] args){
    SVPAServer runner = new SVPAServer();

    try(Scanner s = new Scanner(System.in)){
      System.out.print(SVPAServer.PROMPT);

      while(s.hasNextLine()){
        String command = s.nextLine().trim();

        switch(command){
          case "":
            break;
          case "cfg":
            runner.readCFGAutomaton(s);
            break;
          case "stack":
            runner.readStackAutomaton(s);
            break;
          case "constraint":
            runner.readGenericAutomaton(s);
            break;
          case "witness":
            runner.getAndPrintWitness();
            break;
          case "empty":
            runner.getAndPrintEmpty();
            break;

          case "probe witness":
            runner.stash();
            runner.readGenericAutomaton(s);
            runner.getAndPrintWitness();
            runner.restore();
            break;
          case "probe empty":
            runner.stash();
            runner.readGenericAutomaton(s);
            runner.getAndPrintEmpty();
            runner.restore();
            break;

          default:
            errorAndAbort("invalid command '" + command + "'");
        }

        System.out.print(SVPAServer.PROMPT);
      }
    }
    catch(Exception e){
      errorAndAbort("something went terribly wrong", e);
    }
  }

  public void stash(){
    this.stashedAutomaton = this.automaton;
  }

  public void restore(){
    if(this.stashedAutomaton == null)
      errorAndAbort("Attempt to restore when no automaton was stashed");

    this.automaton = this.stashedAutomaton;
    this.stashedAutomaton = null;
  }

  private void updateAutomaton(SVPA<ICharPred, Character> update){
    if(this.automaton == null)
      this.automaton = update;
    else
      this.automaton = this.automaton.intersectionWith(update, this.ba);
  }

  private void readCFGAutomaton(Scanner s){
    if(this.includesCFG)
      errorAndAbort("multiple CFGs provided");
    this.includesCFG = true;

    Collection<SVPAMove<ICharPred, Character>> transitions =
       new LinkedList<SVPAMove<ICharPred, Character>>();

    Integer initialState = null;
    this.nodeStateMap = new HashMap<Character, Integer>();
    this.nextState = 1;

    while(s.hasNextLine()){
      String line = s.nextLine().trim();

      boolean gotEnd = line.equalsIgnoreCase("END");
      if(gotEnd && initialState != null){
        SVPA<ICharPred, Character> cfgAutomaton = null;
        try{
          cfgAutomaton = SVPA.MkSVPA(transitions, Arrays.asList(initialState),
                                     this.nodeStateMap.values(), this.ba);
        }
        catch(Exception e){
          errorAndAbort("Couldn't make the CFG automaton!", e);
        }

        // clear the junk (these are meaningless outside this method)
        this.nodeStateMap = null;
        this.nextState = null;

        this.updateAutomaton(cfgAutomaton);
        return;
      }
      else if(gotEnd){
        errorAndAbort("unexpected 'END' before specifying entry " +
                      "node in CFG data.");
      }

      String[] lineParts = line.split(",");
      if(lineParts.length < 2 || lineParts.length > 4)
        errorAndAbort("invalid line in CFG data:\n" + line);

      Character from = null;
      Integer fromState = null;
      Character to = null;
      Integer toState = null;
      Character onStack = null;
      Integer onStackState = null;
      switch(lineParts.length){
        case 4:
          onStack = this.getOrAddNode(lineParts[3].trim());
          onStackState = this.getOrAddState(onStack);
        case 3:
          to = this.getOrAddNode(lineParts[2].trim());
          toState = this.getOrAddState(to);
        case 2:
          from = this.getOrAddNode(lineParts[1].trim());
          fromState = this.getOrAddState(from);
          break;
        default:
          errorAndAbort("critical late invalid CFG line:\n");
      }

      switch(lineParts[0].trim().toLowerCase()){
        case "e":
          if(initialState != null)
            errorAndAbort("multiple entry nodes defined!\nSecond was: " + line);

          if(from == null || to != null || onStack != null)
            errorAndAbort("invalid 'entry' line in CFG:\n" + line);

          initialState = 0;
          transitions.add(new Internal<ICharPred, Character>(0, fromState,
                                                           new CharPred(from)));
          break;
        case "i":
          if(from == null || to == null || onStack != null)
            errorAndAbort("invalid 'internal' line in CFG:\n" + line);

          transitions.add(new Internal<ICharPred, Character>(fromState, toState,
                                                             new CharPred(to)));
          break;
        case "c":
          if(from == null || to == null || onStack != null)
            errorAndAbort("invalid 'call' line in CFG:\n" + line);

          transitions.add(new Call<ICharPred, Character>(fromState, toState,
                                                         0,
                                                         new CharPred(from)));
          break;
        case "r":
          if(from == null || to == null || onStack == null)
            errorAndAbort("invalid 'return' line in CFG:\n" + line);

          transitions.add(new Return<ICharPred, Character>(fromState,
                                 toState,
                                 0,
                                 new BinaryCharPred(new CharPred(onStack,
                                                                 true),
                                                    true)));
          
          break;
        default:
          errorAndAbort("invalid cfg line (wrong # parts):\n" + line);
      }
    }

    errorAndAbort("end of input reached while reading cfg");
  }

  /**
   * getOrAddState() gets the integer state number for the node specified
   * (adding it if "node" is new).
   * WARNING: This method should not be used by *anyone* except
   * readCFGAutomaton().  It is specific to that context.
   */
  private int getOrAddState(Character node){
    if(node == null)
      errorAndAbort("invalid empty node name");

    if(!this.nodeStateMap.containsKey(node))
      this.nodeStateMap.put(node, this.nextState++);

    return(this.nodeStateMap.get(node));
  }

  private void readStackAutomaton(Scanner s){
    if(this.includesCrashStack)
      errorAndAbort("multiple crashing stacks provided");
    this.includesCrashStack = true;

    List<Pair<Character, Character>> crashStack =
           new LinkedList<Pair<Character, Character>>();

    boolean expectEnd = false;
    while(s.hasNextLine()){
      String line = s.nextLine().trim();

      boolean gotEnd = line.equalsIgnoreCase("END");
      if(gotEnd && expectEnd){
        SVPA<ICharPred, Character> stackAutomaton = null;
        try{
          BinaryCharPred equality = new BinaryCharPred(StdCharPred.TRUE, false);
          stackAutomaton = getCrashStackAutomata(crashStack, StdCharPred.TRUE,
                                                 StdCharPred.TRUE,
                                                 equality, this.ba);
        }
        catch(Exception e){
          errorAndAbort("Couldn't make the stack automaton!", e);
        }

        this.updateAutomaton(stackAutomaton);
        return;
      }
      else if(expectEnd){
        errorAndAbort("missing expected 'END' after crash stack." +
                      "Instead found:\n" + line);
      }
      else if(gotEnd){
        errorAndAbort("unexpected 'END' before final frame in crash stack.");
      }

      String[] lineParts = line.split(",");
      Character first = null;
      Character second = null;
      switch(lineParts.length){
        case 1:
          first = getOrAddNode(lineParts[0].trim());
          expectEnd = true;
          break;
        case 2:
          first = getOrAddNode(lineParts[0].trim());
          second = getOrAddNode(lineParts[1].trim());
          break;
        default:
          errorAndAbort("invalid crash stack line (wrong # parts):\n" + line);
      }
      crashStack.add(new Pair<Character, Character>(first, second));
    }

    errorAndAbort("end of input reached while reading stack");
  }

  /**
   * readGenericAutomaton() reads a generic SVPA constraint from the input.
   *
   * Format Grammar:
   *   S          ::= obsNo,cfg_node | ENTRY_LIST
   *   ENTRY_LIST ::= ENTRY '\n' ENTRY_LIST | epsilon
   *   ENTRY      ::= t,TRANS | i,state | f,state
   *   TRANS      ::= TYPE,from_state,to_state,COND
   *   TYPE       ::= i | c | r
   *   COND       ::= cfg_node | '~' cfg_node | '*'
   *
   * NOTE: this is a very constrained grammar, and does not allow anywhere near
   *       the full power of SVPAs.  It is currently enough to express obsNo and
   *       obsYes, but can't represent much where calls/returns matter.
   *       Specifically, it does not allow you to specify:
   *         (1) the stack state for call/return transitions
   *         (2) transitions on complex conditions; currently only single
   *             characters or '*' can be used
   * @param s the input Scanner to read from
   */
  private void readGenericAutomaton(Scanner s){
    if(!this.includesCFG || !this.includesCrashStack){
      errorAndAbort("both CFG and crash stack must be provided before " +
                    "other constraints");
    }

    if(!s.hasNextLine())
      errorAndAbort("no input provided while reading generic automaton");
    String line = s.nextLine().trim();

    if(line.length() >= 6 && line.substring(0, 6).equalsIgnoreCase("obsNo,")){
      this.handleObsNoLine(line);

      if(!s.hasNextLine() || !s.nextLine().trim().equalsIgnoreCase("END"))
        errorAndAbort("expected 'END' after obsNo automaton");
      return;
    }

    Collection<SVPAMove<ICharPred, Character>> transitions =
       new LinkedList<SVPAMove<ICharPred, Character>>();
    Collection<Integer> initialStates = new LinkedList<Integer>();
    Collection<Integer> finalStates = new LinkedList<Integer>();

    boolean atLeastOne = false;
    while(s.hasNextLine()){
      // we already got the very first line (above), so read a line only on
      // subsequent iterations
      // NOTE: the "while" above should probably be a "do-while", but one line
      //       is not sufficient to define an automaton anyway, so it's OK as-is
      if(atLeastOne)
        line = s.nextLine().trim();
      else
        atLeastOne = true;

      boolean gotEnd = line.equalsIgnoreCase("END");
      if(gotEnd && transitions.size() > 0 &&
         initialStates.size() > 0 && finalStates.size() > 0){
        // TODO: assert all states used in "transitions" is a superset of
        //       initialStates and a superset of finalStates

        SVPA<ICharPred, Character> thisAutomaton = null;
        try{
          thisAutomaton = SVPA.MkSVPA(transitions, initialStates,
                                      finalStates, this.ba);
        }
        catch(Exception e){
          errorAndAbort("Couldn't make generic automaton!", e);
        }

        this.updateAutomaton(thisAutomaton);
        return;
      }
      else if(gotEnd){
        errorAndAbort("unexpected 'END' with incomplete generic automaton");
      }

      String[] lineParts = line.split(",");
      switch(lineParts[0]){
        case "":
          break;
        case "i":
        case "f": {
          boolean isInitial = lineParts[0].equalsIgnoreCase("i");
          String type = (isInitial ? "initial" : "final");
          if(lineParts.length != 2)
            errorAndAbort("invalid " + type + " state line:\n" + line);

          (isInitial ? initialStates : finalStates).add(
               SVPAServer.stringToInt(lineParts[1],
                                      "bad " + type + " state:\n" + line));
          break;
        }
        case "t": {
          if(lineParts.length != 5)
            errorAndAbort("invalid SVPA transition line:\n" + line);

          String type = lineParts[1];
          int fromState = SVPAServer.stringToInt(lineParts[2],
                                                 "bad 'from' state:\n" + line);
          int toState = SVPAServer.stringToInt(lineParts[3],
                                               "bad 'to' state:\n" + line);
          String cfgNode = lineParts[4];

          switch(type.trim().toLowerCase()){
            case "i":
              transitions.add(new Internal<ICharPred, Character>(
                                     fromState, toState,
                                     genericPredFromString(cfgNode, false)));
              break;
            case "c":
              transitions.add(new Call<ICharPred, Character>(
                                     fromState, toState, 0,
                                     genericPredFromString(cfgNode, false)));
              break;
            case "r":
              transitions.add(new Return<ICharPred, Character>(
                                     fromState, toState, 0,
                                     genericPredFromString(cfgNode, true)));
              break;
            default:
              errorAndAbort("invalid transition type in line:\n" + line + "\n" +
                        "Expected 'i' (internal), 'c' (call), or " +
                        "'r' (return)");
          }
          break;
        }
        default:
          errorAndAbort("invalid generic automaton line:\n" + line + "\n" +
                        "Expected 't' (transition), 'i' (initial), or " +
                        "'f' (final)");
      }
    }

    errorAndAbort("end of input reached while reading generic automaton");
  }

  /**
   * genericPredFromString() generates the appropriate char-theory predicate
   * based on the provided string (and whether or not it should be a return
   * predicate).
   * NOTE: this method is only intended to be used by readGenericAutomaton().
   *       The expected string format is very specific, as follows:
   *       "*" -> the TRUE predicate
   *       "~.*" -> an inverted predicate
   *       REST -> you may only specify ONE SINGLE node from the CFG
   *
   * @param str the string containing the predicate data
   * @param returnPred whether or not we should generate a return predicate
   * @return the predicate
   */
  private CharPred genericPredFromString(String str, boolean returnPred){
    if(str.equals("*")){
      return(SVPAServer.allCharsExcept(null, returnPred));
    }
    else{
      boolean inverted = false;
      if(str.length() > 0 && str.charAt(0) == '~'){
        inverted = true;
        str = str.substring(1);
      }

      Character svpaNode = getOrAddNode(str);
      if(inverted)
        return(allCharsExcept(svpaNode, returnPred));
      else
        return(new CharPred(svpaNode, returnPred));
    }
  }

  /**
   * stringToInt() is simply a wrapper around Integer.parseInt() that
   * appropriately reports error messages, rather than throwing an exception.
   *
   * @param s the String to convert to an int
   * @param errorMessage the error message to print on conversion failure
   * @return the integer represented by s
   */
  private static int stringToInt(String s, String errorMessage){
    try{
      return(Integer.parseInt(s));
    }
    catch(NumberFormatException e){
      errorAndAbort("cannot convert string to int: " + errorMessage, e);
    }

    errorAndAbort("critical error converting string to int");
    return(-1);
  }

  /**
   * handleObsNoLine() provides special handling for obsNo constraints
   * (supporting the "short-hand" form, as they can also be specified as general
   * SVPA constraints).  The form is:
   *   obsNo,CFG_NODE
   *
   * @param line a String representing the obsNo constraint
   */
  private void handleObsNoLine(String line){
    String[] lineParts = line.split(",");
    assert lineParts[0].equalsIgnoreCase("obsNo");
    if(lineParts.length != 2)
      errorAndAbort("invalid obsNo entry:\n" + line);

    Collection<SVPAMove<ICharPred, Character>> transitions =
       new LinkedList<SVPAMove<ICharPred, Character>>();

    // predicates to accept all characters except the "obsNo" node
    Character entry = getOrAddNode(lineParts[1].trim());
    final CharPred withoutEntry = allCharsExcept(entry, false);
    final CharPred withoutEntryRet = allCharsExcept(entry, true);

    transitions.add(new Internal<ICharPred, Character>(0, 0, withoutEntry));
    transitions.add(new Call<ICharPred, Character>(0, 0, 0, withoutEntry));
    transitions.add(new Return<ICharPred, Character>(0, 0, 0, withoutEntryRet));

    SVPA<ICharPred, Character> obsNoAutomaton = null;
    try{
      obsNoAutomaton = SVPA.MkSVPA(transitions, Arrays.asList(0),
                                   Arrays.asList(0), this.ba);
    }
    catch(Exception e){
      errorAndAbort("Couldn't make obsNo automaton!", e);
    }

    this.updateAutomaton(obsNoAutomaton);
  }

  /**
   * allCharsExcept() builds a CharPred predicate that accepts any character
   * except for "excluded".  If "excluded" is null, it returns the TRUE
   * predicate.
   *
   * @param excluded the character to exclude
   * @param returnPred whether or not we should generate a return predicate
   * @return the predicate
   */
  private static CharPred allCharsExcept(Character excluded,
                                         boolean returnPred){
    if(excluded == null){
      if(returnPred)
        return(SVPAServer.TRUE_RET);
      else
        return(StdCharPred.TRUE);
    }

    // weird stuff to avoid Java errors for increment/decrementing chars
    char prev = excluded; prev--;
    char next = excluded; next++;

    CharPred result;
    switch(excluded.charValue()){
      case CharPred.MIN_CHAR:
        result = new CharPred(next, CharPred.MAX_CHAR, returnPred);
        break;
      case CharPred.MAX_CHAR:
        result = new CharPred(CharPred.MIN_CHAR, prev, returnPred);
        break;
      default:
        result = new CharPred(ImmutableList.of(
                                 ImmutablePair.of(CharPred.MIN_CHAR, prev),
                                 ImmutablePair.of(next, CharPred.MAX_CHAR)),
                              returnPred);
        break;
    }
    return(result);
  }


  private void getAndPrintWitness(){
    System.out.println(getWitness());
  }

  private void getAndPrintEmpty(){
    System.out.println(this.isEmpty() ? "true" : "false");
  }

  public String getWitness(){
    if(this.automaton.isEmpty){
      return("{{ NO WITNESS }}");
    }
    else{
      List<TaggedSymbol<Character>> witness =
         this.automaton.getWitness(this.ba);
      String result = "[[";
      for(TaggedSymbol<Character> c : witness){
        result += " ";
        if(c.tag == TaggedSymbol.SymbolTag.Call)
          result += "<";
        result += this.getName(c.input);
        if(c.tag == TaggedSymbol.SymbolTag.Return)
          result += ">";
      }
      result += " ]]";
      return(result);
    }
  }

  public boolean isEmpty(){
    return(this.automaton.isEmpty);
  }


  private Character getOrAddNode(String name){
    if(name == null || name.isEmpty())
      errorAndAbort("invalid empty node name");
    String lowerName = name.toLowerCase();
    for(String regex : SVPAServer.KEYREGEXES){
      if(lowerName.matches(regex)){
        errorAndAbort("invalid node name '" + name + "' matches keyword '" +
                      regex + "'");
      }
    }

    if(!this.nodeNameMap.containsKey(name)){
      Character thisChar = this.nextChar++;
      this.nodeNameMap.put(name, thisChar);
      this.nameNodeMap.put(thisChar, name);
    }

    return(this.getNode(name));
  }

  private Character getNode(String name){
    Character result = this.nodeNameMap.get(name);
    if(result == null){
      errorAndAbort("attempt to get non-existant node (" +
                    ((name == null) ? "null" : name) + ")");
    }
    return(result);
  }

  private String getName(Character node){
    String result = this.nameNodeMap.get(node);
    if(result == null){
      errorAndAbort("attempt to get node for non-existant name (" +
                    ((node == null) ? "null" : node) + ")");
    }
    return(result);
  }


  /**
   * getCrashStackAutomata() constructs an SVPA for the crashing stack.  This
   * is a sequence of call transitions (matching the call stack) with
   * well-matched calls/returns in-between.
   *
   * @param crashStack the crashing stack.  Represented as pairs of
   *        <CallSiteNode, CalledEntryNode>.  Note that the final crash point
   *        is not a call, and, hence, should have a null CalledEntryNode.
   * @param internalPred the predicate to use for the well-matched internal
   *                     transitions
   * @param callPred the predicate to use for well-matched legal calls
   * @param returnPred the predicate to use for well-matched legal returns
   * @param ba the boolean algebra object to use
   * @return an SVPA representing all runs matching the crashing stack config
   * @throws AutomataException if an error occurs trying to allocate
   */
  private static SVPA<ICharPred, Character> getCrashStackAutomata(
       List<Pair<Character, Character>> crashStack,
       CharPred internalPred,
       CharPred callPred,
       BinaryCharPred returnPred,
       BooleanAlgebra<ICharPred, Character> ba) throws AutomataException {
    if(crashStack.size() < 1)
      throw new IllegalArgumentException(
         "Crash stack must contain at least one element");

    Collection<SVPAMove<ICharPred, Character>> transitions =
       new LinkedList<SVPAMove<ICharPred, Character>>();

    int currentState = 0;
    Iterator<Pair<Character, Character>> stackIter = crashStack.iterator();
    assert stackIter.hasNext();
    while(stackIter.hasNext()){
      int unmatchedState = currentState + 1;
      concatWellMatched(transitions, currentState, unmatchedState,
                        internalPred, callPred, returnPred);

      int nextState = currentState + 2;
      Pair<Character, Character> crashPoint = stackIter.next();
      CharPred callSite = new CharPred(crashPoint.first);
      Character calledEntry = crashPoint.second;
      if(stackIter.hasNext()){
        // within the stack, all crash points are calls
        assert calledEntry != null;
        CharPred calledPred = new CharPred(calledEntry);

        transitions.add(new Call<ICharPred, Character>(currentState,
                                                       nextState,
                                                       1,
                                                       callSite));

        int afterCallState = nextState + 1;
        transitions.add(new Internal<ICharPred, Character>(nextState,
                                                           afterCallState,
                                                           calledPred));
        nextState = afterCallState;
      }
      else{
        // the actual final crash point is *not* a call
        assert calledEntry == null;
        transitions.add(new Internal<ICharPred, Character>(currentState,
                                                           nextState,
                                                           callSite));
      }

      currentState = nextState;
    }

    return SVPA.MkSVPA(transitions, Arrays.asList(0),
                       Arrays.asList(currentState), ba);
  }

  /**
   * concatWellMatched() adds appropriate transitions to put a "well-matched"
   * automaton at/from "matchedState".
   * 
   * @param transitions the list of transitions that will become the automaton
   *                    (will be modified/extended by this function)
   * @param matchedState the state that should ensure well-matched calls.  Note
   *                     that this function will add a self-loop on
   *                     internalPred.
   * @param unmatchedState the thus-far-non-existing state to use for the
   *                       "unmatched" condition while creating the automaton
   *                       transitions.  This should be a fresh state number.
   * @param internalPred the predicate to use for the self-loop internal
   *                     transitions (for both matchedState and unmatchedState)
   * @param callPred the predicate to use for legal calls
   * @param returnPred the predicate to use for legal returns
   */
  private static void concatWellMatched(
       Collection<SVPAMove<ICharPred, Character>> transitions,
       int matchedState,
       int unmatchedState,
       CharPred internalPred,
       CharPred callPred,
       BinaryCharPred returnPred){
    transitions.add(new Internal<ICharPred, Character>(matchedState,
                                                       matchedState,
                                                       internalPred));
    transitions.add(new Internal<ICharPred, Character>(unmatchedState,
                                                       unmatchedState,
                                                       internalPred));

    transitions.add(new Call<ICharPred, Character>(matchedState,
                                                   unmatchedState,
                                                   0,
                                                   callPred));
    transitions.add(new Return<ICharPred, Character>(unmatchedState,
                                                     matchedState,
                                                     0,
                                                     returnPred));
    transitions.add(new Call<ICharPred, Character>(unmatchedState,
                                                   unmatchedState,
                                                   1,
                                                   callPred));
    transitions.add(new Return<ICharPred, Character>(unmatchedState,
                                                     unmatchedState,
                                                     1,
                                                     returnPred));
  }


  public void addCFGAutomaton(String cfgString){
    try(Scanner s = new Scanner(cfgString)){
      readCFGAutomaton(s);
    }
    catch(Exception e){
      errorAndAbort("Error reading input string for CFG automaton");
    }
  }

  public void addStackAutomaton(String stackString){
    try(Scanner s = new Scanner(stackString)){
      readStackAutomaton(s);
    }
    catch(Exception e){
      errorAndAbort("Error reading input string for stack automaton");
    }
  }

  public void addGenericAutomaton(String svpaString){
    try(Scanner s = new Scanner(svpaString)){
      readGenericAutomaton(s);
    }
    catch(Exception e){
      errorAndAbort("Error reading input string for generic automaton");
    }
  }



  private static void errorAndAbort(String message){
    SVPAServer.errorAndAbort(message, null);
  }

  private static void errorAndAbort(String message, Throwable e){
    assert(message != null);
    System.err.println("ERROR: " + message);

    if(e != null)
      e.printStackTrace();

    System.exit(1);
  }
}
