# Pre-registered analysis plan

> **Status (20 October 2026): registered, tag `plan-v1`.** No measurement code existed at
> registration. Any later change to this plan is its own commit after the tag.

## The question

The companion
[complexity-concentration study](https://github.com/officefloor/complexity-concentration-study)
(paper one) asks whether a scale-free relative outlier rule (modified z ≥ 3.5 on per-unit
complexity, fitted per repository) recovers god classes as well as a tuned absolute
threshold. The working view, formed from that study's main results, is that
complexity concentration does find god classes and methods but cannot tell a **god unit** from
a **complex algorithm**: a leaf that legitimately holds the complexity of what it computes.

This study asks whether **coupling divergence**, the data a method hands on to the rest of the
system against the data it receives, separates the two:

> In Java, does weighting a unit's complexity by its coupling divergence recover the units
> people call god classes and methods better than complexity alone, by setting complex leaves
> aside?

Coupling divergence is the measurable part of the **sinew** construct (data coupled to the
control flow), described in [`SINEW.md`](SINEW.md).

**Purpose.** A definition of a god class or method with **no raw-scale threshold**, so that it
moves with the codebase it is applied to, including as AI-maintained code changes what a
"normal" level of complexity is. The only constant is the outlier rule's 3.5 on a standardised
axis, taken from the literature and not tuned here: the rule is scale-free, not constant-free
(as in paper one).

**Scope.** The health of the code under management: classes and methods inside one
repository. Not architecture: whether a service is a "god service" in a fleet of services is
outside this study, as it is outside what OfficeFloor sets out to address.

**Not in this study.** Early signs in git history that a unit is becoming a god unit. That is
the next study, once a detector exists; it will be registered separately.

## What was seen before this plan

Stated so a reader can judge what could have shaped it:

- **Paper one's main confirmatory analysis** (PMD GodClass oracle, seed 2) was read before this
  plan was written. It motivates the question (the relative rule flags many classes PMD does
  not), so it is not evidence for it.
- **Paper one's MLCQ results** (step 5 and the exploratory step 5a) were **not** read when this
  draft was written. The commit history records the order: the first draft (with the question,
  the MLCQ oracle and the primary estimand) is committed before those results existed, every
  later change to this plan is its own commit, and the commit adding paper one's
  `mlcq-hashes.txt` dates the MLCQ results. A change made after that date is visible as such
  and can be judged on its diff.
- **Part of paper one's step 5 output was seen before registration,** while checking that the
  run was progressing: its primary against the PMD GodClass oracle on the MLCQ repositories
  (verdict inconclusive), the explore-half choice for the Brain Method oracle (`cognitive`), the
  last lines of its exploratory method-level summary, and about ten lines that an earlier,
  crashed run printed (a ranking against the PMD oracle on the MLCQ repositories, and
  exploratory CK and DECOR lines). **No result against the human labels** (Blob or Long
  Method) was seen. Changes to the plan made after that output appeared are dated in the
  commit history.
- **Exploratory petclinic observations** (the role shares are in
  [`SINEW.md`](SINEW.md)): on AI-evolved petclinic code, the **outgoing** arguments
  carried the signal for later outlier status and the balance (out − in) added little. That observation was seen first, so the
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
`X = B << C`).

**Two result sets.** Every analysis in this plan is run twice, on two measurements of the same
checkouts:

1. **Joined (primary):** complexity by paper one's extractor, coupling by JavaParser, joined as
   above. Units are paper one's: every function lizard reports in a `.java` file, and the
   file. The baseline is exactly paper one's, which is why this set decides.
2. **JavaParser only (robustness):** every complexity field re-implemented on JavaParser's
   syntax tree, so complexity, parameters and calls come from one parser and no method is
   lost to lizard's blind spot. Units: every method and constructor with a body, including
   those of nested and anonymous classes (lambdas belong to their enclosing method), and the
   file. Each field is validated against lizard's value on the joined units of the
   exploration material, and the agreement (rank correlation and the share of exact matches
   per field) is reported before any result.

The verdicts are read from the joined set. The JavaParser-only set is reported beside it, with
each verdict marked **agrees** or **differs**; a verdict that differs is reported as such, with
the units and fields that drive the difference, and does not change the joined verdict.

- **Class unit:** the file (unit = file, as in paper one), in both sets.
- **Parameters `p`:** the number of parameters the method declares (a varargs parameter counts
  once).
- **Calls:** the method's **internal** calls (below): method calls, constructor calls
  (`new T(...)`) and explicit `this(...)`/`super(...)` calls. `a(c)` is the number of arguments
  passed on call `c`.
- **Coupling, three definitions** ([`SINEW.md`](SINEW.md)), every one measured and analysed:

  | definition k | in | out |
  |---|---|---|
  | **flow**: each call is control flow (+1), each parameter is data coupled to it (+1) | `1 + p` | `Σ (1 + a(c))` |
  | **data**: parameters only; a call with no arguments adds nothing | `p` | `Σ a(c)` |
  | **message** (Kay): the first item is the message, every call at least the message | `max(p − 1, 1)` | `Σ max(a(c) − 1, 1)` |

- **Divergence:** `d_k = out_k − in_k`, for each definition k.
- **Internal call:** a call whose target the symbol solver resolves to a declaration in the
  repository's own analysed sources. Resolution uses the repository's source roots plus the JDK
  (reflection type solver), with no build and no dependencies. A call that resolves to the JDK
  is external. A call that does not resolve at all is **external** (almost always a dependency's
  type, which is what "external" means here). The number of unresolved calls, and those whose
  receiver type *is* declared in the repository but whose method could not be resolved
  ("should have resolved"), are reported per repository.
- **Analysed sources: application code only.** The study is about application code as it
  evolves, which is where OfficeFloor applies; test code is a different question, left to a
  later study. Both result sets use paper one's file rule, which already leaves out test
  directories (the sampler's names: `test`, `tests`, `testing`, `javatests` and the like). On
  top of it, before any rule is fitted, both drop every `.java` file with a path segment named
  - `androidTest`, `testFixtures` or `integrationTest` (test roots paper one's rule does not
    name), or
  - `build`, `target`, `generated`, `generated-sources`, `out` or `bin`, at **any** depth
    (paper one skipped build directories only at the root, which let Mindustry's generated
    code in).

  Both lists are matched against the file's **source root**: its directory less the path of
  its `package` declaration. A segment inside the package path is a package name, not a
  directory of the build, and does not exclude; a file whose directory does not end in its
  package path, or that declares none, has its whole directory checked. *(Amended; see
  Amendments, 1.)*

  The extractor and its measures are unchanged; only the file set differs from paper one's,
  so the units each rule is fitted on can differ. MLCQ labels on dropped files are out of
  scope, and their number is reported.

**The primary definition is flow**, the purest definition of a sinew. All three definitions
run through every analysis below; data and message are pre-registered secondaries.

**Calls within the class (the file).** Method and class are counted differently:

- **Method level: both variants.** Every internal call is part of a method's `out`, so the
  **all-calls** variant counts calls to methods of the same file too, and is the method-level
  headline. A method can push its logic into private helpers, which makes those calls look like
  coupling, so the **no-helpers** variant, which leaves out calls to methods declared in the same
  file, is computed and analysed beside it.
- **Class level: calls that leave the class only, inputs that can enter it only.** Calls
  between a class's own methods are logic inside the class, like the logic inside a method, not
  coupling of the class: a class's `out` counts only calls to methods declared in **another**
  file. A class's `in` counts only the methods that can be called from outside it, private
  methods never. Two input variants, both computed and analysed:
  - **non-private (primary):** `public`, `protected` and package-private methods, everything
    callable from outside the file;
  - **public:** `public` methods only.

  **Constructors are not inputs of the class.** A constructor is structure, how the class is
  built, not a way into what it does, so it adds nothing to a class's `in` in either variant.
  Each input variant is also computed and analysed **with constructors** counted (non-private
  or public constructors, beside the methods), to show the difference. A constructor is still a
  method-level unit with its own coupling, the method level is unchanged, and a call to a
  constructor still counts in `out`. *(Amended; see Amendments, 2.)*

## The leaf exemption and the score

A negative divergence marks a **catchment**: a leaf that receives data and processes it, which
is where the complexity of an algorithm belongs. Such a method is exempt. Zero (a pipe) and
positive (a junction) count, with complexity weighted by how much more it hands on:

For each coupling definition k:

```
fD_k(m) = max(d_k(m) + 1, 0)   # divergence factor: d < 0 → 0;  d = 0 → 1;  d = j > 0 → j + 1
fO_k(m) = out_k(m) + 1         # outgoing factor (the petclinic observation)
```

For **every** method complexity field X of paper one, and every definition k, the forms of the
signal:

```
X           complexity alone (paper one's signal, unchanged)
X·D_k(m)  = X(m) × fD_k(m)
X·O_k(m)  = X(m) × fO_k(m)
```

and the coupling factors on their own: `D_k = fD_k` and `O_k = fO_k`.

**The two halves of the divergence factor, apart** *(Amended; see Amendments, 4)*. `fD_k` does two
things: it exempts a catchment, and it multiplies a junction by `d + 1`, without bound. Each is
measured on its own, for every field, definition and variant:

```
fE_k(m) = [d_k(m) ≥ 0]         exemption only: a catchment is 0, everything else is 1
fA_k(m) = max(d_k(m) + 1, 1)   amplification only: nothing is exempt, a junction is d + 1
X·E_k = X × fE_k               X·A_k = X × fA_k           (fD_k = fE_k × fA_k)
```

At class level (form A) the same, on the class's `d_k(C)`. They are pre-registered secondaries
(secondary 8) and they read the mechanism of the primary (Primary estimand and decision).

**The size null** *(Amended; see Amendments, 5)*. The rival explanation of any class-level gain
is that a Blob is a big class with one complex method: size families are kept out of X\*, but
`d_k(C)` is a sum over the class's methods, so the factor brings size back. For every class
signal X_c except `nom`, `X_c·N = X_c × nom` is measured: the same multiplication with the
class's number of methods, which carries no coupling at all. It is a pre-registered secondary
(secondary 9), read beside the primary.

**Class forms.** Two ways to weight a class, each with both input variants:

- **A. The class as one unit (primary).** The class has its own coupling, and it weights each
  of paper one's 31 class signals X_c (`nom` included):

  ```
  in_k(C)  = Σ in_k(m)  over the methods of C callable from outside (non-private, or public;
                        constructors not counted, or counted in the with-constructors variants)
  out_k(C) = Σ out_k(m) over all methods of C, counting calls that leave C only
  d_k(C)   = out_k(C) − in_k(C)
  X_c·D_k(C) = X_c(C) × max(d_k(C) + 1, 0)        X_c·O_k(C) = X_c(C) × (out_k(C) + 1)
  ```

  A class with a wide callable surface that sends little out is a catchment; one with a narrow
  surface that sends much out is a junction.
- **B. Method forms aggregated (secondary).** Each method's form, with `in_k(m)` counted only if
  the method is callable from outside the class (else 0) and `out_k(m)` counting calls that
  leave the class only, aggregated exactly as paper one aggregates X (`_sum`, `_mean`, `_max`):
  `cognitive·D_flow_max` is the largest `cognitive(m) × fD_flow(m)` over the file's methods.
  `nom` has no method form under B.

**`params` and D.** `params` is the method's `p`, which every `in_k` already contains, so
`params·D_k` counts the parameters twice. It is measured and reported but **excluded** from the
primary choice below.

The exemption is a **hypothesis**, tested by the leaf diagnostic below, not assumed.

**Structural leaves.** A method with no counted calls is a leaf. Under the **flow** and
**message** definitions it is always a catchment (`out = 0`, `in ≥ 1`, so `d < 0`). Under the
**data** definition, one with no parameters scores d = 0 and is not exempt: the data view does
not see calls, so it misses methods with no parameters, by its definition. That difference is
part of what comparing the definitions shows.

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
| X·D_k, for 3 definitions | 60 (all calls; no helpers) | A: 372 (31 × 3 × 4 input variants); B: 360 (30 × 3 × 4) |
| X·O_k, for 3 definitions | 60 (all calls; no helpers) | A: 93 (31 × 3); B: 90 (30 × 3) |
| X·E_k, X·A_k, for 3 definitions *(Amendments, 4)* | 60 + 60 (all calls; no helpers) | A: 372 + 372 (31 × 3 × 4 input variants) |
| X·N, the size null *(Amendments, 5)* | – | 30 (every class signal but `nom`) |
| D_k, O_k alone, for 3 definitions | 12 (all calls; no helpers) | A: 15; B: 45 (`_sum`, `_mean`, `_max`) |

The 4 input variants are non-private and public, each without and with constructors.
`O_k` does not depend on `in`, so it has no input variants.

plus, as a sensitivity, **AND**: a unit flagged by the rule on X **and** by the rule on `d_k`
(both outliers, no compensation), for the primary signal and each definition.

**Exploratory: the intersection of the two outlier sets** *(Amended; see Amendments, 3)*.
Instead of weighting complexity by divergence, each is put through the same rule on its own and
the two flag sets are intersected. Every rule is fitted on:

| form | method | class (form A) |
|---|---|---|
| `d_k`, the divergence itself | 6 (3 × all calls, no helpers) | 12 (3 × 4 input variants) |
| AND, X ∩ `d_k` | 60 (10 × 3 × 2) | 372 (31 × 3 × 4) |
| AND with the outgoing factor, X ∩ `O_k` | 60 (10 × 3 × 2) | 93 (31 × 3) |

They are scored against every oracle like every other form, and so appear in the matrix by
family (secondary 4). For X\* (class and method), by `mad_z`, each definition and variant, the
positives of each oracle are reported by region: flagged on X only, on `d_k` only, on both,
and on either. Each region gets its pooled precision, recall and MCC. The paired micro MCC
difference against X\*, with its interval, is reported for "both", "either" and `d_k` alone.
All of this is exploration: it is read after everything above, labelled exploratory, has no
prediction, and changes no verdict. The registered AND sensitivity is the subset of it with the
candidate signals and the primary variant.

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
   **seed 3** (seeds 1 and 2 are seen), **500 usable** repositories, stratified by tier as the
   sampler does (paper one's Java supplement targeted 150; this study is Java only, so the
   sample is larger and its tool-oracle cells narrower). Repositories that appear in paper
   one's pilot (seed 1), its seed-2 sample or MLCQ are **excluded** from this sample before
   measurement. Reported with the ATFD caveat; never the headline.
4. **Secondary, human replication: Fontana's God Class** (Arcelli Fontana et al., *Empirical
   Software Engineering* 21(3), 2016): 420 manually evaluated God Class instances from 74
   systems of the Qualitas Corpus, a different team, different systems and an older Java from
   MLCQ's. Each rule is fitted on the whole system and scored only on the labelled classes;
   class level only. It is read **only as the paired difference** X\*·D_flow minus X\*, never as
   an absolute level, because:
   - its instances are balanced and extreme, so any detector separates them more easily than in
     real code (Di Nucci et al., SANER 2018); the inflation is on both sides of a paired
     difference;
   - its candidates were found by detection tools before they were checked by hand, so it
     carries some of the tool oracles' circularity;
   - its code is Qualitas Corpus source archives, not git commits, so the harness measures an
     archive (its sha256 recorded) in place of a pinned commit.

   The access terms of the God Class files are checked before measurement and recorded.

**Moved repositories.** Paper one could not fetch 21 MLCQ repositories, 15 of them `eclipse/*`;
several Eclipse projects appear to have moved to new GitHub organisations. A supplementary list,
`mlcq-moved-repositories.csv` (old URL, new URL, labelled commit, how the new location was
found, the date checked), maps each one that has moved to its new location, under one rule: a
new location is accepted **only if the labelled commit SHA exists there**, so the mapped code is
the code the reviewers labelled. Where several locations verify, the one chosen is the
project's own organisation (the old owner, or an owner named after it, as `eclipse-dltk` for
`eclipse`), then one that is not a fork, then the most stars; the others are listed. The
script is `scripts/find_moved_repositories.py`. The list is built from locations and commit
SHAs alone, before any measurement, and is committed with this plan. A mapped repository keeps
the half (explore or confirm) paper one assigned to its old URL. A repository with no verified
new location stays a recorded failure. The number mapped, and the labels they carry, are
reported.

The list holds 23 repositories: the 21, and `apache/ctakes` and `apache/uima-ruta`, whose URLs
remain but no longer hold the labelled commit. All 23 verified: 10 at the project's own
organisation (`eclipse-*`), 13 at copies held by others, where no other location searched
holds the commit. A matching SHA means the same code, whoever holds it.

## Primary estimand and decision

- **The base signal X\* is chosen by complexity alone.** On the MLCQ **explore** half, among
  paper one's primary families (class: peak and density; never size, never `params`), the
  signal X whose `mad_z` flags maximise the pooled MCC against human Blob over the reviewed
  units. The multiplied form is **not** consulted, so the divergence factor cannot pick a
  signal it happens to win on. The choice, its criterion value for every candidate signal, and
  the date are written to a file and committed before the confirm half is read. (Paper one's
  chosen signal, `cognitive_max`, was chosen against PMD's GodClass, not people, so it is not
  carried over.)
- **Estimand:** the pooled (micro) MCC of **X\*·D_flow**, class form A with non-private
  methods as inputs (constructors not counted), minus **X\*** (both by `mad_z`), against
  MLCQ human Blob, over the reviewed class units of the MLCQ **confirm** repositories, as a
  paired difference.
- **Interval:** 95% percentile bootstrap resampling repositories, 2000 resamples, seed 12345
  (paper one's).
- **Reading (superiority, since the claim is a refinement):** lower bound above 0, *the
  divergence factor refines complexity*; upper bound below 0, *it makes it worse*; otherwise *no difference resolved*.
- **With constructors, reported beside it, not deciding:** the same estimand with
  constructors counted in the class's inputs, marked **agrees** or **differs** with the
  primary reading, and the paired difference between the two arms (methods only minus with
  constructors).
- **Reported beside it, not deciding:** precision, recall and false-positive rate of each arm
  (the hypothesis predicts higher precision at a small cost in recall); macro MCC; the
  threshold-free pooled AUC of X\*·D_flow against X\* (modified z versus modified z).
- **The mechanism of a refinement, read beside the primary** *(Amended; see Amendments, 4)*.
  The question names the exemption ("by setting complex leaves aside"), but the factor also
  amplifies junctions, and at class level that amplification grows with the class. So when the
  primary reads *refines*, its mechanism is read, pre-registered, from two things in the
  primary's own variant (flow, non-private, constructors not counted): the exemption-only arm
  X\*·E_flow against X\* (same estimand, same interval), and the leaf diagnostic (secondary 1)
  under flow, non-private. If X\*·E_flow also reads *refines* and the leaf diagnostic is not
  *contradicted*, the refinement is **by the exemption**: the claim in the question is
  supported. Otherwise it is **by amplification**: the gain comes from multiplying junctions,
  a fan-out effect, and the claim that setting complex leaves aside refines complexity is
  **not supported**, although the primary is positive. When the primary does not read
  *refines*, the mechanism is not read. Reported with it: X\*·A_flow against X\*, and
  X\*·D_flow against each of X\*·E_flow and X\*·A_flow. The same reading is made at method
  level for secondary 5, from X\*_m·E_flow on all calls and the method leaf diagnostic.
- **Against the size null, read beside the primary** *(Amended; see Amendments, 5)*. The
  paired difference X\*·D_flow minus X\*·N (same estimand, same interval): lower bound above
  0, *beyond size*, the coupling factor beats a size weighting; upper bound below 0, *the size
  factor beats the coupling factor*; otherwise *not distinguished from a size weighting*. The
  primary's reading is unchanged by it; the claim that **coupling** refines complexity takes
  *beyond size* as its support and the other two readings as a rival explanation left
  standing. X\*·N against X\* is reported with it.
- **Effective-sample gate:** set from the explore half before confirm is read. On the MLCQ
  explore half, the standard deviation `s` of the per-repository paired difference (X\*·D_flow
  minus X\*, over repositories with at least one reviewed Blob) gives the number of confirm
  repositories with at least one reviewed Blob needed for a 95% interval of half-width 0.10,
  `n = (1.96 · s / 0.10)²`, rounded up, and never below 20. The gate, `s` and the date are
  written to a file and committed with the choice of X\* before the confirm half is read
  (paper one used 40). Below the gate, the verdict is marked *underpowered*.

## Pre-registered secondary tests

1. **The leaf diagnostic (the exemption's own test).** Among units X\* flags, the human Blob
   rate of catchments (d_k < 0; for a class, d_k(C) < 0 under form A) against the rest, for
   each definition k and input variant, paired bootstrap over repositories. The
   exemption is supported if catchments are called Blob less often (upper bound below 0);
   contradicted if more often; otherwise unresolved. Reported whatever the primary says.
2. **Independence of the two measures.** Within-repository Spearman correlation of every
   complexity field with `d_k` and with `out_k`, for each definition. If they track closely,
   X·D_k is close to a stretched X; the primary is then re-read within complexity strata
   (tertiles of X\* per repository) to show `d_flow` adds information beyond X\*.
3. **X\*·D and X\*·O under the other two definitions, X\*·O_flow, D_k, O_k and AND; the
   public input variant and both input variants with constructors; class form B** against
   X\*, same estimand, labelled secondary, no multiplicity
   correction, none can change the primary.
4. **The matrix, by family.** For every signal, rule and definition, the form (X, X·D_k, X·O_k) difference
   against X, with intervals, reported as exploratory, with Friedman tests over repositories
   across forms within each family, as paper one did across signals and rules. A claim that
   the factor helps *in general* must hold within a family that is not size.
5. **Method level:** the same, against MLCQ Long Method, X\* chosen on the structure and
   density families, on the all-calls variant; the no-helpers variant is reported beside it,
   with the paired difference between the two.
6. **Tool oracles** on the seed-3 sample (above).
7. **Fontana's God Class** (above): the primary's paired difference, and the leaf diagnostic.
8. **The two halves of the factor** *(Amendments, 4)*: X\*·E_flow and X\*·A_flow against X\*,
   and X\*·D_flow against each, class form A non-private, same estimand and interval; the
   same at method level on all calls; every other definition, variant and signal in the
   matrix. They read the mechanism of the primary (above) and change no verdict.
9. **The size null** *(Amendments, 5)*: X\*·D_flow against X\*·N, and X\*·N against X\*, class
   form A non-private, same estimand and interval, read as stated under Primary estimand and
   decision; every X_c·N in the matrix. It changes no verdict.

## Does the construct hold up: the consistency analysis

The primary asks whether one detector improves. This section asks whether **coupling
divergence**, and the sinew construct behind it (`SINEW.md`: data riding on the control flow),
holds up across ways of defining a god unit and ways of calculating complexity. It is
pre-registered with its predictions, and read after the primary.

**Cells.** Every combination of:

- **oracle:** each god definition, textbook or human: MLCQ human Blob and Long Method,
  Fontana's God Class, PMD
  GodClass, DECOR Blob, WMC ≥ 47, PMD NPath, and `brain_method` (internal);
- **level:** class or method, as the oracle defines;
- **family** of the complexity signal: size, peak, density (class) or size, structure, density
  (method);
- **relation:** whether the signal is an **ingredient** of the oracle's definition (paper one's
  ingredient rule, `study.ingredients`; for example `cc_sum` is WMC) or **not**;
- **coupling definition:** flow, data or message.

Class cells use form A with non-private methods as inputs; form B and the public inputs are
reported the same way beside them. The whole analysis is also run with constructors counted in
the inputs, and its verdict is marked **agrees** or **differs**.

**Per cell,** by `mad_z`, three paired micro MCC differences over the cell's repositories, each
averaged over the signals in the cell:

```
ΔD  = MCC(X·D_k) − MCC(X)        does divergence refine?
ΔO  = MCC(X·O_k) − MCC(X)        does outgoing coupling alone refine?
ΔDO = MCC(X·D_k) − MCC(X·O_k)    does what comes in matter (the sinew's balance)?
```

and, between definitions in the same oracle, family and relation:

```
ΔD(flow) − ΔD(data)       does counting the call itself (the control flow) matter?
ΔD(message) − ΔD(flow)    does treating the first item as the message matter?
```

each read by its interval: lower bound above 0, the first is better; upper bound below 0, the
second; otherwise no difference resolved.

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

**Predictions.** Read on the primary
coupling definition (flow); the same readings on the other two are reported beside them. If
the construct holds:

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

Measure design (the implementation of the resolution rules and exclusions)
may be developed and checked only on: paper one's MLCQ **explore** half, paper one's seed-2
Java sample (already read in paper one), and the petclinic runs already used in `SINEW.md`.
Nothing is measured on the MLCQ confirm half or the seed-3 sample before the tag.

## Fixed in advance

- Java only. Results are for Java; other languages, especially dynamically typed ones where
  call targets cannot be resolved statically, are untested and need labelled data first.
- The outlier rule and its constant (`mad_z`, 3.5), and the bootstrap (2000, seed 12345).
- Sample seed 3 and 500 usable Java repositories for the tool-oracle sample; exclusions as above.
- Every analysis after the first confirmatory one is written to a dated
  `analysis.exploratory.<utc>.json`; the confirmatory `analysis.json` is written once and its
  sha256 committed.
- Generated data is never edited; a fault is fixed in the code, the output deleted and the
  step re-run, and the re-run is recorded.

## Procedure

1. Commit this plan; tag `plan-v1`.
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

## Amendments

Each amendment is its own commit after the tag `plan-v1`, stating what had been seen when it
was made.

1. **20 October 2026: the extra file rule is matched against the source root, not the whole
   path** (Units and measures, Analysed sources). Found while validating the measurer on the
   exploration material (Procedure 2), on paper one's seed-2 Java sample: matched at any depth
   of the whole path, `build` deleted 13 files of spring-projects/spring-restdocs whose
   *package* is `org.springframework.restdocs.build` (Gradle plugin code, under
   `gradle/plugins/*/src/main/java`), and `target` would delete every class of a package such
   as Spring's `org.springframework.aop.target`. The rule was written to drop build output and
   generated sources; a package name is neither. Matching only the source root keeps the
   intent: `core/build/generated/...`, `target/generated-sources/...` and an `androidTest`
   root are still dropped. Seen when amended: the validation runs on two repositories of
   paper one's seed-2 Java sample (spring-restdocs and FlowDroid), which report measurer
   diagnostics only. No MLCQ repository and no seed-3 repository had been measured, and no
   score had been computed against any oracle.

2. **20 October 2026: constructors are not inputs of the class; calls are resolved for up to
   8 hours** (Units and measures, Calls within the class; The leaf exemption and the score,
   class form A; The matrix; Primary estimand; the consistency analysis; secondary 3). As registered, a class's `in` summed every
   non-private (or public) callable, constructors included. A constructor is structure: it
   builds the object, and it is not a way into what the class does, so a class whose
   constructor takes many dependencies is not, by that, receiving data its behaviour consumes.
   The primary and every input variant now count methods only. Each variant is also computed
   and analysed with constructors counted, reported beside it and marked agrees or differs. The
   method level is unchanged (a constructor is a unit with its own coupling), and calls to
   constructors still count in `out`. The change was made by the author on these conceptual
   grounds. With it, the measurer's time budget for resolving calls, which the plan did not
   state, is set at **8 hours per repository** (it was 1 hour): a call met after the budget is
   spent cannot be found internal, so its `out` is lost, and the loss falls on the files
   measured last. openjdk/jdk, the largest Java repository, measured during validation, spent
   1 hour with 22% of its calls not yet resolved. A repository that still spends the 8 hours is
   kept and listed in the diagnostics, and the primary is also reported without such
   repositories, as a sensitivity. Seen when amended: Amendment 1's material; a dry run of
   the harness (scoring and the check analysis) on 8 repositories of the MLCQ **explore** half, in scratch directories,
   whose primary was not estimable (4 repositories with a reviewed Blob); and, after the
   decision, to check the code, the constructors' share of the class inputs on those 8
   repositories (3–30%), with the number of form A catchments under flow rising with
   constructors counted (most in the two Spring repositories). No repository of the MLCQ
   confirm half or of the seed-3 sample had been measured.

3. **20 October 2026: an exploratory intersection of the complexity and divergence outliers**
   (The matrix). The author proposed a second way to combine the two measures, besides
   multiplying them: flag the outliers of the coupling divergence by the same rule as those of
   complexity, and see whether the units in both sets are the god units. The registered AND
   sensitivity already scored that intersection for the primary signal under one variant. It is
   widened to every signal and variant, with the divergence alone and the outgoing factor as
   the second set, and the positives are reported by region. It is labelled exploratory: it
   adds no hypothesis, no prediction and no verdict, and changes nothing registered. Seen when
   amended: as for Amendment 2. Afterwards, to check the code, the dry run on the same 8
   MLCQ explore repositories printed the region counts for human Blob and Long Method (5
   positives each). No repository of the MLCQ confirm half or of the seed-3 sample had been
   measured.

4. **21 October 2026: the exemption and the amplification of the divergence factor are tested
   apart, and the mechanism of a refinement is read** (The leaf exemption and the score; The
   matrix; Primary estimand and decision; Pre-registered secondary tests, 8). The factor
   `fD = max(d + 1, 0)` does two things: it exempts a catchment, and it multiplies a junction
   by `d + 1`, without bound. At class level `d` is a sum over the class's methods, so the
   amplification grows with the class, and a refinement could come from it alone while the
   exemption, which the question names, adds nothing or costs recall. Two forms are added for
   every signal, definition and variant, as pre-registered secondaries: exemption only,
   `X·E_k = X × [d_k ≥ 0]`, and amplification only, `X·A_k = X × max(d_k + 1, 1)`. The primary
   and its reading are unchanged; a pre-registered reading of its mechanism is added beside it,
   from the exemption-only arm and the leaf diagnostic, stated under Primary estimand and
   decision. The change was made on a review of the plan and the harness before any
   measurement of the confirm half. Seen when amended: as for Amendment 3, and nothing more.
   No repository of the MLCQ confirm half or of the seed-3 sample had been measured.

5. **21 October 2026: a size null arm** (The leaf exemption and the score; The matrix; Primary
   estimand and decision; Pre-registered secondary tests, 9). A class-level gain from X\*·D_k
   could be the gain of any weighting by the size of the class, because `d_k(C)` sums over the
   class's methods; secondary 2 only reports the correlation. `X_c·N = X_c × nom` is added for
   every class signal, and X\*·D_flow is read against X\*·N beside the primary, as stated
   there. The primary and its reading are unchanged. Made on the same review as Amendment 4.
   Seen when amended: as for Amendment 4. No repository of the MLCQ confirm half or of the
   seed-3 sample had been measured.
