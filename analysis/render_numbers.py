"""Substitute `{{key}}` tokens in manuscript Markdown from `numbers.json`.

    python analysis/render_numbers.py <in_dir> <out_dir>

Both manuscript versions (APA 7 and ACM) are built from the same sections, and
the paper plan requires the same numbers in both. Until corpus v2.0.0 the
section prose carried hand-copied counts ("109 provisions", "46 items"), so a
re-harvest changed `numbers.json` and silently left the prose stale. A token
names the number instead of restating it:

    {{corpus.provisions}}            -> 436
    {{benchmark.abstention_pct}}     -> 47.8
    {{per_act.bonus-act-2030.lettered}} -> 1

An unknown key is an error, never an empty string: a sentence that reads
"covers  Acts" is the silent failure this file exists to prevent.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUMBERS = ROOT / "paper" / "shared" / "numbers.json"
TOKEN = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")


class UnknownNumberError(KeyError):
    pass


def _flatten(numbers: dict) -> dict[str, str]:
    flat: dict[str, str] = {}

    def walk(prefix: str, node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(node, list):
            for entry in node:
                if isinstance(entry, dict) and "act" in entry:
                    walk(f"{prefix}.{entry['act']}", {k: v for k, v in entry.items() if k != "act"})
        else:
            flat[prefix] = f"{node:,}" if isinstance(node, int) and abs(node) >= 10000 else str(node)

    walk("", numbers)
    return flat


TABLE = re.compile(r"\{\{\s*table:([\w\-]+)\s*\}\}")
TABLES = ROOT / "paper" / "shared" / "tables"


def render(text: str, flat: dict[str, str]) -> str:
    # `{{table:table1_corpus}}` inlines the generated table, so a section never
    # carries a hand-copied one (v1's Table 1 was a copy of the generated file).
    def table(m: re.Match[str]) -> str:
        path = TABLES / f"{m.group(1)}.md"
        if not path.exists():
            raise UnknownNumberError(f"table {m.group(1)} was not generated")
        return path.read_text(encoding="utf-8").rstrip("\n")

    text = TABLE.sub(table, text)

    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in flat:
            raise UnknownNumberError(f"{{{{{key}}}}} is not in numbers.json")
        return flat[key]

    return TOKEN.sub(sub, text)


def render_dir(src: Path, dst: Path) -> list[Path]:
    flat = _flatten(json.loads(NUMBERS.read_text(encoding="utf-8")))
    dst.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(src.glob("*.md")):
        target = dst / f.name
        target.write_text(render(f.read_text(encoding="utf-8"), flat), encoding="utf-8")
        out.append(target)
    return out


if __name__ == "__main__":
    for p in render_dir(Path(sys.argv[1]), Path(sys.argv[2])):
        print(p)
