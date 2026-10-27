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
- **Weight.**
  - `unit`: 1 for every variable.
  - `assign`: every definition (the value the variable enters with, plus each reassignment),
    plus every write into its object (`a[i] = v`, `a.f = v`).
  - `role`: 1, plus the definitions that are not steps, plus the writes into it. A step is
    `++`, `--`, `+=` or `-=` of a literal, or anything in a for statement's update. So a value
    set once and a loop counter both weigh 1 (Sajaniemi's *fixed value* and *stepper*), while a
    gatherer or most-recent holder weighs more.
- **Scope.** `locals` covers parameters and locals; `all` adds fields.
- **Parameter start.** From the parameter's first use, or (`sig`) from the signature.
- **Aggregate.**
  - `max`: the live width.
  - `mean`: Dunsmore & Gannon's average.
  - `area`: the sum of widths over the code lines.
  - `over k`: the number of code lines wider than k.

The headline variant is `[loop,role,all]`. Step 13 reads every variant and ranks none of them in
advance.

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
   - **Threshold:** absolute cutoffs (width ≥ k for k = 2…12; for length, nloc ≥ n). On MLCQ
     the cutoff is chosen on the explore half and read once on the confirm half, against
     length's cutoff chosen the same way.

   Class level reads the widest method of a class. The forms "length counts only beyond the
   span" (nloc × [width ≥ k]) and width × [internal call ≥ 1] test whether width explains the
   call gate.

**A note on the halves.** The confirm half was already read for the other measures in steps
9–12. Choosing the cutoff on explore and reading it on confirm keeps this measure's own choice
honest, but it does not make the result confirmatory. A real test is a registration on fresh
data, with the variant and the cutoff fixed from this exploration.
