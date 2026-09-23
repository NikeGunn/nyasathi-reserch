"""Look up arXiv records straight from the export API, for citation verification.

    python analysis/arxiv_lookup.py --q 'ti:"statutory article retrieval"' --q ...
    python analysis/arxiv_lookup.py --id 2108.11792 --id 2104.06039

Exists because the arXiv MCP server returned HTTP 406 for every query on
2026-09-23. The same URL fetched with curl returned 200 every time, while
Python's urllib got 406 with any User-Agent, any Accept header, and after four
backed-off retries: arXiv's CDN refuses the client, not the query. So this
script fetches with curl. Paced at 3.5 s per request (arXiv asks for 3 s).
Prints title, authors, first-version year, journal_ref and DOI, which is what
`logs/citations_verified.md` records.
"""

from __future__ import annotations

import argparse
import time
import shutil
import subprocess
import urllib.parse

from defusedxml import ElementTree as ET

API = "https://export.arxiv.org/api/query?"
NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
UA = "NEPVERSA-citation-check/1.0 (+https://github.com/NikeGunn/nyasathi-reserch)"


def fetch(params: dict[str, str]) -> list[dict[str, str]]:
    curl = shutil.which("curl")
    if curl is None:
        raise SystemExit("curl not on PATH (urllib is refused by arXiv's CDN; see docstring)")
    done = subprocess.run(
        [curl, "-sS", "--fail", "-A", UA, API + urllib.parse.urlencode(params)],
        capture_output=True, timeout=90,
    )
    if done.returncode != 0:
        raise SystemExit(f"arXiv fetch failed: {done.stderr.decode(errors='replace')}")
    root = ET.fromstring(done.stdout)
    out = []
    for e in root.findall("a:entry", NS):
        def text(path: str) -> str:
            node = e.find(path, NS)
            if node is None or node.text is None:
                return ""
            return " ".join(node.text.split())

        out.append({
            "id": text("a:id").rsplit("/abs/", 1)[-1],
            "title": text("a:title"),
            "authors": "; ".join(" ".join((a.text or "").split()) for a in e.findall("a:author/a:name", NS)),
            "published": text("a:published")[:10],
            "journal_ref": text("x:journal_ref"),
            "doi": text("x:doi"),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", action="append", default=[], help="arXiv search_query")
    ap.add_argument("--id", action="append", default=[], help="arXiv id")
    ap.add_argument("-n", type=int, default=5)
    args = ap.parse_args()
    jobs = [{"search_query": q, "max_results": str(args.n)} for q in args.q]
    if args.id:
        jobs.append({"id_list": ",".join(args.id), "max_results": str(len(args.id))})
    for i, params in enumerate(jobs):
        if i:
            time.sleep(3.5)
        print(f"## {params.get('search_query') or params['id_list']}")
        for r in fetch(params):
            print(f"- {r['id']} | {r['published']} | {r['title']}\n    {r['authors']}"
                  + (f"\n    ref: {r['journal_ref']}" if r["journal_ref"] else "")
                  + (f"\n    doi: {r['doi']}" if r["doi"] else ""))


if __name__ == "__main__":
    main()
