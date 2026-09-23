"""Print authoritative metadata for DOIs from Crossref (authors, venue, pages).

    python analysis/crossref_doi.py 10.18653/v1/2022.acl-long.468 ...

Author lists in `references.bib` are copied from this output, never typed from
memory (PAPER_PLAN §1 rule 3). curl, for the reason in `arxiv_lookup.py`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time

MAILTO = "knewboy.nykhil@gmail.com"


def main() -> None:
    curl = shutil.which("curl")
    if curl is None:
        raise SystemExit("curl not on PATH")
    for i, doi in enumerate(sys.argv[1:]):
        if i:
            time.sleep(1.2)
        done = subprocess.run(
            [curl, "-sS", "--fail", f"https://api.crossref.org/works/{doi}?mailto={MAILTO}"],
            capture_output=True, timeout=60,
        )
        if done.returncode != 0:
            print(f"## {doi}\n  FETCH FAILED: {done.stderr.decode(errors='replace')}")
            continue
        m = json.loads(done.stdout)["message"]
        authors = " and ".join(
            f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in m.get("author", [])
        )
        year = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
        print(f"## {doi}\n  title: {(m.get('title') or [''])[0]}\n  authors: {authors}\n"
              f"  venue: {(m.get('container-title') or [''])[0]}\n  year: {year}  pages: {m.get('page', '-')}"
              f"  volume: {m.get('volume', '-')}  publisher: {m.get('publisher', '-')}")


if __name__ == "__main__":
    main()
