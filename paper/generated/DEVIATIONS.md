# Deviations from the plan

*What reviewers call a Long Method is a length.* Daniel Sagenschneider, 2026.

This is the full account of every departure of the analysis as run from the plan as registered
(`PLAN.md`, tag `plan-v1`, 20 October 2026). The paper's Section 3 summarises it; every number
here is written by `paper/scripts/tables.py` from the analysis files named in `README.md`; a
value reads `n/a` where its file is absent. Amendments to the plan are each a dated commit stating what had been seen when it was made; this document says what each one
changed in what the paper reports.

## 1. The human populations held only the repositories with a positive (Amendment 10)

**What the plan says.** Each human definition (MLCQ Blob, MLCQ Long Method, Fontana's God
Class) is scored on the units its reviewers reviewed, and a repository whose reviewed units hold
no positive is kept, its reviewed units negatives.

**What the harness did.** The code that attaches a human definition to a repository's score
(`concentration_divergence_study/units.py`, in `_oracles_from_idx` for the joined set and in
`javaparser_set` for the JavaParser-only set) required the record to name the positive label as
well as its `_reviewed` universe. A repository with reviewed units and no positive therefore
carried no human definition and never entered a human population.

**When it was found, and what had been seen.** The confirmatory analysis of 2026-10-26 09:49:15 UTC
(`results/analysis.v2.json`, sha256 `9519e2466f44…`) had been read in full and its
results reported to the author in a draft of the paper before the fault was found, in the course
of explaining why the populations' sizes differed from the label counts. That differs from
Amendment 9, where nothing had been read. Against it: the fix is required by the plan's
"Fixed in advance" whatever the results say; its target is fixed by the plan's text, so no choice
was open that knowledge of the results could steer; and the units it restores are negatives that
either arm may flag, so the direction of its effect on any paired difference was not known when
it was made.

**What was done.** The condition was changed to attach a definition whenever its universe is
present, with no positives when the record names none (`tests/test_units.py` checks it); a tool
definition is still attached only when the tool ran. The explore-half choices of
2026-10-26 07:54:14 UTC were set aside as `decisions/*.v1.json` and step 7 was run again by the
registered rules; the analysis of 2026-10-26 09:49:15 UTC was set aside as `results/analysis.v2.json`
and step 8 was run again as the confirmatory analysis, into `results/analysis.json`
(sha256 `9aa901ddc12b…`, 2026-10-26 14:55:06 UTC).

**What it restored.**

| Population | Set aside (positive repositories only) | Reported (as registered) | Restored |
|---|---|---|---|
| MLCQ confirm Blob | 67 repositories, 548 reviewed classes, 98 Blob | 208 repositories, 934 classes, 98 Blob | 141 repositories, 386 classes, all negatives |
| MLCQ confirm Long Method | 78 repositories, 711 reviewed methods, 125 positive | 202 repositories, 1033 methods, 125 positive | 124 repositories, 322 methods |
| MLCQ explore Blob (X\* and the gate) | 81 repositories | 205 repositories | 124 repositories |
| MLCQ explore Long Method (X\*\_m) | 69 repositories | 212 repositories | 143 repositories |
| Fontana God Class | 51 systems, 305 labelled classes | 72 systems, 380 classes | 21 systems, 75 classes |

**What moved.** The explore-half choices: X\* nloc_max (pooled MCC 0.277)
before, nloc_max (0.287) after, unchanged; X\*\_m cognitive
(0.638) before, cognitive (0.600) after, unchanged; the gate
108 before (explore estimate −0.063 [−0.178, +0.054], half-width
0.116), 72 after (−0.063 [−0.155, +0.034], half-width
0.095). The headline readings, set aside against reported:

| Reading | Set aside | Reported |
|---|---|---|
| Primary, X\*·D_flow minus X\* (pooled MCC) | −0.075 [−0.191, +0.045], no difference resolved (underpowered) | −0.041 [−0.130, +0.054], no difference resolved (underpowered) |
| Repositories with a reviewed Blob against the gate | 66 of 108 | 66 of 72 |
| MCC of X\* alone / of X\*·D_flow | 0.212 / 0.136 | 0.187 / 0.146 |
| Precision of X\* alone / of X\*·D_flow | 0.38 / 0.26 | 0.26 / 0.19 |
| Pooled AUC of X\* / of X\*·D_flow | 0.767 / 0.620 (−0.147 [−0.201, −0.093]) | 0.768 / 0.631 (−0.137 [−0.195, −0.080]) |
| X\*·D_flow against the size null X\*·N | −0.127 [−0.230, −0.021] | −0.091 [−0.175, −0.006] |
| X\*·D_flow against exemption only X\*·E_flow | −0.087 [−0.166, −0.012] | −0.066 [−0.130, −0.000] |
| Leaf diagnostic, flow, non-private (catchment rate, rest rate, difference) | 36.4%, 37.9%, −0.016 [−0.273, +0.271] | 21.1%, 27.8%, −0.068 [−0.238, +0.102] |
| P1, ΔD peak / density | +0.018 [−0.068, +0.112] / +0.062 [−0.041, +0.161] | +0.041 [−0.031, +0.114] / +0.094 [+0.013, +0.174] |
| P1, ΔO peak / density | +0.147 [+0.061, +0.234] / +0.162 [+0.068, +0.255] | +0.125 [+0.054, +0.195] / +0.151 [+0.076, +0.227] |
| P3, ΔDO peak | −0.128 [−0.199, −0.062] | −0.084 [−0.139, −0.029] |
| Verdict on the construct | outgoing data only | outgoing data only |
| Method level, X\*_m·D_flow minus X\*_m | −0.136 [−0.231, −0.041], it makes it worse | −0.092 [−0.188, +0.010], no difference resolved |
| Fontana, X\*·D_flow minus X\* | −0.118 [−0.260, +0.020], no difference resolved | −0.093 [−0.220, +0.035], no difference resolved |
| Primary on the JavaParser-only set | −0.084 [−0.205, +0.032] | −0.050 [−0.142, +0.049] |

## 2. The confirmatory analysis was written three times (Amendments 9 and 10)

1. `results/analysis.v1.json` (2026-10-26 08:04:12 UTC, sha256 `d64d4c8d547f…`):
   Fontana's systems resolved to their source archives for 19 of
   73 systems, because the corpus names its archives to no one pattern, and one
   seed-3 repository without a PMD report. Set aside by Amendment 9 before any of its results
   was read. On Fontana it had 100 labelled classes and 46 God
   Classes and read the primary's paired difference as −0.203 [−0.337, −0.074],
   it makes it worse; its primary was −0.075 [−0.191, +0.045] and its construct verdict
   outgoing data only.
2. `results/analysis.v2.json` (2026-10-26 09:49:15 UTC, sha256 `9519e2466f44…`): the
   complete samples, on the populations restricted to the repositories with a positive
   (Section 1 above). Set aside by Amendment 10 after its results had been read.
3. `results/analysis.json` (2026-10-26 14:55:06 UTC, sha256 `9aa901ddc12b…`): the complete
   samples on the populations as registered. The paper reports this one.

Each file's digest is in `analysis-hashes.txt`, whose git history dates each entry.

## 3. Amendments made before any confirm or seed-3 repository was measured (Amendments 1 to 8)

Each is a commit after the tag `plan-v1` stating what had been seen. Those that change what the
paper reports:

- **Amendment 1 (20 October).** The extra file rule is matched against the source root, not the
  whole path, after it deleted a package named `build`.
- **Amendment 2 (20 October).** Constructors are not inputs of a class; the registered variant
  with constructors counted is kept beside the primary and marked agrees or differs. The
  measurer's call-resolution budget is set at 8 hours per repository.
- **Amendment 3 (20 October).** An exploratory intersection of the complexity and divergence
  outlier sets, labelled exploratory, with no prediction and no verdict.
- **Amendment 4 (21 October).** The exemption and the amplification of the divergence factor are
  tested apart (the X·E and X·A arms), and the mechanism of a refinement is read from the
  exemption-only arm and the leaf diagnostic.
- **Amendment 5 (21 October).** A size null arm, X·N, read beside the primary.
- **Amendment 6 (21 October).** The effective-sample gate is sized from the estimand's own
  bootstrap half-width on the explore half; the gate as first registered is written beside it
  (73 from a per-repository standard deviation of 0.434) and does not
  decide.
- **Amendment 7 (21 October).** Three diagnostics and two sensitivities on the measurement: the
  rule fitted on the non-exempt units only, the reviewed units that carry no coupling, and the
  share of outgoing coupling that is a thrown exception.
- **Amendment 8 (22 October).** Related work from the Qualitas Corpus's maintainer recorded for
  the paper; nothing registered changes.

## 4. Faults in measuring the registered samples (Amendment 9)

Each a fault in the harness or the machine, not in the design, fixed in the code and the
affected repositories measured again, recorded in each set's `run.json` (`forgotten`): a verdict
read as not estimable instead of failing; the Fontana fetch's own records excepted from the
dirty check; temporary files moved off a small RAM-backed `/tmp`; the seed-3 draw repeated with a
larger target after a network outage and a full filesystem (the first draw kept under
`sample/attempt-1/`); clones restricted to the files a measurement reads; the measurer's heap
raised from 6 to 9 GB after one repository spent its budget in garbage collection; PMD run with a
16 MB thread stack after overflowing on deeply nested code; a repository with no Java units scored
with every count zero; the Fontana source archives located by content rather than by name; the
validation run resumed after a network outage. One seed-3 repository (elastic/elasticsearch)
still produces no PMD report and enters every cell but those of the oracles PMD defines.

## 5. The gate was not met

The confirm half carries 66 repositories with a reviewed Blob against the
72 the explore half's half-width implied, and MLCQ has no more. The primary is
marked underpowered by the plan's rule; its confirm half-width is 0.092.

## 6. Labelled units that land on no measured unit

MLCQ: 5 reviewed Blob classes and 2
reviewed Long Method units lie on files the extra file rule drops (out of scope by the plan);
1,060 reviewed Blob classes are labelled on the confirm half and
934 land on a measured unit, 110 Blobs of which
98. Fontana: of 420 instances on 384
files, 380 files land on a measured unit; the three that do not are
trove's benchmark classes, all negatives, outside its source jar.

## 7. A post hoc exploration after every oracle had been read

After the confirmatory analysis on the registered populations was read, the candidate forms
the full report's Section 5.9 reports (the paper's Section 4) (size times outgoing calls at class level; the "makes a call"
gate at method level) were computed from the raw records by `scripts/exploratory_ranking.py`
(20261026 232945 UTC, sha256 `4bd479a1814c…`), read at a matched flag rate and as a threshold-free
AUC by `scripts/exploratory_matched.py` (20261026 234905 UTC, sha256 `d6b77463f469…`), and the
registered matrix recomputed on a logarithmic scale by `scripts/exploratory_log_matrix.py`
(20261026 230649 UTC, sha256 `2fa130f412f6…`), and MLCQ's individual reviews joined to the measured
units by `scripts/exploratory_reviewers.py` (20261026 235742 UTC, sha256 `321ac1632447…`); each read
against every oracle, both MLCQ halves included. After those had been read, the constant on length
the reviews imply was chosen on the explore half and read on the confirm half, and two further
readings were made on the same half: the live width a reader holds, the variable counts and the
data flow of every method, by `scripts/exploratory_livewidth.py` over the facts of a second
measurer pass (20261028 071327 UTC, sha256 `944570d5aa1b…`; step 13), and the cost of cutting a long
method into pieces under that constant, by `scripts/exploratory_split.py` (20261028 143738 UTC, sha256
`9abdee6de69f…`; step 14). The confirm half is therefore a hold-out for the constant on length
alone. Nothing registered changes; the forms are hypotheses for a next registration, chosen
by looking, and the paper labels every number from them as post hoc.
