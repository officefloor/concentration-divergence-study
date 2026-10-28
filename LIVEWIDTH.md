# Live width — what a reader must hold at once

> **Status (27 October 2026). EXPLORATORY, POST HOC.** Written after every oracle of the study
> had been read (PLAN.md, Amendments, 10). Nothing measured with it here is confirmatory. It
> is a candidate for the next registration, and step 13 is its exploratory reading.

## The claim in one paragraph

The exploration (steps 9–12) found that, at method level, length gated by "makes at least one
call" was the best predictor of god methods. Nothing about complexity beyond length added to it.
Length is a poor reason in itself, though: a method that calls step after step in a long
sequence is easy to follow. The proposal here is that what makes a method too big is **how much
a reader must hold in mind at the same point**, set against the 4 ± 1 chunks of Cowan or the
7 ± 2 of Miller.

Each variable is live from its first reference to its last. A variable set once is cheap to
hold. One whose value keeps changing is wider, because the reader must track which value is
current. The **live width** of a method is the largest summed width of the variables live at
any one line. It is the implicit sinew of the method: the data riding on the method's own
control flow, as [`SINEW.md`](SINEW.md)'s sinews ride on the call chain.

## How it is measured

The measure has two parts:

- [`measurer/…/LiveWidth.java`](measurer/src/main/java/net/officefloor/divergence/LiveWidth.java)
  collects the facts per method. It uses the measurer's units with no symbol solver, matching
  names to declarations by lexical scope.
- [`scripts/livewidth.py`](scripts/livewidth.py) computes every variant from those facts.

The facts it records:

- **Variables.**
  - Parameters.
  - Locals, including for and for-each variables, resources, catch and lambda parameters, and
    pattern variables.
  - Fields: `this.x`, or a simple name that no local declaration in scope matches.
  - Not variables: names starting with an upper-case letter (types and constants by
    convention), and enum constants used as `case` labels.
- **Range.** From the variable's first reference to its last reference.
  - `text`: those line numbers as they stand.
  - `loop`: also widened over every loop the variable is referenced in but declared outside.
    Such a variable is live on the back edge, so it is live over the whole loop. This is the
    cheap part of following control flow; branches are not followed.
  - **The literal rule.** A local declared with no value, or with a literal one (`0`, `-1`,
    `null`, `""`, `false`, a cast or parenthesised literal), depends on nothing above it: the
    declaration could move down to the first use without changing the method. The habit of
    declaring every variable at the top would otherwise make each live from the top. So such a
    variable's range starts at its first use, as a parameter's does. An initializer still
    counts as a definition. The facts keep both starts, so the earlier reading, in which a
    literal initializer started the range at the declaration, is a variant (`decl`) beside the
    headline. A declaration with no value was never a reference, so it is unchanged.
- **Reference lines.** The distinct lines each variable is used at, a literal declaration
  excluded. The range says what is carried over a line; the reference lines say what is touched
  near it, for forms that read locality (a window of lines, or the runs a variable is used in)
  rather than the span.
- **Definition lines and write lines.** The distinct lines of each variable's definitions that
  have a line (an initializer, a binding, an assignment, an increment; not a parameter's
  argument or a field's prior state), and of the writes into its object. With the reference
  lines, a read can be told from a write at any line.
- **Statement tree.** The method body as nested line ranges: a sequence (a block, a switch
  entry, a lambda's block body) holds its statements in order; a statement holds the sequences
  and statements directly inside it (an if's arms, a loop's body, a try's block and catches).
  Each node carries its kind: the jumps (return, break, continue, throw, yield), the structural
  statements (if, loop, try, switch), blocks and switch entries, or other.
  Extract Method moves a contiguous run of one sequence's statements, so the tree says where a
  cut may fall, which the reference lines and data flow then price: the variables used inside
  the run but defined before it are its parameters, those defined inside and used after are its
  results, and Java allows one result. Nested type bodies are left out, as everywhere.
- **Weight.**
  - `unit`: 1 for every variable.
  - `assign`: every definition (the value the variable enters with, plus each reassignment),
    plus every write into its object (`a[i] = v`, `a.f = v`).
  - `role`: 1, plus the definitions that are not steps, plus the writes into it. A step is
    `++`, `--`, `+=` or `-=` of a literal, or anything in a for statement's update. So a value
    set once and a loop counter both weigh 1 (Sajaniemi's *fixed value* and *stepper*), while a
    gatherer or most-recent holder weighs more.
- **Scope.** `locals` covers parameters and locals; `all` adds fields.
- **Start.** `use`: a parameter from its first use, a literal-initialised local from its first
  use (the headline). `decl`: a literal-initialised local from its declaration. `sig`: a
  parameter from the signature.
- **Aggregate.**
  - `max`: the live width.
  - `mean`: Dunsmore & Gannon's average.
  - `area`: the sum of widths over the code lines.
  - `over k`: the number of code lines wider than k.

Beside the widths, the same facts give **plain counts** of the variables a method references,
with no regard to when each is live:

- all of them, and parameters with locals;
- by kind (parameters, fields);
- how many are reassigned beyond a step;
- the sum of their role weights, which is the width the method would have if every variable
  were live at once.

Every form is also paired against the count of all variables. So if a width only ever counts
variables, the comparison shows it: overlap adds nothing over the number.

The headline variant is `[loop,role,all]`. Step 13 reads every variant and ranks none of them in
advance.

### Data flow, and whether it reaches the fan-out

This part ties variables to [`SINEW.md`](SINEW.md)'s coupling. Coupling counts what crosses the
method's boundary: parameters in, call arguments out. Variables are what carries that data
across the body.

The pass records two more kinds of fact:

- **For each variable:** the other variables its definitions are computed from.
- **For each call:** the variables in its arguments, the variable it is called on, and the
  variable that holds its result.

Calls come in the measurer's order, so the i-th call takes the measurer record's resolution.
Only internal calls count as fan-out: those that resolve to an analysed file, the sinew. A
method whose call count differs from the record's is left at zero and counted.

From those facts:

| Measure | What it asks |
|---|---|
| `in_params`, `in_fields`, `in_results`, `in_all` | How many variables come into the method: parameters, fields, and the results of internal calls |
| `max_from`, `derived` | How many variables go into computing one variable, at most; how many variables are computed from others |
| `out_vars`, `max_fanout` | How many variables are passed to internal calls; the most internal calls one variable goes to |
| `in_out`, `in_caught` | Of what comes in, how much flows on to an internal call, directly or through what is computed from it, and how much stops here |
| `in_through` | Parameters and fields passed to an internal call unchanged: a pipe strand, data the method only threads on |
| `bridging` | Variables live (the headline range) at two or more internal-call lines: state held across calls, so the method glues its callees together |
| `lw_at_calls` | The headline width at the lines with an internal call: how much is held when control is handed off |

The hypothesis behind `bridging` is what may explain the earlier finding:

- In a pipeline (`a = f(x); b = g(a); h(b)`), each result is passed straight on, so about one
  variable is held across calls at a time.
- A god method holds many results while it calls around.
- If that is so, "length × [makes a call]" works because the call gate stands in for this
  orchestration, and `bridging` measures it directly.

## Prior measures, and the gap each leaves

| Measure | What it computes | Gap |
|---|---|---|
| Span, live time (Elshoff 1976¹; McConnell, *Code Complete* 2004, "Scope") | Statements between references, and from a variable's first reference to its last, per variable | No overlap across variables, no weighting; offered as advice, never validated |
| Live variables per statement (Dunsmore & Gannon, *IEEE Computer* 12(12) 1979, doi:10.1109/MC.1979.1658576; *JSS* 1(2) 1980, doi:10.1016/0164-1212(79)90014-1; Conte, Dunsmore & Shen 1986) | The number of variables live at each statement, **averaged** over the procedure | No mutation weight; a mean, not a maximum. Related to construction effort¹, not to comprehension |
| MaxLive, linear-scan live intervals (Poletto & Sarkar, *TOPLAS* 21(5) 1999) | The maximum number of overlapping [first, last] intervals | The unweighted `[text,unit,*]` variant. In a compiler a redefinition *ends* a range; here it widens one |
| Crichton, Agrawala & Hanrahan, CHI 2021, doi:10.1145/3411764.3445257 | Propose liveness overlap as a working-memory metric (up to 18 in the Python standard library); measure about 6–7 variable/value pairs held while tracing code | Never validated against people or smells; no weight |
| DepDegree (Beyer & Fararooy, ICPC 2010, doi:10.1109/ICPC.2010.49; Beyer & Häring, ICPC 2014) | Edges of the use–definition graph over the control flow, summed | Mutation-aware, but a sum with no locality or overlap. Peitek et al. name exactly this gap |
| Oviedo (COMPSAC 1980); Tai (ICSE 1984)¹ | Definitions reaching each block, over the control flow, summed | As DepDegree |
| Chapin's Q (1979)¹ | Data items weighted by role (modified ×2, control ×3) | The earliest precedent for "a mutated variable is wider"; no flow, no locality |
| Cognitive Complexity (Campbell, TechDebt 2018¹); Shao & Wang's cognitive weights (2003) | Breaks in linear flow weighted by nesting; structure weights × number of input and output variables | Ignore data, or count only the interface |
| Readability models (Buse & Weimer 2008/2010; Posnett et al. 2011; Scalabrino et al. 2016–2019) | Identifiers per line (average, max), vocabulary, textual features | No lifetime. Scalabrino et al. (TSE 2019) found no metric alone captures understandability |
| Slicing cohesion and Extract Method (Weiser; Ott & Thuss; Bieman & Ott 1994; JDeodorant, *JSS* 2011; SEMI, *TSE* 2017; JExtract, ICPC 2014) | Where a method can be split, from its variable dependencies | No scalar width. A width peak should land on the region these tools would extract, which is a check of convergent validity |

¹ Citation or detail taken from a secondary source, not checked against the original text.

**The strongest motivation in print.** Peitek, Apel, Parnin, Brechmann & Siegmund (ICSE 2021,
an fMRI study with 19 participants) found:

- DepDegree had the strongest correlation with brain activation (Kendall's τ up to .41).
- McCabe showed none, against either time or correctness.
- They write that DepDegree "fails to consider the 'distance' or the locality of data-flow
  relationships", and that adding "the variable lifetime or lexical distance" would be worth
  exploring.

Live width is that combination: lifetime and mutation together, read at the hardest point.

### What it adds

1. **The maximum, not a sum or mean.** A capacity limit is broken at a point, so a long run of
   small independent sections stays narrow however long it is. That is how it would separate a
   long but sequential method from a god method.
2. **Lifetime together with mutation.** No prior measure combines them.
3. **A threshold with a cognitive meaning** (about 4–7), testable as an absolute cutoff that is
   the same for every repository, beside the registered outlier rule.

### Evidence for and against the design choices

**For:**

- The range from first to last reference: McConnell, Dunsmore & Gannon, Crichton.
- Mutation costs more: Chapin; reaching-definitions counts; Crichton (updates make readers
  swap values); Gopstein et al. (FSE 2017: assignments hidden inside expressions confuse).
- Set once is cheap: Cates, Yunik & Feitelson (ICPC 2021, 113 subjects). Well-named
  intermediate variables assigned once did not hurt comprehension, so an unweighted count would
  wrongly penalise extracting an explaining variable.
- Data flow matters more than control flow: Peitek 2021.

**Against, or cautioning:**

- A raw reassignment count over-weights steppers. Sajaniemi's roles say a loop counter is cheap;
  hence the `role` weight.
- How costly a variable is depends on its name (Hofmeister et al., SANER 2017). Experts chunk
  related variables, so one variable is not always one slot.
- Correlation with length. DepDegree correlates with LOC at τ = .59 (Peitek), and slice metrics
  are confounded by module length (Counsell et al.). Step 13 reports the rank correlation of
  width with length and pairs every form against length.
- Expect modest effects. Lavazza et al. (EMSE 2023) and Muñoz Barón, Wyrich & Wagner (ESEM 2020)
  found structural measures predict understandability only weakly, and differently for time,
  correctness and ratings.

### Known limits of this implementation

- **Branches are not followed.** Variables live only in different arms of an `if` are counted
  as live together. A reaching-definitions version (DepDegree made local) needs a control-flow
  graph that JavaParser does not provide, and is left for later.
- **Names are matched lexically.** A lower-case qualified name in an expression
  (`java.util.List.of()`) reads as a field `java`. A lower-case enum constant outside a `case`
  label reads as a field.
- **Stream pipelines carry data with no named variable,** so width under-counts them.
- **Ranges are measured in lines,** so several statements on one line share a line.
- **Weyuker's properties.** A maximum is not additive, and probably fails property 9 that
  DepDegree satisfies.
- **Data flow is syntactic.**
  - A variable is computed from every variable referenced in its right-hand side. Branches and
    the order of definitions are not separated.
  - A lambda's body flows into the variable it is assigned to.
  - Data written into an object through a call (`list.add(x)`) reaches the list only as that
    call's argument, not as a definition of `list`.

## What follows it

Step 13 found that the reviewers' Long Method is an absolute length (26 lines or more) and that
no width form beats it. The direction that follows, the cost of bringing a method under that
cap, with its logic, parameters and literature, is in [`SPLIT.md`](SPLIT.md). The reference
lines, the literal rule and the statement tree were added to the facts for it.

## How it is read (step 13)

```
./step13_explore_livewidth.sh
```

Step 13 runs in two parts:

1. **Fetch and measure.** It fetches every measured repository again at its recorded commit;
   the stored records keep no source. Only the `.java` files the measurer read are checked out,
   and Fontana systems come from their archives. Before any repository is measured, the
   LiveWidth pass is checked on its fixture. Each repository's units are then checked against
   the record's units, and any mismatch is counted.
2. **Score.** [`scripts/exploratory_livewidth.py`](scripts/exploratory_livewidth.py) reads
   every variant against length, tokens, and length × [internal call ≥ 1], two ways:
   - **Outlier:** the registered rule (modified z ≥ 3.5 per repository), with the paired
     bootstrap.
   - **Threshold:** absolute cutoffs (width ≥ k for k = 2…12; variable count ≥ k for
     k = 3…20; for length, nloc ≥ n). On MLCQ
     the cutoff is chosen on the explore half and read once on the confirm half, against
     length's cutoff chosen the same way.

   Class level reads the widest method of a class. The forms "length counts only beyond the
   span" (nloc × [width ≥ k]) and width × [internal call ≥ 1] test whether width explains the
   call gate.

**What to commit.** The raw records and the live-width facts stay out of git: they are many GB
and hundreds of MB. Two outputs are small enough to commit:

- the summary, `results/exploratory/livewidth.<utc>.json`;
- the extract, `results/exploratory/livewidth-units.<utc>.csv.gz`. It has one row per
  MLCQ-reviewed method, with its label and every method form, raw and as its modified z within
  its repository.

The extract lets the reviewed methods be analysed further without the records:

```
git add -f results/exploratory/*.json results/exploratory/*.csv.gz results/exploratory/*.sha256
```

**A note on the halves.** The confirm half was already read for the other measures in steps
9–12. Choosing the cutoff on explore and reading it on confirm keeps this measure's own choice
honest, but it does not make the result confirmatory. A real test is a registration on fresh
data, with the variant and the cutoff fixed from this exploration.
