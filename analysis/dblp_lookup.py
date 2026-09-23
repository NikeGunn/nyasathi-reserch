"""Find the published (peer-reviewed) version of a paper, for citation verification.

    python analysis/dblp_lookup.py "SituatedQA Incorporating Extra-Linguistic" ...

Queries **Crossref**, the DOI registry, and prints container (venue), year, DOI
and type for the top hits. arXiv tells us a paper exists; Crossref tells us
where it was published, which is what a reference list must cite when a
published version exists.

Named for DBLP, which was tried first: on 2026-09-23 its API answered every
request with an HTML "Making sure you're not a bot!" page and HTTP 200, which a
JSON parser reports as a decode error rather than as a refusal. The check below
names that layer instead. Fetched with curl, as in `arxiv_lookup.py`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.parse

MAILTO = "knewboy.nykhil@gmail.com"  # Crossref "polite pool" contact


def main() -> None:
    curl = shutil.which("curl")
    if curl is None:
        raise SystemExit("curl not on PATH")
    for i, q in enumerate(sys.argv[1:]):
        if i:
            time.sleep(1.5)
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
            {"query.bibliographic": q, "rows": "4", "mailto": MAILTO,
             "select": "DOI,title,container-title,issued,type,author"}
        )
        done = subprocess.run([curl, "-sS", "--fail", url], capture_output=True, timeout=60)
        print(f"## {q}")
        if done.returncode != 0:
            print(f"  FETCH FAILED: {done.stderr.decode(errors='replace')}")
            continue
        try:
            items = json.loads(done.stdout)["message"]["items"]
        except (json.JSONDecodeError, KeyError):
            print(f"  NOT JSON (bot wall or error page?): {done.stdout[:120]!r}")
            continue
        for it in items:
            year = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
            first = (it.get("author") or [{}])[0].get("family", "?")
            print(f"  - {(it.get('container-title') or ['-'])[0]} {year} | "
                  f"{(it.get('title') or ['-'])[0]} | {first} | doi:{it['DOI']} | {it.get('type')}")


if __name__ == "__main__":
    main()
