# Ancillary data for the paper

*Does coupling divergence tell a god unit from a complex algorithm? A pre-registered test of
weighting complexity concentration by the data a unit hands on.* Daniel Sagenschneider, 2026.

This directory holds the data the paper is computed from and the key to every public repository,
commit, file and command involved. The paper itself names none of these; everything a reader
needs to trace a number to its source is here. The raw per-repository records (the harness's
`results/<set>/repos/*.json.gz`, several gigabytes per set) are **not** included: they regenerate
by running the harness on the sample files below, which pin every repository to its commit and
every Qualitas system to its archive's sha256. `REGENERATION.txt` maps every table and inline
number to the command that produces it.

## The repositories

Everything is public and Apache-2.0 licensed unless stated.

| Repository | What it is |
|---|---|
| https://github.com/officefloor/concentration-divergence-study | **The harness and the paper.** The pre-registered plan (`PLAN.md`, tag `plan-v1` = commit `6ef3883`, 20 October 2026, with its nine dated amendments), the construct (`SINEW.md`), the measurement harness (`concentration_divergence_study/`), the JavaParser measurer (`measurer/`), the numbered step scripts, the samples (`sample/`), the explore-half decisions (`decisions/`), the committed digests (`analysis-hashes.txt`) and the paper with its generator (`paper/`). The confirmatory analysis's `harness_commit` is recorded inside `analysis.json`; the two set aside were written by `a809d0a` (`analysis.v1.json`, tag `analysis-v1` = `bd0e84f`) and `4d73bc1` (`analysis.v2.json`). |
| https://github.com/officefloor/complexity-concentration-study | **The companion study (paper one).** Installed at commit `0f8e654` (byte-identical in code to `393da76`, which measured the first MLCQ rows); supplies the complexity extractor (lizard 1.23.0), the outlier rules, the statistics and bootstrap, the PMD and CK panels, the MLCQ converter and the frozen explore/confirm split. Its paper: doi:10.5281/zenodo.23581333. |
| https://github.com/officefloor/open-source-repository-sampler | **The sampler**, release 0.2.1: drew the seed-3 sample from GitHub's index and the criteria alone, and clones each repository at its pinned commit with a filter for the files a measurement reads. |
| https://github.com/javaparser/javaparser | **JavaParser 3.28.2** with its symbol solver: the coupling measurer's parser and call resolution (`measurer/pom.xml`). |
| https://pmd.github.io | **PMD 7.27.0**: the GodClass and NPath oracles and the cognitive-complexity check; run with a 16 MB thread stack. |
| https://github.com/mauricioaniche/ck | **CK 0.7.0** (jar sha256 `2ddfdc275b6b59c2033e03253c4fec511c338fe494a10b70f651bc039a72c74d`): the class counts the approximate DECOR Blob is composed from. |
| https://zenodo.org/records/3666840 | **MLCQ 1.1** (Madeyski and Lewowski 2020), the human-labelled data set, CC BY 4.0; downloaded by the harness and verified by sha256 (`labels/mlcq-summary.json` holds the input's digest). |
| https://drive.usercontent.google.com/download?id=15aXc_el-nx4tQwU3khunQ-I5ObSA1-Zb | **Fontana's MLCSD binary-class data sets** (Arcelli Fontana et al. 2016); `binary_class/god-class.csv` is the God Class oracle. The page that links it states no licence. |
| http://www.cs.auckland.ac.nz/~ewan/download/corpus/ | **The Qualitas Corpus**, release 20130901 (r, e and f distributions), the source of Fontana's systems; used with the maintainer's written agreement (`labels/ACCESS.md`), not redistributed. |

## What is here

### `analysis/` : the analyses of record

| File | What it is |
|---|---|
| `full-report/report.tex`, `full-report/report.pdf` | **The full registered report.** The paper keeps three things (the claim failing, the constant on length, the next form of the construct); this is the complete account the plan commits to, every secondary, sensitivity, tool oracle, Fontana replication, Friedman test, intersection, matched-rate and log-scale reading, and the size-times-calls exploration, built from the same generated numbers and tables. Section numbers quoted as "full report" below refer to it. |
| `analysis.json`, `.sha256` | **The confirmatory analysis** the paper reports (`kind: confirmatory`; its `made_utc`, `harness_commit` and sha256 are inside it and in `analysis-hashes.txt`). Every primary, secondary, sensitivity and diagnostic number in the paper is read from it. Its sections: `diagnostics`, `primary`, `leaf`, `consistency`, `secondary`, `sensitivity`, `exploratory_intersection`, each for the `joined` and `javaparser` result sets. |
| `analysis.v1.json`, `.sha256` | The first confirmatory analysis (2026-10-26 08:04 UTC, commit `a809d0a`, sha256 `d64d4c8d…`), set aside by Amendment 9 because Fontana's archives had resolved for 19 of 73 systems; none of its results had been read. |
| `analysis.v2.json`, `.sha256` | The second (2026-10-26 09:49 UTC, commit `4d73bc1`, sha256 `9519e246…`), set aside by Amendment 10: the human populations held only the repositories with a positive. Its results had been read and reported to the author in a draft of the paper before the fault was found. `DEVIATIONS.md` tabulates every headline reading of this file against the reported one. |
| `analysis.exploratory.<utc>.json` | Any later re-analysis (none existed when the paper was built). |
| `matched.<utc>.json`, `.sha256` | **Ranking or flag rate** (paper, Section 5.2; full report, Section 5.9): for the registered arms and the exploratory forms, the threshold-free pooled AUC of the per-repository modified z and of the per-repository percentile over the reviewed units, with the paired bootstrap against X\*, and every form read at a matched flag rate (the constant that gives it as many flags over every unit as X\*·O_flow has at 3.5; at method level as tokens has), by `scripts/exploratory_matched.py`. Post hoc. |
| `log-matrix.<utc>.json`, `.sha256` | The registered matrix with ln(1 + X) in place of every complexity signal X, scored by the registered rule against every oracle and paired with the raw form from the score files, by `scripts/exploratory_log_matrix.py`. Post hoc; reported in one sentence of the full report's Section 5.9 because a logarithm compresses the tail and the rule then flags almost nothing. |
| `reviewers.<utc>.json`, `.sha256` | **What the reviewers judge** (paper, Section 5.2; full report, Section 5.9): MLCQ's individual reviews (reviewer, severity) joined to the measured units, by `scripts/exploratory_reviewers.py`: the Long Method rate by length bin for leaves (no internal call) and the rest, per reviewer, the disagreement among multiply reviewed samples, each reviewer's own best length cutoff, and the Blob rate and disagreement by class size. Post hoc. |
| `livewidth.<utc>.json`, `.sha256`; `livewidth-units.<utc>.csv.gz`, `.sha256` | **Live width** (paper, Section 5.2; full report, Section 5.9): a second measurer pass over every measured repository (`LiveWidth`, no symbol solver) records each method's variables, their reference and definition lines, its loops, calls and statement tree; `scripts/exploratory_livewidth.py` scores the live width a reader holds at a line (several definitions), the variable counts and the data flow against every oracle by the registered rule and by absolute cutoffs chosen on the explore half and read on the confirm half, length among them. The cutoff on length is the constant the paper reports. The units file holds every reviewed method's values. Post hoc (step 13). |
| `split.<utc>.json`, `.sha256`; `split-units.<utc>.csv.gz`, `.sha256` | **The split cost** (paper, Section 5.2; full report, Section 5.9): for every method at or over the constant, the cheapest segmentation into pieces under it (`scripts/split.py` over the live-width facts): the worst seam, its cost, its binding to the class, and the structural-only and no-input-limit variants, scored by `scripts/exploratory_split.py` as the live width is, with the AUC among the long methods only and the locked share at class level. The units file holds every reviewed method's values and the cuts of its best segmentation. Post hoc (step 14). |
| `ranking.<utc>.json`, `.sha256` | **The post hoc exploration** (paper, Section 5.2; full report, Section 5.9): every candidate form built from size and outgoing calls, scored from the raw records by `scripts/exploratory_ranking.py` (in the harness repository) by the registered rule against every oracle, with paired bootstrap differences against the best complexity-alone signal and the size-only counterparts. Made after every oracle had been read; labelled `kind: exploratory`; its `harness_commit` is inside it and its digest in `analysis-hashes.txt`. |
| `analysis-hashes.txt` | The committed digests of the analyses, the decisions, the labels, the samples and each set's run and validation records. |

### `decisions/` : the explore-half choices

| File | What it is |
|---|---|
| `explore-choices.json` | X\*, X\*\_m, the effective-sample gate and every candidate's criterion, made on the MLCQ explore half by the registered rules (its `made_utc` and `harness_commit` are inside it); the paper's Section 5.1 (full report, Section 5.2). |
| `measurer-validation.mlcq-explore.json` | The measurer's agreement with paper one's extractor and its resolution rates on the explore half. |
| `explore-choices.v1.json`, `measurer-validation.mlcq-explore.v1.json` | The choices first made (2026-10-26 07:54 UTC, commit `a809d0a`) on the populations restricted to the repositories with a positive, set aside by Amendment 10 and kept with their digests. |
| `DEVIATIONS.md` (at `anc/`) | The full account of every deviation from the plan, written by `paper/scripts/tables.py` from the analysis files: the population fault and what it restored, the three confirmatory analyses, the amendments, the measurement faults, the gate, and the labelled units that land on no measured unit. |

### `mlcq/`, `seed3/`, `fontana/`, `validation/` : the measured sets

| File | What it is |
|---|---|
| `run.json` | The set's sessions: when each started, the harness commit, every tool's version, the sample and labels it read with their digests, and the repositories forgotten and re-measured (`forgotten`). |
| `validation.json` | The diagnostics read first: join share, complexity agreement, call resolution, PMD cognitive agreement, files failed, pruned files, DI frameworks, labels landing on measured units. |
| `study.json` | One row per repository or system: identity, commit or archive, half, usability, counts, labels, pruned files, DI, the harness commit that measured it. |
| `run-log.jsonl` | The sampler's clone log (not for Fontana, measured from archives). |

The harness commits that measured each set are recorded in the rows and in `run.json`: MLCQ
`89447ed`, `c45f4f1`, `716ff49`; seed-3 `4f8b1a5`, `716ff49`; Fontana `5cf5fbb`; the validation
set (paper one's seed-2 Java supplement, the exploration material) `ec6ecce`, `716ff49`.

### `sample/` : what pins every repository

| File | What it is |
|---|---|
| `open-source-repository-sample.seed3.csv`, `.derivation.json` | The seed-3 draw (target 580 usable, seed 3, tiers high/mid/low, Java only, the author's organisations excluded): every candidate, its pinned commit, and how the draw was made (command, every GitHub query, the sampler's version and commit). |
| `seed3-measured.csv`, `.json` | The 500 measured: the first 500 usable in draw order that appear in no exclusion list (paper one's pilot and seed-2 samples, MLCQ), with the 62 excluded and why. |
| `attempt-1/` | The first draw (target 540), abandoned after a network outage and a full temporary filesystem; kept with its note. |
| `mlcq-halves.json` | Paper one's frozen explore/confirm assignment of the 522 MLCQ repositories. |
| `pilot-run-v1-repos.txt` | Paper one's pilot list, an exclusion list for the seed-3 draw. |
| `mlcq-moved-repositories.csv` | The 23 MLCQ repositories whose labelled commit moved to another GitHub location, with the verified location, how it was found and the date checked. |

### `labels/` : the oracles

| File | What it is |
|---|---|
| `mlcq-labels.csv`, `mlcq-labels.mapped.csv` | MLCQ converted by paper one's converter (strict majority): `blob`, `blob_reviewed`, `long_method`, `long_method_reviewed` with lines; the mapped file points moved repositories at their new URLs. |
| `mlcq-repos.csv`, `mlcq-repos.mapped.csv`, `mlcq-frame.json`, `mlcq-summary.json` | The repositories at their labelled commits as a sampler CSV, the frame, and the counts with the input's sha256. |
| `fontana-labels.csv`, `fontana-systems.csv` | Fontana's 420 instances as `fontana_god_class_reviewed` and the 140 God Classes as `fontana_god_class`, by system and class; each system's archive and its sha256. |
| `ACCESS.md`, `SHA256SUMS` | Where Fontana's files and the corpus came from, the terms as read, the maintainer's reply, and the sha256 of every file fetched. |

### `PLAN.md`, `SINEW.md`

The pre-registered plan as amended (every amendment dated, with what had been seen) and the
construct.

## Reproducing

From a clone of the harness repository (python3 3.10+, git, Java 17+, Maven 3, the GitHub CLI
for step 3; a machine of 14 GB or more, the measurer runs with a 9 GB heap):

    ./step1_setup.sh          # venv with paper one @ 0f8e654, sampler 0.2.1, numpy; PMD, CK; the measurer; tests
    ./step2_validate.sh       # the measurer on the exploration material (results/validation)
    ./step3_sample.sh         # MLCQ prepared; the seed-3 draw; the 500 selected
    ./step4_run_mlcq.sh       # every MLCQ repository at its labelled commit, scored
    ./step5_run_seed3.sh      # the seed-3 sample, scored
    scripts/fetch_fontana.sh && ./step6_run_fontana.sh
    ./step7_explore.sh        # decisions/ (commit them)
    ./step8_analyse.sh        # results/analysis.json, once; ./record_hashes.sh
    .venv/bin/python paper/scripts/tables.py && cd paper && ./build.sh

Measuring the published sample files measures exactly the repositories and commits this paper
did, for as long as GitHub serves those commits and the corpus serves its archives. The
measurer's time budget (8 hours per repository) and heap (`CDS_MEASURER_HEAP=9g`) are the
constants recorded in `concentration_divergence_study/pins.py`.

### The post hoc exploration (paper, Section 5.2; full report, Section 5.9)

    .venv/bin/python scripts/exploratory_ranking.py              # every set, mad_z, ~5 minutes
    .venv/bin/python scripts/exploratory_ranking.py --all-rules  # every rule of paper one
    ./record_hashes.sh                                           # adds its digest to analysis-hashes.txt

It reads `results/<set>/repos/*.json.gz`, builds the forms in its docstring from the measurer's
per-call data (the plain internal-call count, fan-out as distinct callee files, the method gate
"makes at least one call"), and writes `results/exploratory/ranking.<utc>.json`. The paper's
generator reads the latest such file (or `--ranking FILE`) for the full report's Section 5.9 tables and
inline numbers.

    .venv/bin/python scripts/exploratory_matched.py       # AUC and matched flag rate, ~7 minutes
    .venv/bin/python scripts/exploratory_log_matrix.py    # the log-scale matrix, ~3 minutes with 6 workers
    .venv/bin/python scripts/exploratory_reviewers.py     # the reviews themselves, ~3 minutes

The paper's generator reads the latest of each (`--matched FILE`, `--log-matrix FILE`).

    ./step13_explore_livewidth.sh     # the live-width pass over every repository (fetches again; hours), then the scores
    ./step14_explore_split.sh         # the split cost over step 13's facts, no fetching, ~3 hours

The paper's generator reads the latest `livewidth.*.json` and `split.*.json` for the constant on
length and the readings against it (paper, Section 5.2; full report, Section 5.9, *A constant on length, and what was tried against it*).

### The population fault (paper, Section 6; `DEVIATIONS.md`, 1)

The condition that attaches a human definition to a repository's score is in
`concentration_divergence_study/units.py` (`_oracles_from_idx` for the joined set, `javaparser_set`
for the JavaParser-only set). It was changed, in the commit that records Amendment 10, to attach
the definition whenever its `_reviewed` universe is present; `tests/test_units.py` checks it.
Steps 7 and 8 were then run again by the commands above; what they set aside is kept as
`decisions/*.v1.json` and `results/analysis.v2.json`.
