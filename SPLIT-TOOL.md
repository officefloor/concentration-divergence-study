# Split tool — an IDE refactoring that proposes where to cut

> **Status (28 October 2026). DESIGN ONLY, LATER DEVELOPMENT.** Nothing here is built, and
> nothing in the study depends on it. It records how the split cost of [`SPLIT.md`](SPLIT.md)
> would be turned into a refactoring tool, so the design is not lost while the study runs.

## Two signals

The split says three different things about a long method, and the tool surfaces them
differently:

- **Getting big, and splittable.** The method is near or over the cap and has a feasible split
  with a cheap seam. The warning carries the fix: the pieces, their inputs and outputs, the
  lines saved. A nudge that can be acted on in minutes.
- **Splittable only with a type.** No segmentation gets by with one return, but one does if a
  piece may return a record. The proposal carries the record: its fields are the values that
  cross, and the cost (three per value, `SPLIT.md`) says what the developer takes on for the
  type, the packing and the unpacking. The choice is theirs: the record, or a different cut by
  hand, or leaving the method as it is.
- **Big, and not splittable.** The method is over the cap and either no segmentation is
  feasible even with a record, or every piece is locked to the class. There is no fix to attach, and that is the
  point. Adding to this method grows something that cannot be taken apart afterwards; when the
  class's locked share is high, it is the class that is the problem. The notice says so in
  words: *this method is bound to the object's state; the next change here is a design
  decision, not an edit*. A sinew that cannot be cut is what a god method is.

## Three surfaces

| Surface | Scope | What it does |
|---|---|---|
| IDE | the method under the cursor | the facts on the fly, the proposal with names to fill in, and the not-splittable notice while the developer is still inside the method |
| Git hook | the methods the diff touches | the pass on changed files only; a warning on a touched method that is over the cap or has grown, with the proposal in the hook's output; never a word about a method the change did not touch |
| Pipeline gate | the whole repository | the ratchet: fail only on growth, a method that crossed the cap in this change or was over it and got longer; report the class-level locked share as a trend, never as a gate |

The ratchet is what makes a gate survivable on a codebase that already has long methods:
nothing that was long before fails the build, only making it longer does. It is the rule the
"new code" quality gates use, and the right one here. All three surfaces share the one pure
module below; the pass has no symbol solver, which is why it is fast enough for a hook.

Before any surface gates anything, step 14 has to show the measure separates something, the
own-class call reading (an upper bound on *locked* until the measurer records static calls)
should be tightened, and the scope is Java through the measurer.

## What it does

Every IDE can extract a method from a region the developer selects: it computes the parameters
and the return value, refuses a region with two outputs, and asks for a name. What no IDE does
is choose the region. This tool chooses it. For a method over the cap it proposes the cheapest
feasible segmentation that brings the method, and every piece, under the cap, shows each piece
with its cost, and asks the developer for one thing per piece: the name. The IDE's own Extract
Method then performs the edit and verifies it.

The division of labour is deliberate:

- **the tool proposes**: where to cut, from the statement tree and the data flow, ranked by
  benefit per unit cost;
- **the developer names**: the one judgement a machine should not make, since the name is the
  piece's meaning;
- **the IDE verifies and applies**: parameters, return, checked exceptions, order of side
  effects, and the edit itself, with its own undo.

## What the developer sees

For a method over the cap, a gutter mark and an action, *Split this method*. The action shows
the proposed pieces in place, each as a highlighted run with a one-line summary:

```
lines 48-71   24 lines   in: request, config   out: session   declares: count, buf   static            saves 23
lines 73-90   18 lines   in: session           out: -         declares: -            instance: writes cache   saves 17
remainder     19 lines                                                                instance: calls validate   was 61
```

*declares* lists the variables declared before the piece with no value or a literal one and
used only inside it. The tool moves those declarations to the top of the new method as part
of the proposal; they cost nothing and cross no seam. Left in place, the IDE would pass them
as parameters, so the move happens before the IDE's extraction is invoked.

The last column is the piece's binding (`SPLIT.md`, *Binding to the class*): *static* for a
piece that touches no field and calls none of the class's own methods, so it can be a
stateless utility and moved anywhere; *instance* with the reason for one that cannot, a field
it writes or a method of the class it calls. A piece that only reads fields is shown as
*static if passed: cfg, limit*, and accepting that form adds those fields as parameters. The
summary ends with the count: *2 of 3 pieces stay in the class*. Over a whole class the tool
reports the locked share, since a class whose long methods split only into instance pieces is
a god class rather than a collection of long methods, and splitting will not fix it.

Accepting a piece first moves its literal declarations down into the region, then opens the
IDE's Extract Method dialog with the region selected and the parameters and return already
shown, and the cursor in the name field. Declining a piece drops
it and re-solves the rest, since the cheapest segmentation without that piece may differ.
Pieces are applied one at a time, each through the IDE's refactoring, so every step is
verified and undoable on its own.

When no segmentation gets by with one return the action says so, and why: *every cut carries
two results*, or *the loop at 52-88 cannot be shortened without a second output*. If a record
would do it, the proposal is shown with the record's fields and its cost, and the developer
names the type as they name the piece. If not even that works, those are the methods that
need more than Extract Method (a parameter object, a class), and naming the reason is more
useful than a silent absence.

## How it decides

The algorithm is [`SPLIT.md`](SPLIT.md)'s, run for one method on demand:

1. **Facts.** Parse the method with JavaParser as the LiveWidth pass does (no symbol solver):
   the statement tree, each variable's reference and definition lines, its loop extent, the
   literal rule, and the data flow. In an IDE the parse is the editor's own syntax tree, and the
   same facts come from it.
2. **Candidates.** Every contiguous run of one sequence's statements, with its line count, its
   inputs and outputs, the literal declarations it takes with it, and the jump rule. Runs that
   fail feasibility are kept, with the reason, for the explanation above.
3. **Search.** The bottom-up dynamic program: cheapest worst seam such that the remainder and
   every piece end under the target, recursing into statements longer than the cap. The
   structural-only variant (whole `if`, `try` and loop statements) is solved too, and preferred
   when its cost is within one of the best, since that is where developers cut.
4. **Binding.** Each piece and the remainder are classed free, bound by reads or locked, from
   the fields referenced and the calls that resolve to the class's own methods; the IDE's
   extraction then decides static or instance, and the tool proposes the field parameters when
   they fit under the maximum inputs.
5. **Ranking.** Pieces are presented in the order a developer would apply them: the piece that
   saves most per unit cost first. The cost is the refactor cost of `SPLIT.md`, the benefit the
   lines and nesting removed (the two features Haas and Hummel found carry acceptance).

Everything numeric is a setting, with `SPLIT.md`'s defaults: the trigger and target lengths,
the minimum piece, the maximum inputs, the single output, the weights, structural-only or any
run, and whether a trailing return is allowed.

## What the IDE must still check

The tool reads syntax and lexical scope only, so it proposes and the IDE disposes. The IDE's
extraction is the authority on:

- **checked exceptions** thrown inside the piece, which need a `throws` clause;
- **the order of side effects** when an input is an object mutated inside the piece;
- **shadowing and resolution** the lexical match gets wrong (a lower-case qualified name, a
  lower-case enum constant);
- **generics and types** of the parameters and the return;
- **anything the proposal missed**: if the IDE refuses a proposed region, the tool reports the
  refusal as a reason and re-solves without that run.

A proposal the IDE refuses is a defect in the facts worth logging, since the same facts feed
the study.

## Where it would live

- **IntelliJ**: a plugin contributing an intention action and an inspection on methods over the
  cap, invoking `ExtractMethodProcessor` with the chosen range. The IDE's own analysis of
  parameters and return is what the dialog shows.
- **Eclipse**: a plugin over JDT's `ExtractMethodRefactoring`, as JDeodorant and JExtract are.
- **Language server**: a code action, *Split this method*, returning the pieces as workspace
  edits only where the server's refactoring can perform them; otherwise a diagnostic with the
  proposed ranges and the cost, for an editor to act on.
- **Command line**: the same search over a repository, writing the proposals as a report, for
  review tooling and for the study's own extract (which is where it starts).

The core is one pure module, facts in and segmentation out, shared by all four, with the
`LiveWidth` pass and `scripts/livewidth.py` as its first implementation.

## What it is not

- **Not a smell detector.** Length over the cap is the trigger; the step 13 result is that
  nothing beats it. The tool does not re-litigate that, it acts on it.
- **Not an automatic refactorer.** Every edit goes through the IDE's refactoring with the
  developer's name on it. The tool never applies a change itself.
- **Not a judge of cohesion.** It costs interface, not meaning. A piece with one parameter and
  no return can still be the wrong thing to name, and the developer declining it is the
  feedback the ranking needs.

## Open questions, and what would settle them

- **Do developers accept the proposals?** Haas and Hummel's 86% is the bar, measured the same
  way: proposals on real long methods, developers asked whether they would apply them. Their
  three decisive features (statement reduction, nesting reduction, input count) are all in the
  cost, so acceptance should be at least comparable.
- **Does the data-flow seam beat the structural cue?** Alon and Feitelson's developers cut at
  `if` and `try`. The structural-only variant is the control; if it is accepted as often and
  costs no more, the seam adds nothing in practice, whatever it adds in the measure.
- **Does a split lower the width a reader holds?** Replaying the segmentation over the facts
  gives width before and after; the claim is that the remainder's width falls to about its
  total interface. If it does not, the split moved the problem rather than reducing it.
- **What changes for AI-written code?** The same tool, the same defaults, over a corpus of
  AI-generated methods: whether more of them are infeasible under one output, and whether the
  pieces proposed carry more interface at the same length. That is the descriptive study
  `SPLIT.md` sets out, and the tool is how it would be run on code that has no reviewer.

## References

The literature is in [`SPLIT.md`](SPLIT.md), *Prior work, and the gap each leaves*. The tools
closest to this one are JDeodorant (Tsantalis & Chatzigeorgiou), JExtract (Silva, Terra &
Valente), Haas and Hummel's Teamscale suggestions, and EM-Assist (Pomian et al.), each of
which ranks candidates within a method; the difference here is the cap as a constraint and the
segmentation as the unit proposed.
