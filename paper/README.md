# The paper

*Does coupling divergence tell a god unit from a complex algorithm? A pre-registered test of
weighting complexity concentration by the data a unit hands on.*

## What is here

| File | Purpose |
|---|---|
| `main.tex` | The paper. Self contained: no `.bib`, the bibliography is a `thebibliography` environment. Every number is a macro from `generated/numbers.tex`, every table an `\input` of `generated/tab_*.tex`. It names no code, commit, file or command; those are in `anc-README.md`. |
| `generated/` | The tables and the number macros, written by `scripts/tables.py` from `../results/analysis.json` and what it rests on. **Tracked**, so the paper builds on a fresh clone with no results. |
| `scripts/tables.py` | The one script behind every number and table; its docstring says what it reads. Run it with the harness's virtualenv from the repository root. |
| `anc-README.md` | The ancillary README packed into the arXiv bundle as `anc/README.md`: the key to every repository, commit, file and command. **Every GitHub link and commit lives here**, not in the paper. |
| `regeneration.txt` | The map from every table and inline number to the analysis section and command that produces it; packed as `anc/REGENERATION.txt`. |
| `build.sh` | `pdflatex` twice, `abstract.txt` (git-ignored) and `arxiv.tar.gz` (git-ignored) with the ancillary data under `anc/`. |

## Build

    ../.venv/bin/python scripts/tables.py     # from the repository root: .venv/bin/python paper/scripts/tables.py
    ./build.sh                                 # main.pdf, abstract.txt, arxiv.tar.gz

The build needs only `main.tex` and `generated/`, so it works on a clone with no results and no
Python. `./build.sh` packs the ancillary data from `../results/`, `../decisions/`, `../sample/`
and `../labels/` when they are present and warns about what is missing.

## What the paper reports

The paper reports `results/analysis.json`, the confirmatory analysis made after the population
fault of PLAN.md Amendment 10 was fixed; the two analyses set aside (`results/analysis.v1.json`,
`results/analysis.v2.json`) and the first explore choices (`decisions/*.v1.json`) are read by
`scripts/tables.py` for the ancillary `DEVIATIONS.md`, which tabulates every headline reading
before and after the fix. `deviations.template.md` is that document's template; the generator
fills it from the same macros the paper uses.

## Publishing

arXiv primary class `cs.SE`. Reserve the Zenodo DOI and define `\thedoi` in `main.tex` before
submitting; `build.sh` prints the abstract's character count against arXiv's limit.
