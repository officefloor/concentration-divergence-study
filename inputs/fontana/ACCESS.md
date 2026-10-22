# Fontana's God Class and the Qualitas Corpus: where they came from

Written by `./scripts/fetch_fontana.sh` on 2026-10-20 (UTC); do not edit by hand, except the
maintainer's reply at the end, which a later run keeps. The sha256 of every file fetched is
in `SHA256SUMS`; the pages quoted are saved in `provenance/`.

## The data set

- MLCSD binary-class datasets (Arcelli Fontana, Mäntylä, Zanoni and Marino, Empirical
  Software Engineering 21(3), 2016), the file the MLCSD page links:
  https://drive.usercontent.google.com/download?id=15aXc_el-nx4tQwU3khunQ-I5ObSA1-Zb&export=download&confirm=t
- `god-class.csv` is `binary_class/god-class.csv` of that archive (sha256 pinned in the script).
- The MLCSD page (provenance/mlcsd.2026-10-20.html) states no licence for the files it links.

## The corpus

- Qualitas Corpus (Tempero et al., APSEC 2010), web distribution of release 20130901, from
  http://www.cs.auckland.ac.nz/~ewan/download/corpus/ ; parts fetched: 12.
- Fontana's data set names versions of the 20120401 release, which is no longer on the web
  ("can be provided if required"); the 20130901 r, e and f distributions together hold the
  complete corpus, every version. System versions the data set names that are not in what was
  fetched: none.
- Terms, as the acquisition page reads (provenance/qualitas-acquisition.2026-10-20.html):

  > The Qualitas Corpus is available by contacting Ewan Tempero . Identify the distribution required and email him.

- The download page (provenance/qualitas-download.2026-10-20.html) offers the parts openly over the web.

Check these terms before measuring, and record any reply from the corpus's maintainer here
in a commit of its own (PLAN.md, Oracles 4).

## The maintainer's reply

Recorded by hand, in a commit of its own. Ewan Tempero, the corpus's maintainer, was asked
whether the Qualitas Corpus may be used for this study; his reply, received before
22 October 2026 (PLAN.md, Amendments, 8), reads in full:

> Hello,
> Your use of the Qualitas Corpus is acceptable. Good luck with your research.
> regards,
> --ewan

It sets no condition. The corpus is used under it and is not redistributed (`.gitignore`).
