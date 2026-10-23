# Seed-3 draw, attempt 1 (superseded)

The first seed-3 draw (`./step3_sample.sh`, target 540 usable, sampler 0.1.0 @ 7502a158), drawn
2026-10-23 (10:15 to 15:31 UTC) and kept as the record of why it was redrawn. It is not measured.

**Why it was redrawn.** `cds seed3-select` found 56 of the 540 usable repositories in the exclusion
lists (paper one's Java supplement 25, MLCQ 24, paper one's pilot 10, paper one's main sample 3),
leaving 484 of the 500 needed. The margin of 40 was too small, so `pins.SEED3_DRAW_TARGET` was raised
to 580 and the draw repeated into `sample/` (the selection code's own instruction).

**Its errors were the machine's, not the repositories'.** 139 of its 810 candidates are `error`:

- 131 are `Could not resolve host: github.com`, contiguous at draws 244 to 374: a network outage.
- 8 are `unable to write file` (draws 8 to 455): large clones that did not fit the RAM-backed `/tmp`.

**The draw was edited once.** After `/tmp` reached its per-user quota, every clone failed and the
sampler recorded 26 `Disk quota exceeded` errors (draws 562 to 587). The run was stopped, the step
scripts moved their temporary files to the project's `.tmp/` (commit 8052f87), and those 26 rows,
the last in the progress file, were cut so the draw resumed at draw 562 and re-drew them.
`.seed3.progress.before-quota-truncation.jsonl` is the progress file as it was before the cut.

Files: `open-source-repository-sample.seed3.csv` and its `.derivation.json` as the sampler wrote
them; `.seed3.progress.before-quota-truncation.jsonl` as above.
