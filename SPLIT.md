# Split cost — what it takes to bring a method under the cap

> **Status (28 October 2026). EXPLORATORY, POST HOC.** Written after step 13 was read
> (PLAN.md, Amendments, 10). It records a direction, the facts it needs, the parameters it
> takes, and the literature it stands on, and step 14 is its reading. Nothing here is
> registered. It follows from [`LIVEWIDTH.md`](LIVEWIDTH.md): the facts it reads are the
> live-width facts, with the statement tree, the reference and definition lines and the
> literal rule added for it.
>
> The registered construct priced a sinew as a multiplier on complexity, and the confirmatory
> analysis showed that price wrong. What is measured here is the sinew itself: the data that
> has to cross a seam, counted where the seam would be cut.

## Where it comes from

Steps 9 to 13 settled what the reviewers' Long Method is. On the MLCQ confirm half, length at an
absolute cutoff of 26 lines reaches an MCC of 0.777, beats every other form by 0.08 or more with
the interval clear of zero, and each reviewer's own best cutoff lies between 17 and 34 lines.
Complexity, coupling, variable counts and every live-width form sit below it; the forms that
come close are length with a gate on it, and the gate only removes trivial short methods. So the
smell is settled by length, and the useful question is no longer *is it long* but *what does
it cost to make it short*.

## The claim in one paragraph

Extracting a run of statements into its own method turns every variable crossing the run's
boundary into interface: what is used inside and defined before becomes a parameter, what is
defined inside and used after becomes the return value, and Java allows one. A method of
sequential steps has cuts that carry one or two variables. An interwoven method has no cut that
carries fewer than five or six, because the same variables are touched everywhere. The **split
cost** of a method over the cap is the cheapest worst seam over every segmentation that brings
every piece, the remainder included, under the cap. A long method with a cheap split is tidy
and merely long; one where every split is expensive is what a reviewer means by a god method,
and the cost says how far from clean it is.

## The logic

**A cut.** A piece is a contiguous run of statements from one sequence of the statement tree: a
block, a switch entry, or a lambda's block body. Whole statements move, so a run that includes
an `if` or a loop takes its arms or body with it. A piece's length is the count of the method's
code lines inside its range, as the oracle counts, not the raw span. Extracting a piece
replaces it with one call line, so the remainder's length is the original minus the extracted
lines plus one per extraction.

**The cost of a cut.** For a run with line set L, each local or parameter takes one role from
its reference lines, its definition lines and its data flow. Fields are not interface.

| Role | Rule | Becomes |
|---|---|---|
| Input | referenced in L and referenced before L | a parameter |
| Output | written in L and referenced after L, or, inside a loop, referenced earlier in the loop (the back edge) | the return value |
| Internal | every reference in L | nothing; it moves |
| Untouched | no reference in L | nothing |

An object written into through its state (an array store, a field set) is an input only: the
caller's reference sees the change. The seam cost is inputs plus outputs. A run is feasible when
it has at most one output, no `return`, `break` or `continue` that leaves it (a trailing return
being the usual exception), and no more than the cap in lines.

**Choosing the segmentation.** The search runs bottom up over the tree. For a sequence, a
dynamic program walks its statements in order; at each statement it either keeps it in the
remainder or closes an extracted run ending there. The state is the remainder's length so far,
the value the worst seam among the runs chosen, and the result the cheapest segmentation whose
remainder and every run end at or under the cap, ties broken by fewest pieces, then by the
smallest total of seams. A single statement longer than the cap (a 40-line loop) cannot move
whole: its inner sequences are solved first, each yielding the lengths it can be reduced to and
the cost of each, and the parent treats the statement as having those reduced lengths
available.

**Per method, the reading gives:**

- **split cost**: the worst seam of the best segmentation;
- **pieces**: how many extractions, and the cut lines, so a decomposition can be shown and set
  beside what the slicing tools would propose;
- **infeasible**: no segmentation reaches the cap (two outputs at every seam; a statement no
  inner cut can shrink), the methods that need more than Extract Method;
- **records variant**: the same search with several returns allowed and costed as a record's
  values (below). A method infeasible by default and feasible here is splittable only by
  introducing a type, and its cost says what that takes;
- **structural variant**: the same search restricted to runs that are whole `if`, `try` and loop
  statements, which is where developers cut (Alon and Feitelson, below). The gap between the two
  costs is how much the data-flow seam adds over the structural cue;
- **framework variant**: the same search read as if the pieces were functions a framework
  calls in sequence rather than methods the remainder calls (below, *The framework reading*).
  A parameter handed on unchanged costs nothing, and a second result is one more declared
  value, not a record. It is not part of step 14; it is read on the agent-written corpora,
  where one arm is written that way.

## The cost of the refactor

A split turns live width inside one method into coupling between two, so the refactor is
costed in the study's own currency: what crosses a boundary (the sinew of
[`SINEW.md`](SINEW.md), here on the call edges the split creates), plus the edits that create
it. Every component comes from the facts.

**Per extracted piece**

| Component | Computed from | Why it costs |
|---|---|---|
| Parameters | the inputs: used inside, referenced before | a signature slot, an argument at the call, and a name a reader carries across |
| Return value | the outputs: written inside, used after | none: a void piece is a plain call; one: a plain call with a result, the same as a parameter; two or more: infeasible by default, or three per value under the records variant, since Java has no tuple and each extra value needs a record type declared, packed in the piece and unpacked at the call |
| Moved declarations | variables with every reference inside, declared before with no value or a literal one | nothing: the declaration is not a computation, so the tool places it at the top of the new method; the literal rule already said it could move without changing the method |
| Trailing return | a run ending in `return` | the piece returns and the caller returns its result: cheap, but two signatures change |
| Checked exceptions | calls inside that throw checked types | the new method needs a `throws` clause; not in the facts, so a flag at most, and better left to the IDE |
| Naming and call site | one per piece | the developer's one input, and the line that replaces the body |

**Across the segmentation**

- **Worst seam**: the maximum over pieces of parameters plus return. The split cost above: the
  hardest single piece, the number set against the reviewers.
- **Total interface**: the sum of seams. The coupling the refactor adds to the class, the sinew
  count on the new call edges. A method whose best segmentation adds twelve sinews has not been
  simplified; it has been spread.
- **Pieces**: each costs a name and a call, so fewer is better at equal interface.
- **Binding**: free, bound by reads, or locked (above), per piece and per remainder, and the
  locked share per class.
- **Not counted**: a declaration with no value or a literal one, declared before the piece and
  used only inside it. It crosses no seam and carries no data; the tool moves it to the top of
  the new method as part of the proposal. Left where it is, an IDE would turn it into a
  parameter, so the move is the tool's job, not a cost to the developer.
- **Width afterwards**: the remainder is read as calls whose arguments and results a reader
  tracks, so its live width after the split is about its total interface. Replaying the
  segmentation over the same facts gives width before against width after, the honest
  comparison, not length alone.

### Binding to the class

The seam counts what crosses between the piece and the rest of the method. A piece also
depends, or not, on the object it lives in, and that is a constraint on where the piece can
go, not a cost of cutting it. Each piece is classed by what it touches:

| Class | Rule | What the piece can become |
|---|---|---|
| **Free** | no field referenced, no call to the class's own methods | a stateless utility: a static method, movable to any class |
| **Bound by reads** | reads fields, writes none, calls none of the class's own methods | static if the fields it reads are passed in, one input each; otherwise an instance method |
| **Locked** | writes a field, or calls one of the class's own methods | an instance method of this class, and nothing else |

A field write locks a piece because the write is a second output path, into the object rather
than the return, and because a method that changes the object's state belongs with the object.
A call to the class's own methods locks it because the only way to pass that dependence is to
pass `this`, which is the binding itself. A field read can be parameterised, at a cost of one
input per distinct field, and the tool offers that when it fits under the maximum inputs.

The remainder is classed the same way, so a method yields, after its split, a set of pieces
each marked free, bound or locked. The width and the cost above are unchanged by the class;
binding is reported beside them.

**Across a class.** Count, over every method of a class that is over the cap, the pieces its
best segmentation produces and how many are locked. The **locked share** of a class is locked
pieces over all pieces. A class whose long methods split only into locked pieces has not
concentrated its length, it has concentrated its logic on its data: every piece that could be
cut off still has to stay. That is the god class rather than the long method, and it is
invisible to the method-level reading, which would count the split as cheap. The locked share
is a class-level number that can be read against the Blob oracles the study already holds,
exploratory like everything here. In the study's own terms, fields are the sinews that never
cross a call edge, and the locked share is how much of a class's logic rides on them.

**The benefit side.** Haas and Hummel (below) found that the reduction in statements and in
nesting area, with the input count, carry nearly all of what developers accept. The benefit of
a segmentation is the lines and nesting removed from the remainder, and whether the cap is met.
A suggestion ranks by benefit per unit cost; the measure for the study is the minimum cost at
which the cap is met.

**A formula to start from.** For a segmentation S with pieces p:

```
cost(S)  = sum over p of ( inputs_p + output_cost(outputs_p) + 1 )  + penalty * [infeasible]
width(S) = max over p of ( inputs_p + outputs_p )

output_cost(0) = 0        a void piece: a plain call
output_cost(1) = 1        one result: a plain call with a value, the same as a parameter
output_cost(k) = 3 * k    two or more: a record, when allowed at all (infeasible by default)
```

A method call that takes some values and returns one is just a method; its interface costs
one per value crossing, in either direction, and the one per piece is the name and the call
site. Several returns are not what a method is for, and Java makes that concrete: there is no
tuple in the JDK, `java.lang.Record` cannot be used as a generic return type for two values,
and the only honest route is a named record, local to the enclosing method (Java 16) or
nested in the class. Each value then costs three things: the type declared, with a name the
developer must invent; the packing, a constructor call in the piece's return; and the
unpacking, one accessor read per value at the call site, since Java has no destructuring
assignment (record patterns, Java 21, destructure only in `instanceof` and `switch`). Hence
three per value returned, applied to every value once there are two, so a two-value seam
costs six against one for a single return. By default such a seam is infeasible; the records
variant allows it at that price, and the methods that become feasible only there are a count
of their own. All of these are parameters (next section), to be fitted, not asserted.

### The framework reading

The cost above assumes the pieces are methods the remainder calls: a piece's inputs are its
parameters, its results come back through one return, and the remainder sequences the calls.
Under function injection (OfficeFloor's functions, and any style where a container calls each
function and supplies what it declares) the pieces are not called by the remainder at all. The
framework calls them one after another, and each declares what it needs. Two things change at
the seam.

- **A parameter handed on unchanged is free.** If the long method takes `request`, `repository`
  and `config` and a piece uses them as they arrived, the piece declares the same three
  parameters and the framework injects them. No argument is written, no call site exists, and
  the names already stood on the method. In the facts such a value is a parameter of the method
  with no definition and no mutation before the run; the seam records it as *passed* and, under
  this reading, leaves it out of the inputs. A parameter the method reassigned or mutated before
  the run is a computed value like any local and still counts.
- **Several results are several declared values, not a record.** A value one piece computes
  for a later one is declared as an output on the one side and an input on the other, one
  declaration per value, and the framework carries it. There is no type to invent, no packing
  and no unpacking, so the second and later results cost one each, the same as a single return,
  and no seam is infeasible on its outputs. A computed value still crosses, and its declaration
  on both sides is a name a reader carries across, so it costs one as an input does.

What does not change: computed locals are still inputs, the maximum inputs still applies to
them, a jump that leaves a run is still fatal, and the binding to the class is read as before.
This reading does not apply to a Spring handler, and the search makes no attempt to: the
analogue of an injected parameter there is an injected field, which the seam already treats
as free (fields are not interface), and which appears instead in the binding, since a piece
that reads or writes the controller's fields stays in the controller. That is the comparison
the reading sets up. Under default parameters both arms are costed as if their pieces were
instance methods; under the framework reading the OfficeFloor arm is costed as what its pieces
would be, and the difference between the two readings on that arm is what the framework buys
on the seam: on the OfficeHQ chains (October 2026) it took the infeasible share of the long
functions from about half to about a seventh, the remaining infeasible ones threading four to
eight computed locals through a run, which no reading of the parameters removes.

## Parameters

Every number the algorithm decides by should be named, defaulted and sourced, so a fit on one
corpus can be compared with a fit on another. The grid should be fixed before either corpus is
read, the defaults the headline, the rest reported in full.

| Parameter | Default | Source |
|---|---|---|
| Trigger: the length at which a method is split | 26 lines | the step 13 cutoff on the human oracle |
| Target: the length every piece and the remainder must end at | 25 lines | the trigger minus one; lower leaves headroom |
| Minimum piece | 5 lines | Alon and Feitelson: 80% of extracted functions at 5–30 lines |
| Minimum saving a cut must make | 3 lines | avoids cuts that only shuffle a call |
| What a line is | code lines, as the oracle counts | tokens or statements as alternatives |
| Maximum inputs | 3 | Haas and Hummel's prune; Fowler's long parameter list at 4 |
| Maximum outputs | 1 | Java's single return; 0 for a pure helper; no limit under the records and framework variants |
| Cost of a single return | 1 | the same as a parameter: a call with a result is a plain method call; 0 for a void piece |
| Cost per value of several returns | 3 each | a record type declared, packed and unpacked; only when the maximum outputs allows them; 1 each under the framework variant, where each result is a declared value the framework carries |
| Pass-through parameters | inputs, one each | a parameter of the method handed on unchanged; free under the framework variant, since the piece declares it and the framework injects it |
| Moved literal declarations | 0 | not a computation: the tool places them in the new method; a parameter only if left behind |
| Cost per piece | 1 | a name and a call site |
| Infeasible penalty | reported, not summed | the methods that need more than Extract Method are a count of their own |
| Parameterise field reads | yes, within the maximum inputs | a read field passed in makes a bound piece free at one input each |
| What locks a piece | a field write, or a call to the class's own methods | reference semantics and `this`; a stricter setting locks on any field reference |
| Fields | free | or weighted: a helper reading five fields is coupled to the class |
| Mutated objects | input only | reference semantics; or half an output |
| Structural only, or any run | both computed | the gap is a finding |
| Jumps | trailing return allowed; break/continue fatal | or carried as a boolean result |
| Recursion | into loop, lambda and switch bodies, any depth | or a depth limit |
| Objective | worst seam; then pieces; then total | sum of seams as an alternative |
| Cohesion penalty | none | a cost per variable whose uses are divided across pieces |
| Search | exhaustive dynamic program | or the greedy best cut repeated, as in an IDE |

On human code the oracle is the MLCQ reviewers: the settings are those under which the split
cost separates the long methods reviewers passed from the ones they flagged, chosen on the
explore half and read on the confirm half. On AI-written code there is no reviewer oracle; the
first honest study is descriptive, the same instrument with the same defaults, reporting where
the distributions differ. The suspicion that AI concentrates complexity has a precise form
here: a higher split cost at the same length, lower structural-only feasibility, and more
methods infeasible under one output. If that holds, the parameters to refit are the interface
ones, outputs above all, not the size ones.

## As a tool

The same search, run for one method in an editor, proposes where to cut and asks only for the
name. That is a separate piece of work, described in [`SPLIT-TOOL.md`](SPLIT-TOOL.md); it is
later development, and nothing in this note depends on it.

## Facts needed, and what the pass has

The live-width facts (schema 3) carry, per variable, the range, the loop extent, the literal
flag, the use-first start, the distinct reference lines, the definition lines and the write
lines, the definitions count and the variables it is computed from; per call, its line,
arguments, receiver and result; per method, the statement tree with each node's kind. So:

- a reference inside the run and after it is an input if both are reads and an output if the
  inner one is a definition (`def_lines`) or, for an object, a write into it (`mut_lines`);
- the jump rule reads each node's kind (return, break, continue, throw, yield), and the
  structural variant reads the if, loop, try and switch kinds.

For the binding, two facts are already there and one is approximate:

- field reads and writes come from the FIELD variables' reference lines and, once recorded,
  their definition lines (`this.x = v` is a definition of `x`; `x.f = v` is a write into it);
- calls to the class's own methods come from the measurer record, which resolves each call to
  a file: a call with no receiver variable that resolves to the method's own file. The limit is
  that the record names the file, not the class, and does not say whether the target is static,
  so a call to a static method of the same class reads as binding when it is not. The measurer
  could record both; until it does, the locked share is an upper bound.

## How it is read (step 14)

```
./step14_explore_split.sh
```

[`scripts/split.py`](scripts/split.py) is the search, over one method's facts;
[`scripts/exploratory_split.py`](scripts/exploratory_split.py) runs it for every method at or
over the trigger in every set and reads the results as step 13 read the widths: the registered
rule with the paired bootstrap, absolute cutoffs chosen on the explore half and read on the
confirm half, and, new here, the AUC of each form against the label **among the long methods
only**, since a method under the trigger has no split and the only ground a split form can gain
over length is among the methods length already flags. On the confirm half that ground is 28
false positives against 103 hits: perfect separation would take length's 0.777 to about 0.90.
Class level reads the locked share and the sums of cost and interface against the step 13
class competitors. The defaults are the headline; the structural-only, no-input-limit and
records variants are read beside them (the last with its cost, since what a record costs is
its point); nothing else of the grid is tried, and the parameters are written into the output.
The framework variant is not read in step 14, since nothing in the human corpora is written
that way; [`scripts/exploratory_petclinic.py`](scripts/exploratory_petclinic.py) reads it
beside the default and records variants on the agent-written corpora, arm by arm, and reports
each arm under the reading its architecture earns.

The search's approximations, beyond the own-class call above: the facts give a method's lines
as the statement tree's spans, which agree with the measurer's nloc for most methods and within
a line or two for the rest, so the trigger and the target are read on the measurer's nloc and
the lines a cut saves on the tree; a reference after a run is taken as a read, so a variable
merely overwritten later counts as an output; a run of several statements is extracted as it
stands, and only a single statement is reduced from inside before it is extracted whole, which
is the loop-body case the recursion is for.

Two outputs, small enough to commit: `results/exploratory/split.<utc>.json`, and
`results/exploratory/split-units.<utc>.csv.gz`, one row per reviewed method with its label, its
length, every split reading and the cuts of its best segmentation.

## Prior work, and the gap each leaves

No paper defines the quantity above: a cap as a hard constraint, the seam cost as the
objective, the minimum over valid segmentations as a scalar per method, computed over a
population and set against reviewer labels. Every ingredient is in print. The two nearest are
Haas and Hummel, who have the cost but no cap and no search over a segmentation, and a 2020
patent (Kimball et al., below), which has the cap and a search for movable blocks that bring
the function under it but no cost at all. Nothing was found on any of it for AI-written code.
The search was of the open web, Google Scholar's and Google Patents' indexes and the papers'
own reference lists, in English; vendor internals (CodeScene, Sourcery, JetBrains) are not
published.

### Length caps, and what breaks when methods get smaller

| Work | What it found | What it leaves |
|---|---|---|
| Chowdhury, Holmes, Zaidman & Kazman, "An Empirical Study on Maintainable Method Size in Java", MSR 2022, doi:10.1145/3524842.3527975 | ~785K Java methods in 49 projects with two years of history: length correlates with change- and bug-proneness; a benchmark-based threshold procedure (after Alves et al.) gives **24 SLOC** as the realistic cap; groups of small methods that could be merged into one are collectively less change- and bug-prone than one method of the same total size | a maintenance oracle, not a reviewer's; the threshold lands within two lines of step 13's 26 |
| Hatton, "Reexamining the fault density–component size connection", IEEE Software 14(2), 1997; "Why is the defect density curve U-shaped with component size?" (synthesising Basili & Perricone 1984, Möller & Paulish, Compton & Withrow 1990, Shen et al.)¹ | fault density U-shaped against component size, minimum at a few hundred lines, explained by short-term memory | whole modules and files, not methods; the small-is-worse arm disputed (Rosenberg) as fixed per-component overhead |
| Landman, Serebrenik & Vinju, "Empirical analysis of the relationship between CC and SLOC in a large corpus of Java methods", ICSME 2014, doi:10.1109/ICSME.2014.44; journal version with Bouwers, JSEP 28(7), 2016 | 17.8M Java methods (17.6M in the journal version, with 6.3M C functions): CC and SLOC correlate only moderately, with high variance; CC is not redundant with SLOC | no oracle; says complexity is not length, which step 13 confirms, and that on the human oracle it is also not better |
| AlOmar, Mkaouer & Ouni, "Behind the Intent of Extract Method Refactoring: A Systematic Literature Review", IEEE TSE 2024, doi:10.1109/TSE.2023.3345800 (arXiv 2312.12600) | 37 tools catalogued, 49% for clones and 24% for long methods; names as a design-level limit that extraction can raise cognitive load by introducing locals and parameters and spreading logic; names the lack of benchmarks and ground truth as the field's gap | the gap the reviewed extract fills |
| "Refactoring for Novices in Java: An Eye Tracking Study on the Extract vs. Inline Methods", JSS 2026 (arXiv 2602.18579)¹ | 32 novices: extraction helped on harder tasks (time down by up to 78.8%, regressions by 84.6%) and hurt on trivial ones; readers made more regressions across extracted pieces | novices, small programs; shows the cost of a split is real, which is the case for measuring it |

### How tools decide where to cut

| Work | What it does | What it leaves |
|---|---|---|
| Komondoor & Horwitz, "Semantics-Preserving Procedure Extraction", POPL 2000, pp. 155–169; "Effective, Automatic Procedure Extraction", IWPC 2003¹ | sufficient conditions on control and data dependences for a statement set (contiguous or not) to be extractable while preserving semantics | validity, no cost |
| Lakhotia & Deprez, "Restructuring programs by tucking statements into functions", IST 40(11–12), 1998, pp. 677–689¹ | the *tuck* transformation: wedge, split, fold | validity, no cost |
| Maruyama, "Automated method-extraction refactoring by using block-based slicing", SSR 2001, pp. 31–40¹ | block-based slicing: several valid extraction candidates per slicing criterion | candidates, not a segmentation |
| Tsantalis & Chatzigeorgiou, "Identification of Extract Method Refactoring Opportunities", CSMR 2009; "…for the decomposition of methods", JSS 84(10), 2011, pp. 1757–1782, doi:10.1016/j.jss.2011.05.016 (JDeodorant) | complete computation slice and object state slice: a candidate holds the full computation of one variable, with behaviour-preservation rules; the single output is built in | long candidate lists; ignores return statements (per critics); no cap, no seam cost |
| Charalampidou, Ampatzoglou, Chatzigeorgiou, Gkortzis & Avgeriou, "Identifying Extract Method Refactoring Opportunities Based on Functional Relevance", IEEE TSE 43(10), 2017, pp. 954–974, doi:10.1109/TSE.2016.2645572 (SEMI)¹ | clusters statements coherent by shared variables, objects and method names, ranks the opportunities | cohesion, not interface; no cap |
| Silva, Terra & Valente, "Recommending Automated Extract Method Refactorings", ICPC 2014; "JExtract: An Eclipse Plug-in…", arXiv 1506.06086, 2015 | scores regions by how rarely their structural dependencies are used by the rest of the method; better recall and precision than JDeodorant at finding misplaced code | the only size criterion is the candidate's statement count (per critics); no seam cost |
| "Extract Method Refactoring by Successive Edge Contraction", arXiv 1908.04636, 2019 | collapses a structure dependence graph by structural-control, exclusive-data and sequential-data edge contractions into a segment graph; four case studies | no cap, no scalar |
| Yang, Liu & Niu, "Identifying Fragments to be Extracted from Long Methods", APSEC 2009 (AutoMeD)¹ | identifies statements extractable without changing behaviour from a long method | candidates, not a segmentation |
| **Haas & Hummel, "Deriving Extract Method Refactoring Suggestions for Long Methods", SWQD 2016, LNBIP 238, pp. 144–155, doi:10.1007/978-3-319-27033-3_10; "Learning to Rank Extract Method Refactoring Suggestions for Long Methods", SWQD 2017** | for methods over 40 LoC, enumerates valid contiguous candidates, prunes those needing more than three input parameters or several outputs, ranks the rest on 20 features in three groups (length and nesting reduction, data flow, parameters as "data coupling between the original and the extracted methods", structure); ten developers would apply 86% of suggestions; learning to rank over ~1,000 manually ranked candidates from 13 systems finds three features carry the ranking: statement reduction, nesting-area reduction and the **number of input parameters** (NDCG 0.885 on those alone, 0.894 at best) | **the closest prior work**: the seam cost is a ranking feature within one method, never minimised over a segmentation, never a property of the method, never read against a smell oracle |
| Shahidi, Ashtiani & Zakeri-Nasrabadi, "An automated extract method refactoring approach to correct the long method code smell", JSS 187, 2022, 111221, doi:10.1016/j.jss.2022.111221; follow-up "Supporting single responsibility through automated extract method refactoring", EMSE 2023, doi:10.1007/s10664-023-10427-3 (arXiv 2305.03428)¹ | detects long methods, ranks extractions, chooses a destination class for modularity; computes Weiser's tightness, overlap and coverage before and after extraction | tool evaluation on five projects; no cap, no scalar |
| Pomian et al., "EM-Assist: Safe Automated ExtractMethod Refactoring with LLMs", FSE 2024 companion, doi:10.1145/3663529.3663803 (arXiv 2401.15298); "Automated Extract Method Refactoring with Open-Source LLMs: A Comparative Study", arXiv 2510.26480, 2025 | LLM suggestions validated by the IDE's parameter and single-return checks; 81.3% of 16 industrial developers agreed; open-source LLMs accepted in over 70% of cases by nine developers, κ ≈ 0.30 | small surveys; the IDE still decides feasibility |
| Kimball, Huddleston & Nicotera, "Software refactoring systems and methods", US patent 10,853,060 B2 (Architecture Technology Corp., filed 2018, granted 2020) | the nearest thing to a cap-driven search in print: a function over a line threshold (50 in its example) is a violation; the tool walks the syntax tree for runs of movable statements (a return, a break or a continue, or anything too large, is not movable, and a parent inherits its children's immovability), sums their significant lines, tests whether removing them, singly or as subsets, brings the function under the threshold, and offers the largest; variables used only inside stay local, those depending on the original become parameters | no cost: the choice is movability and line count, with no seam, no width, no binding, no single-output rule, and nothing read against an oracle or over a population |
| Kaya & Fawcett, "Identifying Extract Method Opportunities Based on Variable References", 2014; "Identification of Extract Method Refactoring Opportunities through Analysis of Variable Declarations and Uses", IJSEKE 26(9–10), 2016, doi:10.1142/S0218194017500036¹ | fully extractable fragments confined by variable declarations and uses and by control blocks, with no user intervention, filtered by a user-set maximum number of parameters; a visualisation tool, case studies on their own and open-source code | candidates with a parameter cap, not a segmentation under a length cap; no cost over a decomposition |
| CodeScene ACE (2024–); EM-Assist; Sourcery and the IDE assistants | commercial auto-refactoring of a flagged Complex or Large Method by LLMs, with semantic and syntactic checks on the suggestion; ACE considers functions under 130 lines (200 for Java) | the model picks the region; no stated criterion, no cost, nothing published on where it cuts |
| LLVM `CodeExtractor` (Transforms/Utils); Zhao & Amaral, "Function Outlining and Partial Inlining", SPE 37(5), 2007, pp. 465–491 | the compiler's extraction finds a region's inputs and outputs, passes inputs as arguments and each output through an alloca (so no single-output limit); outlining cost models weigh size and execution frequency, not interface | mechanics without cost; cost without interface |
| Mkaouer, Kessentini, Bechikh, Deb & Ó Cinnéide, "High Dimensional Search-based Software Engineering: Finding Tradeoffs among 15 Objectives for Automating Software Refactoring Using NSGA-III", GECCO 2014; Ouni, Kessentini et al., NSGA-II refactoring with semantics preservation¹ | multi-objective search over sequences of refactorings for class-level cohesion and coupling | the wrong grain: not a dynamic program over a method's statements under a length constraint |

### Whole-method scalars

| Work | What it gives | What it leaves |
|---|---|---|
| Weiser (slice metrics, 1981/1984); Ott & Thuss, "Slice based metrics for estimating cohesion", METRICS 1993; Bieman & Ott, TSE 1994; Meyers & Binkley, "An Empirical Study of Slice-Based Cohesion and Coupling Metrics", TOSEM 17(1), 2007, doi:10.1145/1314493.1314495; Green, "An Introduction to Slice-Based Cohesion and Coupling Metrics" (Hertfordshire)¹ | tightness, coverage, min/max coverage, overlap of a method's output slices; low coverage read by Weiser as "several distinct conceptual purposes"; Meyers & Binkley compare them head to head and against LOC; Black et al. separate faulty from non-faulty functions with tightness and overlap | how separable the slices are, not what any cut costs or whether a cap can be met |
| Wang, Pollock & Vijay-Shanker, "Automatic Segmentation of Method Code into Meaningful Blocks: Design and Evaluation", JSEP 26(1), 2014 (WCRE 2011)¹ | partitions a method body into segments from syntax, blank lines and data flow, evaluated against developers' own segmentations | segments for reading, not extraction; no cap, no cost |

### What developers do, and why

| Work | What it found | What it leaves |
|---|---|---|
| Alon & Feitelson, "How Developers Extract Functions: An Experiment", arXiv 2209.01098, 2022 | 23 developers re-extracted a 208-line flattened Python function: 3–10 functions each, 80% of them 5–30 lines; 77 of 142 began at an `if` and 31 at a `try`; data flow not a stated criterion; survey: cohesive logic 4.62/5, passing few arguments 3.10, an ideal length 2.65, yet specific length answers clustered at 20–30 lines | one code base; shows cuts land on structural boundaries, the structural variant above |
| "Major motivations for extract method refactorings: analysis based on interviews and change histories", Frontiers of Computer Science, 2016, doi:10.1007/s11704-016-5131-4¹ | 25 developers interviewed; in seven systems' histories reuse is the primary motive for 56% of extractions, decomposing a long method for 28%, clone resolution for 16% | decomposition is the minority case |
| Silva, Tsantalis & Valente, "Why We Refactor? Confessions of GitHub Contributors", FSE 2016, doi:10.1145/2950290.2950305 (arXiv 1607.02459) | 11 motives behind Extract Method, reuse and readability leading | as above |

¹ Citation or detail taken from a secondary source (an abstract, a citing paper, a search result), not checked against the original text.

### Already in the live-width note

Crichton, Agrawala & Hanrahan (CHI 2021), Peitek et al. (ICSE 2021), Cates, Yunik & Feitelson
(ICPC 2021), DepDegree (Beyer & Fararooy 2010), Dunsmore & Gannon (1979/1980), McConnell,
Elshoff, Chapin, Sajaniemi's roles, Campbell's Cognitive Complexity, the readability models and
the slicing-cohesion tools are cited in [`LIVEWIDTH.md`](LIVEWIDTH.md), *Prior measures, and
the gap each leaves*.
