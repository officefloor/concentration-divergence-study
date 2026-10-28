# Deviations from the plan

*Does coupling divergence tell a god unit from a complex algorithm?* Daniel Sagenschneider, 2026.

This is the full account of every departure of the analysis as run from the plan as registered
(`PLAN.md`, tag `plan-v1`, 20 October 2026). The paper's Section 6 summarises it; every number
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

**When it was found, and what had been seen.** The confirmatory analysis of {{priorMadeUtc}}
(`results/analysis.v2.json`, sha256 `{{analysisVTwoShaShort}}…`) had been read in full and its
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
{{priorDecisionsMadeUtc}} were set aside as `decisions/*.v1.json` and step 7 was run again by the
registered rules; the analysis of {{priorMadeUtc}} was set aside as `results/analysis.v2.json`
and step 8 was run again as the confirmatory analysis, into `results/analysis.json`
(sha256 `{{analysisShaShort}}…`, {{analysisMadeUtc}}).

**What it restored.**

| Population | Set aside (positive repositories only) | Reported (as registered) | Restored |
|---|---|---|---|
| MLCQ confirm Blob | {{priorPrimRepos}} repositories, {{priorPrimUniv}} reviewed classes, {{priorPrimPos}} Blob | {{primRepos}} repositories, {{primUniv}} classes, {{primPos}} Blob | {{restoredBlobRepos}} repositories, {{restoredBlobUnits}} classes, all negatives |
| MLCQ confirm Long Method | {{priorMethRepos}} repositories, {{priorMethUniv}} reviewed methods, {{priorMethPos}} positive | {{methRepos}} repositories, {{methUniv}} methods, {{methPos}} positive | {{restoredLongRepos}} repositories, {{restoredLongUnits}} methods |
| MLCQ explore Blob (X\* and the gate) | {{priorXClassRepos}} repositories | {{xClassRepos}} repositories | {{restoredExploreBlobRepos}} repositories |
| MLCQ explore Long Method (X\*\_m) | {{priorXMethodRepos}} repositories | {{xMethodRepos}} repositories | {{restoredExploreLongRepos}} repositories |
| Fontana God Class | {{priorFontanaSystems}} systems, {{priorFontanaUniv}} labelled classes | {{fontanaPopSystems}} systems, {{fontanaPopUniv}} classes | {{restoredFontanaSystems}} systems, {{restoredFontanaUnits}} classes |

**What moved.** The explore-half choices: X\* {{priorXClass}} (pooled MCC {{priorXClassMcc}})
before, {{xClass}} ({{xClassMcc}}) after, {{xClassChanged}}; X\*\_m {{priorXMethod}}
({{priorXMethodMcc}}) before, {{xMethod}} ({{xMethodMcc}}) after, {{xMethodChanged}}; the gate
{{priorGateRequiredExplore}} before (explore estimate {{priorGateExploreEstimate}}, half-width
{{priorGateHalfWidth}}), {{gateRequired}} after ({{gateExploreEstimate}}, half-width
{{gateHalfWidth}}). The headline readings, set aside against reported:

| Reading | Set aside | Reported |
|---|---|---|
| Primary, X\*·D_flow minus X\* (pooled MCC) | {{priorPrimMicro}}, {{priorPrimVerdict}} | {{primMicro}}, {{primVerdict}} |
| Repositories with a reviewed Blob against the gate | {{priorGateReposWithBlob}} of {{priorGateRequired}} | {{primGateReposWithBlob}} of {{gateRequired}} |
| MCC of X\* alone / of X\*·D_flow | {{priorPrimXMcc}} / {{priorPrimDMcc}} | {{primXMcc}} / {{primDMcc}} |
| Precision of X\* alone / of X\*·D_flow | {{priorPrimXPrecision}} / {{priorPrimDPrecision}} | {{primXPrecision}} / {{primDPrecision}} |
| Pooled AUC of X\* / of X\*·D_flow | {{priorPrimAucX}} / {{priorPrimAucD}} ({{priorPrimAucDiff}}) | {{primAucX}} / {{primAucD}} ({{primAucDiff}}) |
| X\*·D_flow against the size null X\*·N | {{priorDvsNMicro}} | {{primDvsNMicro}} |
| X\*·D_flow against exemption only X\*·E_flow | {{priorDvsEMicro}} | {{primDvsEMicro}} |
| Leaf diagnostic, flow, non-private (catchment rate, rest rate, difference) | {{priorLeafCatchRate}}, {{priorLeafRestRate}}, {{priorLeafDiff}} | {{leafCatchRate}}, {{leafRestRate}}, {{leafDiff}} |
| P1, ΔD peak / density | {{priorPOneDPeak}} / {{priorPOneDDensity}} | {{pOneDPeak}} / {{pOneDDensity}} |
| P1, ΔO peak / density | {{priorPOneOPeak}} / {{priorPOneODensity}} | {{pOneOPeak}} / {{pOneODensity}} |
| P3, ΔDO peak | {{priorPThreePeak}} | {{pThreePeak}} |
| Verdict on the construct | {{priorConsVerdict}} | {{consVerdict}} |
| Method level, X\*_m·D_flow minus X\*_m | {{priorMethMicro}}, {{priorMethReading}} | {{methMicro}}, {{methReading}} |
| Fontana, X\*·D_flow minus X\* | {{priorFontanaMicro}}, {{priorFontanaReading}} | {{fontanaMicro}}, {{fontanaReading}} |
| Primary on the JavaParser-only set | {{priorJpPrimMicro}} | {{primJpMicro}} |

## 2. The confirmatory analysis was written three times (Amendments 9 and 10)

1. `results/analysis.v1.json` ({{analysisVOneMadeUtc}}, sha256 `{{analysisVOneShaShort}}…`):
   Fontana's systems resolved to their source archives for {{fontanaVOneSystems}} of
   {{fontanaSystems}} systems, because the corpus names its archives to no one pattern, and one
   seed-3 repository without a PMD report. Set aside by Amendment 9 before any of its results
   was read. On Fontana it had {{fontanaVOneUniv}} labelled classes and {{fontanaVOnePos}} God
   Classes and read the primary's paired difference as {{fontanaVOneMicro}},
   {{fontanaVOneReading}}; its primary was {{primVOneMicro}} and its construct verdict
   {{consVOneVerdict}}.
2. `results/analysis.v2.json` ({{priorMadeUtc}}, sha256 `{{analysisVTwoShaShort}}…`): the
   complete samples, on the populations restricted to the repositories with a positive
   (Section 1 above). Set aside by Amendment 10 after its results had been read.
3. `results/analysis.json` ({{analysisMadeUtc}}, sha256 `{{analysisShaShort}}…`): the complete
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
  ({{gateVOneRequired}} from a per-repository standard deviation of {{gateVOneS}}) and does not
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

The confirm half carries {{primGateReposWithBlob}} repositories with a reviewed Blob against the
{{gateRequired}} the explore half's half-width implied, and MLCQ has no more. The primary is
marked underpowered by the plan's rule; its confirm half-width is {{primHalfWidthConfirm}}.

## 6. Labelled units that land on no measured unit

MLCQ: {{labelsBlobReviewedDeleted}} reviewed Blob classes and {{labelsLongReviewedDeleted}}
reviewed Long Method units lie on files the extra file rule drops (out of scope by the plan);
{{labelsBlobReviewedLabelled}} reviewed Blob classes are labelled on the confirm half and
{{labelsBlobReviewedMeasured}} land on a measured unit, {{labelsBlobLabelled}} Blobs of which
{{labelsBlobMeasured}}. Fontana: of {{fontanaInstances}} instances on {{fontanaFilesReviewed}}
files, {{fontanaFilesReviewedMeasured}} files land on a measured unit; the three that do not are
trove's benchmark classes, all negatives, outside its source jar.

## 7. A post hoc exploration after every oracle had been read

After the confirmatory analysis on the registered populations was read, the candidate forms
the full report's Section 5.9 reports (the paper's Section 5.2) (size times outgoing calls at class level; the "makes a call"
gate at method level) were computed from the raw records by `scripts/exploratory_ranking.py`
({{expMadeUtc}}, sha256 `{{expShaShort}}…`), read at a matched flag rate and as a threshold-free
AUC by `scripts/exploratory_matched.py` ({{matchedMadeUtc}}, sha256 `{{matchedShaShort}}…`), and the
registered matrix recomputed on a logarithmic scale by `scripts/exploratory_log_matrix.py`
({{logMadeUtc}}, sha256 `{{logShaShort}}…`), and MLCQ's individual reviews joined to the measured
units by `scripts/exploratory_reviewers.py` ({{revMadeUtc}}, sha256 `{{revShaShort}}…`); each read
against every oracle, both MLCQ halves included. After those had been read, the constant on length
the reviews imply was chosen on the explore half and read on the confirm half, and two further
readings were made on the same half: the live width a reader holds, the variable counts and the
data flow of every method, by `scripts/exploratory_livewidth.py` over the facts of a second
measurer pass ({{lwMadeUtc}}, sha256 `{{lwShaShort}}…`; step 13), and the cost of cutting a long
method into pieces under that constant, by `scripts/exploratory_split.py` ({{splitMadeUtc}}, sha256
`{{splitShaShort}}…`; step 14). The confirm half is therefore a hold-out for the constant on length
alone. Nothing registered changes; the forms are hypotheses for a next registration, chosen
by looking, and the paper labels every number from them as post hoc.
