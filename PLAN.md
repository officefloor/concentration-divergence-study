# Pre-registered analysis plan (DRAFT, not registered)

> **Status (19 October 2026): draft for the author's review.** Nothing below is registered
> until this file is committed and tagged (`plan-v1`). Sections marked **OPEN** are decisions
> still to make; every one must be closed, or moved to an explore-half choice with its
> criterion stated, before the tag. No measurement code exists yet, and none is to be written
> against data before the tag except on the exploration material named under *Exploration*.

## The question

The companion
[complexity-concentration study](https://github.com/officefloor/complexity-concentration-study)
(paper one) asks whether a scale-free relative outlier rule (modified z ≥ 3.5 on per-unit
complexity, fitted per repository) recovers god classes as well as a tuned absolute
threshold. The author's working view, formed from that study's main results, is that
complexity concentration does find god classes and methods but cannot tell a **god unit** from
a **complex algorithm**: a leaf that legitimately holds the complexity of what it computes.

This study asks whether **coupling divergence**, the data a method hands on to the rest of the
system against the data it receives, separates the two:

> In Java, does weighting a unit's complexity by its coupling divergence recover the units
> people call god classes and methods better than complexity alone, by setting complex leaves
> aside?

**Purpose.** A definition of a god class or method with **no raw-scale threshold**, so that it
moves with the codebase it is applied to, including as AI-maintained code changes what a
"normal" level of complexity is. The only constant is the outlier rule's 3.5 on a standardised
axis, taken from the literature and not tuned here: the rule is scale-free, not constant-free
(as in paper one).

**Scope.** The health of the code under management: classes and methods inside one
repository. Not architecture: whether a service is a "god service" in a fleet of services is
outside this study, as it is outside what OfficeFloor sets out to address.

**Not in this study.** Early signs in git history that a unit is becoming a god unit. That is
the next study, once a detector exists (see the draft hypotheses H1–H3 in
`sinew-identification-study/paper/SINEW.md`); it will be registered separately.

## What was seen before this plan

Stated so a reader can judge what could have shaped it:

- **Paper one's main confirmatory analysis** (PMD GodClass oracle, seed 2) was read before this
  plan was written. It motivates the question (the relative rule flags many classes PMD does
  not), so it is not evidence for it.
- **Paper one's MLCQ results** (step 5 and the exploratory step 5a) were **not** read when this
  draft was written. **OPEN:** tag this plan before reading them, or record the date they were
  read relative to the tag. Tagging first keeps MLCQ a clean oracle for this study (below).
- **Exploratory petclinic observations** in `sinew-identification-study/paper/SINEW.md`: on
  AI-evolved petclinic code, the **outgoing** arguments carried the signal for later outlier
  status and the balance (out − in) added little. That observation was seen first, so the
  outgoing-only arm below is a pre-registered secondary, not a post-hoc addition.

## Units and measures

**Complexity: every measure of paper one, unchanged.** Complexity is measured by paper one's
extractor at its released commit, so every baseline number is the number paper one would
produce on the same unit:

- **Method signals** (paper one's `COMPLEXITY_FIELDS`, with its families): size `nloc`,
  `tokens`, `hvol`; structure `cc`, `cognitive`, `nesting`, `exit_points`; density
  `cyc_density`, `mi`, `params`.
- **Class signals:** each method field aggregated per file as `_sum`, `_mean` and `_max`, plus
  `nom`: 31 signals in the families size (every `_sum`, `nom`), peak (every `_max`) and density
  (every `_mean`).

**Coupling: JavaParser with its symbol solver**, which paper one's extractor (lizard) cannot
provide. Its per-method `in` and `out` are **joined to paper one's units** by file and start
line (paper one's `_labelled_unit_at` handling of annotations). Reported as diagnostics: the
share of lizard units joined, and the methods JavaParser finds that lizard does not (paper one
found lizard silently drops the methods after some class-level field initialisers, such as
`X = B << C`). **OPEN:** joined measurement as above (exact comparability with paper one), or
every field re-implemented on JavaParser (one parser, no blind spot, but a new baseline that
must be validated against lizard).

- **Method unit:** paper one's (every function lizard reports in a `.java` file).
- **Class unit:** the file (unit = file, as in paper one).
- **in:** the number of parameters the method declares (a varargs parameter counts once).
- **out:** the sum, over the method's **internal** calls (below), of the number of arguments
  passed. Calls are method calls, constructor calls (`new T(...)`) and explicit
  `this(...)`/`super(...)` calls.
- **Divergence:** `d = out − in`.
- **Internal call:** a call whose target the symbol solver resolves to a declaration in the
  repository's own analysed sources. Resolution uses the repository's source roots plus the JDK
  (reflection type solver), with no build and no dependencies. A call that resolves to the JDK
  is external. A call that does not resolve at all is **external** (almost always a dependency's
  type, which is what "external" means here). The number of unresolved calls, and those whose
  receiver type *is* declared in the repository but whose method could not be resolved
  ("should have resolved"), are reported per repository.
- **Analysed sources:** `.java` files outside any path segment named `build`, `target`,
  `generated`, `generated-sources`, `out` or `bin`, at **any** depth (paper one skipped build
  directories only at the root, which let Mindustry's generated code in). **OPEN:** whether test
  sources (`src/test/`, `test/` roots) are analysed; MLCQ labels a few test classes.

**OPEN, the Kay rule.** `SINEW.md` proposes not counting the first parameter and the first
argument of each call (a method receives one message). Default here: **plain counts** (the
author's definition), with the Kay variant as a labelled sensitivity analysis.

**OPEN, same-class calls.** At method level, a call to another method of the same class is
internal and counts. At class level, see the class score below.

## The leaf exemption and the score

A negative divergence marks a **catchment**: a leaf that receives data and processes it, which
is where the complexity of an algorithm belongs. Such a method is exempt. Zero (a pipe) and
positive (a junction) count, with complexity weighted by how much more it hands on:

```
fD(m) = max(d(m) + 1, 0)     # divergence factor: d < 0 → 0;  d = 0 → 1;  d = k > 0 → k + 1
fO(m) = out(m) + 1           # outgoing factor (the petclinic observation)
```

For **every** method complexity field X of paper one, three forms of the signal:

```
X          complexity alone (paper one's signal, unchanged)
X·D(m)   = X(m) × fD(m)
X·O(m)   = X(m) × fO(m)
```

and the coupling factors on their own: `D = fD` and `O = fO`. Class signals aggregate each
method form exactly as paper one aggregates X (`_sum`, `_mean`, `_max`), so `cognitive·D_max`
is the largest `cognitive × fD` over the file's methods. `nom` has no method form and stays
complexity alone.

**`params` and D.** `params` is the method's `in`, which `fD` already contains, so `params·D`
counts the parameters twice. It is measured and reported but **excluded** from the primary
choice below.

The exemption is a **hypothesis**, tested by the leaf diagnostic below, not assumed.

**OPEN, structural leaves.** By sign alone, a method with no parameters and no internal calls
scores d = 0 and is not exempt, though it is a leaf. Alternative: exempt any method with **no
internal calls** as well as any with d < 0. Pick one; the other is a sensitivity analysis.

**OPEN, class-level `out`.** Whether a class's method forms count every internal call, or only
calls that leave the class (so a class whose private helpers call each other does not look like
a hub). The other is a sensitivity analysis.

## The matrix

Every signal form is scored by **every** rule of paper one (`mad_z`, `double_mad`, `iqr`,
`adj_boxplot`, `evt_pot`, `pct_top1`, and `zscore` as its parametric control), at each rule's
default constant, fitted on **every** unit of the repository at that level, zeros included,
exactly as paper one. The scale kind (MAD, mean-AD fallback, constant) is recorded per
repository, signal and form, because exempt units add zeros. Against every oracle below this
gives, per level:

| form | method signals | class signals |
|---|---|---|
| complexity alone, X | 10 | 31 |
| X·D | 10 | 30 |
| X·O | 10 | 30 |
| D, O alone | 2 | 6 (`_sum`, `_mean`, `_max` of each) |

plus, as a sensitivity, **AND**: a unit flagged by the rule on X **and** by the rule on `d`
(both outliers, no compensation), for the primary signal only.

The full matrix is reported, labelled by role. Only the comparison below decides.

## Oracles and populations

1. **Primary: MLCQ human Blob** (class level), scored only on the classes MLCQ's reviewers
   reviewed, with paper one's strict-majority aggregation and its explore/confirm split of the
   MLCQ repositories (`results/mlcq/halves.json`, frozen before measurement). Humans are the
   only oracle that can arbitrate "god unit or complex algorithm"; tool definitions encode a
   threshold, and PMD's GodClass already contains a coupling measure (ATFD), which would make
   agreement partly circular.
2. **Secondary: MLCQ human Long Method** (method level), same split and aggregation.
3. **Secondary, tool oracles on a fresh random sample:** PMD GodClass, DECOR Blob and PMD
   NPath (method), on Java repositories drawn by `open-source-repository-sampler` with
   **seed 3** (seeds 1 and 2 are seen). Repositories that appear in paper one's pilot (seed 1),
   its seed-2 sample or MLCQ are **excluded** from this sample before measurement. Reported
   with the ATFD caveat; never the headline.

**OPEN:** a second human Java dataset (Arcelli Fontana et al.'s God Class labels on the
Qualitas Corpus; Palomba et al.'s Landfill Blob) as a replication oracle.

## Primary estimand and decision

- **The base signal X\* is chosen by complexity alone.** On the MLCQ **explore** half, among
  paper one's primary families (class: peak and density; never size, never `params`), the
  signal X whose `mad_z` flags maximise the pooled MCC against human Blob over the reviewed
  units. The multiplied form is **not** consulted, so the divergence factor cannot pick a
  signal it happens to win on. If paper one's chosen signal (`cognitive_max`) is wanted
  instead, **OPEN:** fix it now and skip the choice.
- **Estimand:** the pooled (micro) MCC of **X\*·D** minus **X\*** (both by `mad_z`) against
  MLCQ human Blob, over the reviewed class units of the MLCQ **confirm** repositories, as a
  paired difference.
- **Interval:** 95% percentile bootstrap resampling repositories, 2000 resamples, seed 12345
  (paper one's).
- **Reading (superiority, since the claim is a refinement):** lower bound above 0, *the
  divergence factor refines complexity*; upper bound below 0, *it makes it worse*; otherwise *no difference resolved*.
- **Reported beside it, not deciding:** precision, recall and false-positive rate of each arm
  (the hypothesis predicts higher precision at a small cost in recall); macro MCC; the
  threshold-free pooled AUC of X\*·D against X\* (modified z versus modified z).
- **Effective-sample gate:** **OPEN**, set from the explore half before confirm is read
  (paper one used 40 repositories carrying the definition). Below it, the verdict is marked
  *underpowered*.

## Pre-registered secondary tests

1. **The leaf diagnostic (the exemption's own test).** Among units X\* flags, the human Blob
   rate of catchments (d < 0) against the rest, paired bootstrap over repositories. The
   exemption is supported if catchments are called Blob less often (upper bound below 0);
   contradicted if more often; otherwise unresolved. Reported whatever the primary says.
2. **Independence of the two measures.** Within-repository Spearman correlation of every
   complexity field with `d` and with `out`. If they track closely, X·D is close to a
   stretched X; the primary is then re-read within complexity strata (tertiles of X\* per
   repository) to show `d` adds information beyond X\*.
3. **X\*·O, D, O and AND** against X\*, same estimand, labelled secondary, no multiplicity
   correction, none can change the primary.
4. **The matrix, by family.** For every signal and rule, the form (X, X·D, X·O) difference
   against X, with intervals, reported as exploratory, with Friedman tests over repositories
   across forms within each family, as paper one did across signals and rules. A claim that
   the factor helps *in general* must hold within a family that is not size.
5. **Method level:** the same, against MLCQ Long Method, X\* chosen on the structure and
   density families.
6. **Tool oracles** on the seed-3 sample (above).

## Does the construct hold up: the consistency analysis

The primary asks whether one detector improves. This section asks whether **coupling
divergence**, and the sinew construct behind it (`SINEW.md`: data riding on the control flow),
holds up across ways of defining a god unit and ways of calculating complexity. It is
pre-registered with its predictions, and read after the primary.

**Cells.** Every combination of:

- **oracle:** each god definition, textbook or human: MLCQ human Blob and Long Method, PMD
  GodClass, DECOR Blob, WMC ≥ 47, PMD NPath, and `brain_method` (internal);
- **level:** class or method, as the oracle defines;
- **family** of the complexity signal: size, peak, density (class) or size, structure, density
  (method);
- **relation:** whether the signal is an **ingredient** of the oracle's definition (paper one's
  ingredient rule, `study.ingredients`; for example `cc_sum` is WMC) or **not**.

**Per cell,** by `mad_z`, three paired micro MCC differences over the cell's repositories, each
averaged over the signals in the cell:

```
ΔD  = MCC(X·D) − MCC(X)       does divergence refine?
ΔO  = MCC(X·O) − MCC(X)       does outgoing data alone refine?
ΔDO = MCC(X·D) − MCC(X·O)     does what comes in matter (the sinew's balance)?
```

**Intervals.** One percentile bootstrap (2000, seed 12345) resamples **repositories** once per
replicate and recomputes every cell from that replicate, so the dependence between cells (same
repositories, correlated signals) is carried into every interval. Cells are never counted as
independent evidence.

**How cells are read.**

- **Ingredient cells** test whether the factor *damages* a signal that matches the definition
  (complexity alone is near its ceiling there). Reported, not counted toward the construct.
- **PMD GodClass cells** contain coupling in the definition (ATFD), so a gain is partly
  circular. Reported, not counted toward the construct.
- **Counted cells:** non-ingredient cells of every other oracle.

**Predictions (OPEN: the author confirms or changes these before the tag).** If the construct
holds:

1. **P1, refinement.** ΔD > 0 (lower bound above 0) for MLCQ human Blob in the peak and density
   families. These are the families where one complex method makes a class an outlier, which
   is where a complex algorithm and a god unit are confused.
2. **P2, where it helps.** ΔD is larger in peak and structure families than in size families
   (paired difference of the cell estimates, same bootstrap). Size sums already favour classes
   with many methods, which leaves are not.
3. **P3, the balance matters.** ΔDO ≥ 0 for human Blob in the counted families: what a method
   receives adds to what it sends. Competing expectation, recorded from the petclinic
   observations: ΔDO ≤ 0 (outgoing data carries the signal). Reading: lower bound above 0
   supports the sinew's balance; upper bound below 0 supports outgoing-only; otherwise
   unresolved.
4. **P4, generality.** Among counted cells of the tool oracles, the ΔD estimates are
   positive in a majority, reported with each cell's interval. This is a descriptive pattern,
   not a test.

**Verdict on the construct.** *Supported* if P1 holds and P3 does not read outgoing-only.
*Outgoing data only* if P1 holds for ΔO and P3 reads outgoing-only. *Not supported* if neither
ΔD nor ΔO has a lower bound above 0 for human Blob in any non-size family. Otherwise
*unresolved*. Exploratory beyond these: every other rule of paper one, every individual signal
and the method-level cells, in the full matrix.

## Diagnostics, read first

Cognitive complexity agreement with PMD; resolution rates (resolved internal, JDK, unresolved,
"should have resolved") per repository; share of units in each role (catchment, pipe,
junction); zero shares and scale kinds per arm; the share of MLCQ labels that land on a
measured unit; files excluded as generated; owner concentration.

**Calls static parsing cannot see.** Dependency injection, reflection, event listeners and
configuration-defined flows hide real calls, so `out` reads low and some hubs look like leaves.
Repositories declaring a DI framework (Spring, Guice, CDI, Dagger, Micronaut, Quarkus, read from
`pom.xml` / `build.gradle`) are counted, and the primary is re-read without them as a labelled
sensitivity.

## Exploration

Measure design (resolution rules, exclusions, the OPEN items that are not fixed by the author)
may be developed and checked only on: paper one's MLCQ **explore** half, paper one's seed-2
Java sample (already read in paper one), and the petclinic runs already used in `SINEW.md`.
Nothing is measured on the MLCQ confirm half or the seed-3 sample before the tag.

## Fixed in advance

- Java only. Results are for Java; other languages, especially dynamically typed ones where
  call targets cannot be resolved statically, are untested and need labelled data first.
- The outlier rule and its constant (`mad_z`, 3.5), and the bootstrap (2000, seed 12345).
- Sample seed 3 for the tool-oracle sample; exclusions as above.
- Every analysis after the first confirmatory one is written to a dated
  `analysis.exploratory.<utc>.json`; the confirmatory `analysis.json` is written once and its
  sha256 committed.
- Generated data is never edited; a fault is fixed in the code, the output deleted and the
  step re-run, and the re-run is recorded.

## Procedure

1. Close the OPEN items; commit this plan; tag `plan-v1`.
2. Build the JavaParser measurer; validate it on the exploration material only; commit.
3. Measure the MLCQ repositories at their labelled commits (both halves) and draw and measure
   the seed-3 sample. The harness commit is recorded in every row and must not be `-dirty`.
4. Make the explore-half choices the plan delegates (class score, if left to explore; the gate).
5. Run the confirmatory analysis once; commit its hash.
6. Report the primary, then the leaf diagnostic, then the consistency analysis and its verdict
   on the construct, then the secondaries, then the sensitivities.

## Interests

The author created OfficeFloor. This study does not compare frameworks and samples repositories
at random; the interest is declared because the coupling construct comes from the same line of
work (`SINEW.md`).
