"""Build mlcq-moved-repositories.csv: the MLCQ repositories whose labelled commit is no longer at
their URL, mapped to a new GitHub location where that commit exists.

    python3 scripts/find_moved_repositories.py <mlcq-repos.csv> [-o mlcq-moved-repositories.csv]

Needs the GitHub CLI (`gh`), authenticated. Reads locations and commit SHAs only; no repository
is cloned or measured, and no result is read. The rule (PLAN.md, Moved repositories):

  1. A repository is MISSING if GitHub cannot show its labelled commit at its URL
     (GET repos/{owner}/{name}/commits/{sha} is not 200).
  2. Candidates for a missing repository, in this order, all recorded:
     - where GitHub redirects the old name (a rename or transfer);
     - a repository search for its name (`{name} in:name`, 20 results), and for an Eclipse
       name `eclipse.x` or `org.eclipse.x`, also for `x`.
  3. A candidate is VERIFIED if GitHub shows the labelled commit in it.
  4. The new location is the verified candidate of the project's own organisation (owner is
     the old owner, or `{old owner}-...`, as `eclipse-dltk` for `eclipse`), then one that is
     not a fork, then the most stars, then by name. The others verified are listed. None
     verified: the repository stays a recorded failure (new_url empty).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import re
import subprocess
import sys
import time


def gh(path: str):
    """GET a GitHub API path: (status, json or None)."""
    p = subprocess.run(["gh", "api", "-i", path], capture_output=True, text=True)
    head, body = (re.split(r"\r?\n\r?\n", p.stdout, maxsplit=1) + [""])[:2]
    try:
        status = int(head.split()[1])
    except (IndexError, ValueError):
        status = 0
    try:
        return status, json.loads(body) if body.strip() else None
    except json.JSONDecodeError:
        return status, None


def has_commit(full_name: str, sha: str) -> bool:
    return gh(f"repos/{full_name}/commits/{sha}")[0] == 200


def search(term: str) -> list[dict]:
    time.sleep(2.5)                      # the search API allows 30 requests a minute
    status, js = gh(f"search/repositories?q={term}+in:name&per_page=20")
    return (js or {}).get("items", []) if status == 200 else []


def candidates(full_name: str) -> list[tuple[str, str]]:
    """(candidate full_name, how found), in the order of the rule, without repeats."""
    out, seen = [], {full_name.lower()}
    status, js = gh(f"repos/{full_name}")
    if status == 200 and js and js["full_name"].lower() != full_name.lower():
        out.append((js["full_name"], "redirect"))
        seen.add(js["full_name"].lower())
    name = full_name.split("/", 1)[1]
    terms = [name]
    for prefix in ("org.eclipse.", "eclipse."):
        if name.startswith(prefix):
            terms.append(name[len(prefix):])
    for t in terms:
        for it in search(t):
            if it["full_name"].lower() not in seen:
                seen.add(it["full_name"].lower())
                out.append((it["full_name"], f"search '{t}'"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repos", help="mlcq-repos.csv (paper one's MLCQ conversion)")
    ap.add_argument("-o", "--out", default="mlcq-moved-repositories.csv")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    rows = [r for r in csv.DictReader(open(args.repos)) if r.get("status", "usable") == "usable"]
    out = []
    for i, r in enumerate(rows, 1):
        name, sha = r["full_name"], r["commit"]
        if has_commit(name, sha):
            continue
        print(f"[{i}/{len(rows)}] {name} @ {sha[:12]}: missing", file=sys.stderr)
        owner = name.split("/", 1)[0].lower()
        verified = []
        for cand, how in candidates(name):
            if has_commit(cand, sha):
                _, js = gh(f"repos/{cand}")
                cand_owner = cand.split("/", 1)[0].lower()
                verified.append({"full_name": cand, "how": how, "fork": bool(js and js["fork"]),
                                 "official": cand_owner == owner or cand_owner.startswith(owner + "-"),
                                 "stars": (js or {}).get("stargazers_count", 0)})
        verified.sort(key=lambda v: (not v["official"], v["fork"], -v["stars"], v["full_name"].lower()))
        best = verified[0] if verified else None
        print(f"    -> {best['full_name'] if best else 'none verified'}"
              f" ({len(verified)} verified)", file=sys.stderr)
        out.append({"old_url": r["url"], "new_url": f"https://github.com/{best['full_name']}" if best else "",
                    "commit": sha, "how_found": best["how"] if best else "",
                    "new_is_fork": best["fork"] if best else "",
                    "other_verified": " ".join(v["full_name"] for v in verified[1:]),
                    "checked": today})
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["old_url", "new_url", "commit", "how_found", "new_is_fork",
                                           "other_verified", "checked"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"wrote {args.out}: {len(out)} missing, {sum(1 for o in out if o['new_url'])} mapped",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
