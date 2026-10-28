# Concentration divergence: what reviewers call a Long Method is a length

The measurement harness for the study pre-registered in [`PLAN.md`](PLAN.md) (tag `plan-v1`),
on the construct in [`SINEW.md`](SINEW.md). It asks whether weighting a Java unit's complexity
by its **coupling divergence** (the data it hands on minus the data it receives) recovers the
classes and methods people call god units better than complexity alone, by setting complex
leaves aside.

It is built on the companion
[complexity-concentration study](https://github.com/officefloor/complexity-concentration-study)
(paper one) and reuses it unchanged: paper one's package is installed from its pinned commit and
supplies the complexity extractor (lizard), the outlier rules, the statistics, the PMD and CK
panels and the MLCQ converter, so every baseline number is the number paper one produces on the
same unit. This study adds the coupling: a JavaParser measurer with its symbol solver
(`measurer/`).

Everything that produced a number is in this repository as code. The steps below are the whole
procedure; nothing is done by hand. Fontana's files are fetched by `scripts/fetch_fontana.sh`
before step 6, which records where they came from and their hashes.

## Reproducing the study

```
./step1_setup.sh          # venv (paper one @ pinned commit, sampler, numpy), PMD + CK, the measurer, tests
./step2_validate.sh       # the measurer on the exploration material (paper one's seed-2 Java sample)
./step3_sample.sh         # MLCQ prepared; the seed-3 Java draw; the 500 measured after exclusions
./step4_run_mlcq.sh       # every MLCQ repository at its labelled commit, then scored
./step5_run_seed3.sh      # the seed-3 sample, then scored
./step6_run_fontana.sh    # Fontana's God Class on the Qualitas Corpus (after scripts/fetch_fontana.sh)
./step7_explore.sh        # the explore-half choices -> decisions/ ; commit them
./step8_analyse.sh        # the confirmatory analysis, once -> results/analysis.json ; ./record_hashes.sh
```

The exploration made after every oracle had been read (PLAN.md, Amendments, 10) follows, one
step per post hoc analysis, in the order it was done. None of it is confirmatory: each writes
`results/exploratory/<name>.<utc>.json` (`kind: exploratory`, its sha256 beside it) and ends with
`./record_hashes.sh`.

```
./step9_explore_ranking.sh     # size x calls and the leaf gate (scripts/exploratory_ranking.py)
./step10_explore_matched.sh    # AUC and matched flag rate (scripts/exploratory_matched.py)
./step11_explore_log_matrix.sh # the registered matrix on a log scale (scripts/exploratory_log_matrix.py)
./step12_explore_reviewers.sh  # MLCQ's individual reviews (scripts/exploratory_reviewers.py)
./step13_explore_livewidth.sh  # live width (LIVEWIDTH.md): re-fetches every repository, then scores
./step14_explore_split.sh      # split cost (SPLIT.md): reads step 13's facts, no fetching
```

Needs python3 (3.10+), git, Java 17+, Maven 3 and, for step 3, the GitHub CLI authenticated.
The measurer runs with a 9 GB heap (`CDS_MEASURER_HEAP`, `pins.py`), so a machine of 14 GB or
more; with less, the largest repositories can spend their time budget in garbage collection
(PLAN.md, Amendments, 9f).
Each script states at its head what it does and what it needs, and prints the next step.

### Run and analyse are separate

Measuring is slow (hours per set: a clone, paper one's extractor, PMD, CK and the measurer per
repository); analysing is fast. The two are kept apart so a fault found while things run is fixed
without measuring again:

| layer | written by | holds | a fault there is fixed by |
|---|---|---|---|
| **record** `results/<set>/repos/<key>.json.gz` | steps 2, 4, 5, 6 (`cds study`) | everything raw: paper one's row and per-unit values and oracles, PMD's raw findings, the measurer's per-method parameters, calls and their resolution, the human labels as given | fixing the code, `cds forget --results D --key K --reason R` (recorded in `run.json`; the old record is kept under `repos/superseded/`), re-running the step: only those repositories are measured again |
| **score** `results/<set>/scores/<key>.npz` | `cds score` (inside steps 4–8) | every form × rule × definition's confusion counts, per repository and result set, and the per-unit extracts the secondaries need | fixing the code: a score is recomputed automatically whenever the scoring modules (or its record) change |
| **analysis** `results/analysis*.json` | step 8 (`cds analyse`) | the estimands, intervals, readings and verdicts | fixing the code and re-running step 8 (before the confirmatory run: `--check`; after it: `--exploratory`) |

Every measuring step is resumable (re-run the same command; failures are retried), every row
records the harness commit that measured it, and a resume by another commit is recorded as a new
session in `run.json`.

### What may be read when

The plan's order is enforced by the code, not by discipline:

- Steps 2–6 measure and score; they print progress only, never a result.
- Step 7 (`cds explore`) opens only the scores whose row is in the MLCQ **explore** half. It
  writes `decisions/explore-choices.json` (X\*, X\*\_m and the effective-sample gate, with every
  candidate's criterion) and `decisions/measurer-validation.mlcq-explore.json`, once.
- `./step8_analyse.sh --check` runs the whole analysis on the explore half alone, to find faults
  in the analysis code before anything confirmatory is read.
- Step 8 refuses to run until `decisions/explore-choices.json` is committed and unchanged, and
  writes `results/analysis.json` once (with its sha256); any later analysis is
  `analysis.exploratory.<utc>.json`. `./record_hashes.sh` writes `analysis-hashes.txt`; commit it.
- A fault in the harness is fixed in the code and the steps re-run (PLAN.md, Fixed in advance);
  what the fault set aside is kept beside the re-run, never deleted: `results/analysis.v*.json`
  and `decisions/*.v1.json` (PLAN.md, Amendments, 9 and 10), each still hashed.

## The design in code

| PLAN.md | where |
|---|---|
| complexity: paper one's extractor and its 10 method / 31 class signals, unchanged | `pyproject.toml` pins paper one's commit; `pins.py` refuses any other; `measure.py` calls `study.analyse` |
| coupling: JavaParser with its symbol solver, no build, no dependencies; internal = resolves to an analysed file | `measurer/src/.../Measurer.java` (rules in its header); `javaparser.py` checks it on a fixture before every run |
| the extra file rule (test roots, build directories at any depth) | `files.py`, applied to the clone before any tool runs |
| the two result sets, joined (decides) and JavaParser-only (robustness) | `units.py` |
| flow, data, message; all-calls / no-helpers; class form A (non-private / public, without and with constructors) and B; the exploratory intersection (d alone, X AND d, X AND O) | `units.py`, `forms.py` |
| fD, fO, every form of the matrix, AND | `forms.py` |
| every rule of paper one at its default constant, fitted on every unit | `rules.py` (exactly paper one's flags: `tests/test_rules.py`) |
| oracles: MLCQ Blob and Long Method (reviewed units, strict majority, frozen split), seed-3 tool oracles, Fontana | `mlcq.py`, `sample.py`, `fontana.py`; definitions in `units.py` |
| moved MLCQ repositories | `mlcq-moved-repositories.csv` (built by `scripts/find_moved_repositories.py`), applied in `mlcq.py` |
| X\*, the gate | `core.py`, `explore.py` |
| the primary estimand, the bootstrap (2000, seed 12345) | `core.compare`, `boot.py` (paper one's draws: `tests/test_boot.py`) |
| the leaf diagnostic, secondaries, consistency analysis and verdict, sensitivities | `analyse.py` |
| diagnostics read first | `validate.py`, `analyse.diagnostics` |

## Inputs committed here

- `inputs/paper-one/` — copies of paper one's frozen inputs: its seed-2 samples and their
  derivations (`sample/`), its pilot list, and its MLCQ split (`mlcq-halves.json`, paper one's
  `results/mlcq/halves.json`). `cds mlcq-prepare` checks that the split is the one
  `stats.assign_halves` gives on the MLCQ sample it regenerates, and that the sample is the file
  the split was frozen on.
- `mlcq-moved-repositories.csv` — the MLCQ repositories whose labelled commit moved, with their
  verified new locations.
- `sample/` (after step 3) — the seed-3 draw, its derivation and the selection.
- `decisions/` (after step 7) — the explore-half choices.

Not committed: `results/` (many GB), `labels/` (the MLCQ download and its conversion, regenerated
by `cds mlcq-prepare`), `lib/` (PMD and CK, downloaded by step 1), Fontana's files. Their hashes
are in `analysis-hashes.txt`.

## Interests

The author created OfficeFloor; see PLAN.md, Interests.
