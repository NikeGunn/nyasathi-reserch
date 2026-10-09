#!/usr/bin/env python3
"""Reproduce every NEPVERSA number reported in the paper, with one command.

    python reproduce.py                  # quick check: ~1 minute, offline, no API key
    python reproduce.py --from-source    # full rebuild from nepallaws.com: ~1 hour,
                                         # needs the Firecrawl CLI (REPRODUCE.md)
    python reproduce.py --from-source --cache DIR   # full rebuild from saved pages

Works the same on Windows, macOS and Linux (use `py` or `python3` if `python`
is not on your PATH). Needs Python 3.10+; `pip install pytest` to include the
test suite. Nothing else is installed, and nothing in this folder is modified:
a full rebuild runs in a temporary directory.

Quick check
  1. runs the test suite;
  2. confirms the data files are the v2.0.0 release cited in the paper
     (SHA-256 below, independent of git and of line endings);
  3. recounts Table 3, Table 4 and Figure 2 from those files with the paper's
     own counting code (analysis/make_tables.py) and compares every value with
     paper/shared/numbers.json.

Full rebuild additionally re-harvests the five Acts, re-derives every
amendment and item, re-runs the validator and the item audit (Method 3.4),
reproduces Table 5, and checks all 455 provisions and 181 items against the
release by SHA-256.

Exit status: 0 = every number matches the paper; 1 = a mismatch (printed);
2 = the environment cannot run the check (the message says what to install).
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is required (found %d.%d)." % sys.version_info[:2])

# Never let a console encoding turn a result into a crash (Windows cp1252/cp437).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
RELEASE = "v2.0.0"

# SHA-256 of each data file at tag v2.0.0, computed with CRLF normalised to LF
# so a Windows checkout (core.autocrlf) or a ZIP download gives the same value.
V2_DATA = {
    "AUDIT/audit_log.json": "96ea28b66ef7a2b4dca8f55735fc99ac9ffa8d78488587d90e7d0dd568cdd4b2",
    "benchmark/banking-offences-en.jsonl": "f69654b8a2dc1512834cfda3fc842bbe0ac2b32267c0df4a7c14bf22c4ab433f",
    "benchmark/bonus-act-2030.jsonl": "e77251d3bf59801f11c669987da33d529b310cc4dfca164245461e4976c6916c",
    "benchmark/companies-act-2063.jsonl": "6c57f29ed78f3c8c82ea59046a0fb82bf887daa4e8de371b88ecbb965973b1d9",
    "benchmark/foreign-exchange-regulation-act-2019.jsonl": "6c5ec39ee2b243fae39f1536a56250f09cdedfc31efe09a7ad6598ff9a1c264f",
    "benchmark/income-tax-act-2058.jsonl": "b4357d2e0040bc5ec5046510814fa986fc7da700c9c362f6129e5270c4d2f5c8",
    "corpus/banking-offences-en.jsonl": "e1802ca9b073528aed7b72119fdbbf31457b24bceea6035a098d4556ef7c29f4",
    "corpus/bonus-act-2030.jsonl": "4869d6b9e4fe8dca2c384ad44da39c4b5b4143ac439f8c8834fefafa3155656b",
    "corpus/companies-act-2063.jsonl": "cad6bb6b6f40ba337ea4db526875e15ec3b3c806346c9884dee8d1fe2a8d3c43",
    "corpus/foreign-exchange-regulation-act-2019.jsonl": "f14ea044b742f756f3bbbc5bc5ea746124e0f7d4ff6c7a659d174bce052628d9",
    "corpus/income-tax-act-2058.jsonl": "39c8fa5f5f477096db97c8c5f1d7ab127639f3c42a994242798ee9fc81c7a542",
    "paper/shared/numbers.json": "62873292998bdf995270564fd63227dd8cab559a3b1b8a2288adbc08038d4339",
}

# act slug served by the site | output file name | cache directory
ACTS = [
    ("banking-offence-and-punishment-act-2064", "banking-offences-en", "banking-en"),
    ("bonus-act-2030", "bonus-act-2030", "bonus-act-2030"),
    ("foreign-exchange-regulation-act-2019", "foreign-exchange-regulation-act-2019",
     "foreign-exchange-regulation-act-2019"),
    ("income-tax-act-2058-2002", "income-tax-act-2058", "income-tax-act-2058-2002"),
    ("companies-act-2063-2006", "companies-act-2063", "companies-act-2063-2006"),
]

TITLES = {
    "banking-offence-and-punishment-act-2064": "Banking Offence 2064",
    "bonus-act-2030": "Bonus 2030",
    "companies-act-2063-2006": "Companies 2063",
    "foreign-exchange-regulation-act-2019": "Foreign Exchange 2019",
    "income-tax-act-2058-2002": "Income Tax 2058",
}


def step(n, title):
    print("\n== %s  %s ==" % (n, title), flush=True)


def child_env():
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def run(args, cwd, check=True):
    """Run a Python module/script with the same interpreter; return stdout."""
    done = subprocess.run([sys.executable, *args], cwd=str(cwd), env=child_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and done.returncode != 0:
        print(done.stdout[-2000:], done.stderr[-2000:], sep="\n")
        sys.exit("FAILED: python %s (exit %d)" % (" ".join(args), done.returncode))
    return done


def sha_normalised(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rows(directory):
    out = []
    for f in sorted(Path(directory).glob("*.jsonl")):
        out += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out


def diffs(a, b, path):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            yield from diffs(a.get(k), b.get(k), "%s.%s" % (path, k))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diffs(x, y, "%s[%d]" % (path, i))
    elif a != b:
        yield "%s: paper=%r reproduced=%r" % (path, a, b)


def table(headers, body):
    widths = [max(len(str(r[i])) for r in [headers] + body) for i in range(len(headers))]
    fmt = "  " + "  ".join("{:<%d}" % w if i == 0 else "{:>%d}" % w for i, w in enumerate(widths))
    print(fmt.format(*headers))
    for r in body:
        print(fmt.format(*[str(c) for c in r]))


def main():
    ap = argparse.ArgumentParser(description="Reproduce the NEPVERSA paper's numbers.")
    ap.add_argument("--from-source", action="store_true",
                    help="re-harvest the five Acts and rebuild everything (about an hour)")
    ap.add_argument("--cache", type=Path, help="reuse previously fetched pages from this directory")
    a = ap.parse_args()

    # The author's working copy keeps the statutory text (corpus/raw) and the
    # fetched pages (corpus/cache); the public release has neither.
    working = (HERE / "corpus" / "raw").is_dir()
    corpus_dir = HERE / ("corpus/raw" if working else "corpus")
    bench_dir = HERE / ("benchmark/candidates" if working else "benchmark")
    cache = a.cache.resolve() if a.cache else None
    if working and cache is None and (HERE / "corpus" / "cache").is_dir():
        cache = HERE / "corpus" / "cache"
    full = a.from_source or cache is not None
    if cache is not None and not cache.is_dir():
        print("--cache %s is not a directory" % cache)
        return 2
    problems, notes = [], []

    step("1/5", "Environment")
    print("  Python %s on %s" % (sys.version.split()[0], sys.platform))
    print("  folder: %s" % HERE)
    print("  mode:   %s" % ("full rebuild" + (" (saved pages)" if cache else " (live site)")
                            if full else "quick check (offline)"))
    if full and cache is None and not (shutil.which("firecrawl") or shutil.which("firecrawl.cmd")):
        print("  The live rebuild needs the Firecrawl CLI:\n"
              "    npm i -g @mendable/firecrawl-cli && firecrawl config\n"
              "  or run without --from-source for the offline check.")
        return 2

    step("2/5", "Test suite")
    try:
        import pytest  # noqa: F401
        have_pytest = True
    except ImportError:
        have_pytest = False
    if have_pytest:
        done = run(["-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], HERE, check=False)
        last = (done.stdout.strip().splitlines() or ["(no output)"])[-1]
        print("  " + last)
        if done.returncode != 0:
            print(done.stdout[-3000:])
            problems.append("test suite failed")
    else:
        print("  SKIPPED: pytest is not installed in this Python (%s).\n"
              "  To include it: %s -m pip install pytest" % (sys.executable, Path(sys.executable).name))
        notes.append("tests skipped: pytest not installed")

    step("3/5", "Data files are the %s release" % RELEASE)
    if working:
        print("  author's working copy (holds statutory text); compared with the release by\n"
              "  SHA-256 in step 5 instead")
    else:
        bad = []
        for rel, want in V2_DATA.items():
            p = HERE / rel
            if not p.is_file():
                bad.append("%s: missing" % rel)
            elif sha_normalised(p) != want:
                bad.append("%s: differs from %s" % (rel, RELEASE))
        if bad:
            for b in bad:
                print("  " + b)
            problems.append("data files are not the %s release" % RELEASE)
        else:
            print("  all %d data files match %s by SHA-256" % (len(V2_DATA), RELEASE))

    paper = json.loads((HERE / "paper/shared/numbers.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="nepversa-") as tmp:
        work = Path(tmp)
        if full:
            step("4/5", "Rebuild corpus -> benchmark -> numbers")
            if cache is None:
                print("  fetching from nepallaws.com, 7 s between pages (about an hour)", flush=True)
            for rel in ("src", "analysis", "AUDIT", "configs"):
                if (HERE / rel).exists():
                    shutil.copytree(HERE / rel, work / rel,
                                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for rel in ("corpus/raw", "benchmark/candidates", "paper/shared", "logs"):
                (work / rel).mkdir(parents=True, exist_ok=True)
            if cache is not None:
                shutil.copytree(cache, work / "corpus" / "cache")
            for slug, out, cdir in ACTS:
                done = run(["-m", "nepversa.harvest", "https://nepallaws.com/Laws/" + slug,
                            "--out", "corpus/raw/%s.jsonl" % out, "--cache", "corpus/cache/" + cdir],
                           work, check=False)
                report = (done.stdout.strip().splitlines() or [""])[0]
                verdict = report.rsplit("-> ", 1)[-1] if "-> " in report else "no report"
                print("  harvest %-40s %s" % (out, verdict), flush=True)
                if done.returncode != 0 or not report.endswith("-> VALID"):
                    print(done.stdout[-1500:], done.stderr[-1500:], sep="\n")
                    print("  A harvest that is not VALID is never counted; stopping.")
                    return 1
                run(["-m", "nepversa.build_benchmark", "corpus/raw/%s.jsonl" % out,
                     "--out", "benchmark/candidates/%s.jsonl" % out], work)
            print("  audit verdicts: " + run(["analysis/audit_sheet.py", "reapply"], work).stdout.strip().splitlines()[-1])
            print("  validator:      " + run(["-m", "nepversa.validate",
                                              *["corpus/raw/%s.jsonl" % o for _, o, _ in ACTS]],
                                             work, check=False).stdout.strip().splitlines()[-1])
            audit = run(["analysis/audit_items.py"], work, check=False)
            print("  item audit:     " + audit.stdout.strip().splitlines()[-1])
            if audit.returncode != 0:
                problems.append("item audit (Method 3.4) failed")
            run(["analysis/make_tables.py"], work)
            built = json.loads((work / "paper/shared/numbers.json").read_text(encoding="utf-8"))
            checked = sorted(paper)
        else:
            step("4/5", "Recount every number from the released files")
            sys.path.insert(0, str(HERE / "analysis"))
            import make_tables as mt
            mt.CORPUS, mt.BENCH = corpus_dir, bench_dir
            agg, per_act = mt.corpus_stats()
            built = {"corpus": agg, "per_act": per_act, "benchmark": mt.benchmark_stats()}
            checked = ["corpus", "per_act", "benchmark"]
            print("  counted with analysis/make_tables.py over %s and %s"
                  % (corpus_dir.relative_to(HERE), bench_dir.relative_to(HERE)))

        step("5/5", "Compare with the paper (paper/shared/numbers.json)")
        problems += [d for k in checked for d in diffs(paper.get(k), built.get(k), k)]
        c, b = built["corpus"], built["benchmark"]

        print("\n  Table 3. Corpus composition by Act")
        table(["Act", "Prov.", "Amended", "Density%", "Lettered", "Repealed", "INS", "SUB", "REP"],
              [[TITLES.get(r["act"], r["act"]), r["provisions"], r["amended"], r["amended_pct"],
                r["lettered"], r["repealed_in_full"], r["insert"], r["substitute"], r["repeal"]]
               for r in built["per_act"]]
              + [["Total", c["provisions"], c["amended_provisions"], c["amended_pct"],
                  c["lettered_sections"], c["repealed_in_full"], c["op_insert"],
                  c["op_substitute"], c["op_repeal"]]])

        print("\n  Table 4. Benchmark composition by question type")
        table(["Question type", "Items", "Abstention expected"],
              [["T2 point-in-time", b["t2_point_in_time"], b["t2_abstention"]],
               ["T3 supersession", b["t3_supersession"], b["t3_abstention"]],
               ["Total", b["items"], "%d (%s%%)" % (b["abstention_expected"], b["abstention_pct"])]])
        print("  nuggets: %d label, %d citation, %d exact; %d T2 items anchored to a named instrument"
              % (b["nugget_label"], b["nugget_citation"], b["nugget_exact"], b["instrument_anchored"]))

        print("\n  Figure 2. Pipeline yield")
        print("  %d Acts -> %d provisions -> %d amendment units -> %d amended -> %d items -> %d checked by author"
              % (c["acts"], c["provisions"], c["amendment_units"], c["amended_provisions"],
                 b["items"], b["status_verified"]))

        if full:
            x = built["extraction"]
            print("\n  Table 5. Amended units, HTML vs Markdown-only route")
            table(["Act", "HTML", "Markdown", "Agree", "MD only", "HTML only", "Prov. disagree"],
                  [[TITLES.get(r["act"], r["act"]), r["units_html"], r["units_markdown"], r["agree"],
                    r["md_only"], r["html_only"], r["provisions_disagreeing"]]
                   for r in built["extraction_by_act"]]
                  + [["Total", x["units_html"], x["units_markdown"], x["agree"], x["md_only"],
                      x["html_only"], x["provisions_disagreeing"]]])
            print("  markers: %d in the HTML = %d on units + %d whole-section + %d reported"
                  % (x["html_markers"], x["markers_on_units"], x["markers_whole_section"],
                     x["markers_unattached"]))

            # Every rebuilt provision and item must hash to the released record.
            def by(items, key):
                return {r[key]: r for r in items}
            rel_c, reb_c = by(rows(corpus_dir), "citation_key"), by(rows(work / "corpus/raw"), "citation_key")
            rel_i, reb_i = by(rows(bench_dir), "item_id"), by(rows(work / "benchmark/candidates"), "item_id")

            def text_hash(r):
                return r.get("text_sha256") or sha(r.get("text", ""))

            def nugget_hashes(r):
                return [(n.get("value_sha256") or sha(n["value"])) if n["kind"] == "exact" else n.get("value")
                        for n in r["gold_nuggets"]]
            c_bad = sorted(k for k in rel_c.keys() | reb_c.keys()
                           if k not in rel_c or k not in reb_c or text_hash(rel_c[k]) != text_hash(reb_c[k]))
            i_bad = sorted(k for k in rel_i.keys() | reb_i.keys()
                           if k not in rel_i or k not in reb_i
                           or rel_i[k]["gold_state"] != reb_i[k]["gold_state"]
                           or nugget_hashes(rel_i[k]) != nugget_hashes(reb_i[k]))
            print("\n  provisions matching the release: %d / %d (SHA-256 of text)"
                  % (len(rel_c) - len([k for k in c_bad if k in rel_c]), len(rel_c)))
            print("  items matching the release:      %d / %d (id, gold state, nugget hashes)"
                  % (len(rel_i) - len([k for k in i_bad if k in rel_i]), len(rel_i)))
            problems += ["provision %s differs from the release" % k for k in c_bad[:20]]
            problems += ["item %s differs from the release" % k for k in i_bad[:20]]
        else:
            print("\n  Table 5 and the item audit need the source pages; run with --from-source.")

    print()
    if problems:
        print("MISMATCH:")
        for p in problems:
            print("   " + p)
        if full:
            print("\nAfter --from-source, a mismatch can mean nepallaws.com edited a page after"
                  "\n2026-09-23 (each record carries retrieved_at). Please report it with this output.")
        return 1
    print("REPRODUCED: every number checked matches the paper%s."
          % (" (" + "; ".join(notes) + ")" if notes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
