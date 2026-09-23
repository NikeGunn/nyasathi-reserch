"""Generate every figure the manuscript shows.

    python analysis/make_figures.py

Writes 300-dpi PNG (for Word) and vector PDF (for the ACM/LaTeX version) of the
same figure source into `paper/shared/figures/`, per PAPER_PLAN.md §15.3.

**Every value is read from `paper/shared/numbers.json`**, which
`analysis/make_tables.py` counts from the artefacts. Nothing here is typed by
hand, and a figure cannot show a number the corpus does not contain: §1 rule 1
and §14 rule 1. The one exception is F2 and F3's *structure* (a pipeline's
stages, a timeline's shape), which is design, not data - and F3's text is quoted
from the harvested provision, not composed here.

Figures produced (PAPER_PLAN.md §15.1):

* **F2**  Benchmark construction pipeline - sources to human verification.
* **F3**  Worked example - one real provision, two versions, one question.
* **F9**  Benchmark statistics - composition by act, operation, and type.
* **F10** Amendment density by act - the act-selection evidence.

F1 and F4-F8 describe the compute-matched experiments, which are future work
(STATUS.md): the numbers behind them do not exist, so the figures are not drawn.
Drawing an empty axis would imply a measurement was attempted.

APA 7 rules applied here (the caption itself lives in the manuscript, because
APA puts **Figure N** and the italic title *above* the image as document text):

* No title inside the image - the caption is the title (§15.3).
* Okabe-Ito colour-blind-safe palette, and every series also differs by
  hatch or marker so the figure survives greyscale printing.
* Axis labels carry units; no chartjunk, no 3-D, no gradients.
* Devanagari renders through Nirmala UI and always carries an English gloss.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "paper" / "shared"
FIGDIR = SHARED / "figures"

# Okabe-Ito: the standard colour-blind-safe qualitative palette.
OKABE_ITO = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "vermillion": "#D55E00",
    "sky": "#56B4E9",
    "yellow": "#F0E442",
    "purple": "#CC79A7",
    "black": "#000000",
    "grey": "#8C8C8C",
}

INK = "#1A1A1A"
RULE = "#4D4D4D"
FAINT = "#D9D9D9"


def _serif() -> str:
    """The APA body font, if the system has it.

    APA 7 permits several fonts but requires one used consistently; the
    manuscript is built in Times New Roman, so a figure in a different face
    reads as a pasted-in foreign object.
    """
    from matplotlib.font_manager import fontManager

    names = {f.name for f in fontManager.ttflist}
    for want in ("Times New Roman", "Nimbus Roman", "Liberation Serif", "DejaVu Serif"):
        if want in names:
            return want
    return "serif"


def _devanagari() -> FontProperties | None:
    """A font that can actually draw Devanagari, or None.

    PAPER_PLAN.md §15.3 requires Devanagari in figures to render correctly.
    Without this check the glyphs silently become tofu boxes, which is the
    figure equivalent of the shell that turned Nepali into `????`.
    """
    from matplotlib.font_manager import fontManager

    names = {f.name for f in fontManager.ttflist}
    for want in ("Noto Sans Devanagari", "Nirmala UI", "Mangal", "Kokila"):
        if want in names:
            return FontProperties(family=want)
    return None


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": _serif(),
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.edgecolor": RULE,
            "axes.linewidth": 0.8,
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,  # embed real glyphs, not curves
            "ps.fonttype": 42,
        }
    )


def _numbers() -> dict:
    path = SHARED / "numbers.json"
    if not path.exists():
        raise SystemExit(
            "paper/shared/numbers.json is missing - run analysis/make_tables.py "
            "first. A figure must not invent the values it plots."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _act_label(slug: str) -> str:
    """Short, readable act name for an axis tick."""
    words = slug.replace("-", " ").split()
    # The site appends the Gregorian year to some slugs
    # (`income-tax-act-2058-2002`); the Act's own year is the Bikram Sambat one
    # before it, and that is the year the paper uses everywhere else.
    years = [w for w in words if w.isdigit()]
    year = years[0] if years else ""
    head = " ".join(w.title() for w in words if not w.isdigit())
    short = {
        "Banking Offence And Punishment Act": "Banking Offence",
        "Foreign Exchange Regulation Act": "Foreign Exchange",
        "Bonus Act": "Bonus",
        "Companies Act": "Companies",
        "Income Tax Act": "Income Tax",
    }.get(head, head)
    return f"{short}\n{year}" if year else short


_ORDINALS = {
    1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
    6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth",
}


def _ordinal_word(value: object) -> str:
    """"First", not "1".

    Nepali consolidated Acts name an amendment by its ordinal ("the First
    Amendment"), which is how the footnote reads and how a lawyer cites it.
    The corpus stores the integer, so the figure must spell it back out.
    """
    if isinstance(value, int) and value in _ORDINALS:
        return _ORDINALS[value]
    if isinstance(value, int):
        return f"{value}th"
    return "an"


def _save(fig, name: str) -> None:
    """Write the 300-dpi PNG for Word and the vector PDF for LaTeX.

    The PNG is flattened to **opaque RGB**. matplotlib writes RGBA by default,
    and a transparent-capable PNG round-tripped through this pipeline reaches
    Word as a correctly sized, correctly related, completely invisible picture:
    four inline shapes at the right dimensions rendering as blank space, with
    valid XML, valid relationships and byte-identical image parts. Nothing in
    the package disagrees with itself, which is why it survived a structural
    check, an OOXML check and Word's own open. Only looking at the page showed
    it.
    """
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGDIR / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)

    png = FIGDIR / f"{name}.png"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.02,
                transparent=False, facecolor="white")
    plt.close(fig)

    try:
        from PIL import Image
    except ImportError:
        print(f"  wrote figures/{name}.png and .pdf  (WARNING: Pillow missing, "
              "alpha channel not flattened; Word may render it blank)")
        return
    with Image.open(png) as im:
        if im.mode in ("RGBA", "LA", "P"):
            flat = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            flat.paste(rgba, mask=rgba.split()[-1])
            flat.save(png, "PNG", optimize=True)
    print(f"  wrote figures/{name}.png and .pdf")


# --------------------------------------------------------------------------
# F2 - benchmark construction pipeline
# --------------------------------------------------------------------------
def figure_pipeline(n: dict) -> None:
    """Sources to human verification, with the counted yield at each stage.

    The stage labels are design; the counts under them come from numbers.json,
    so the figure cannot drift from the corpus it describes.
    """
    c, b = n["corpus"], n["benchmark"]
    stages = [
        ("Consolidated\nActs", f'{c["acts"]} acts', OKABE_ITO["blue"]),
        ("Provision\nsegmentation", f'{c["provisions"]} provisions', OKABE_ITO["sky"]),
        ("Footnote\nprovenance", f'{c["amendment_units"]} units', OKABE_ITO["green"]),
        ("Validity\nwindows", f'{c["amended_provisions"]} amended', OKABE_ITO["orange"]),
        ("Candidate\nitems", f'{b["items"]} items', OKABE_ITO["vermillion"]),
        ("Author\naudit", f'{b["status_verified"]} checked', OKABE_ITO["grey"]),
    ]

    fig, ax = plt.subplots(figsize=(6.5, 1.55))
    ax.set_xlim(0, len(stages) * 10)
    ax.set_ylim(1.5, 10)
    ax.axis("off")

    w, h, y = 8.0, 3.6, 4.0
    for i, (label, count, colour) in enumerate(stages):
        x = i * 10 + 0.6
        pending = i == len(stages) - 1
        box = mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.18,rounding_size=0.45",
            linewidth=1.1, edgecolor=colour,
            facecolor="white" if pending else colour,
            linestyle=(0, (3, 2)) if pending else "solid",
            alpha=1.0 if not pending else 0.95,
        )
        ax.add_patch(box)
        ax.text(x + w / 2, y + h * 0.62, label, ha="center", va="center",
                fontsize=8, color=INK if pending else "white",
                weight="bold", linespacing=1.25)
        ax.text(x + w / 2, y + h * 0.20, count, ha="center", va="center",
                fontsize=7.5, color=INK if pending else "white", style="italic")
        if i < len(stages) - 1:
            ax.annotate(
                "", xy=(x + w + 1.35, y + h / 2), xytext=(x + w + 0.15, y + h / 2),
                arrowprops=dict(arrowstyle="-|>", color=RULE, linewidth=1.0,
                                shrinkA=0, shrinkB=0),
            )

    # The gate is the point of the figure: nothing crosses it automatically.
    gx = (len(stages) - 1) * 10 + 0.6
    ax.plot([gx - 1.5, gx - 1.5], [y - 1.0, y + h + 1.0],
            color=OKABE_ITO["vermillion"], linewidth=1.2, linestyle=(0, (4, 2)))
    ax.text(gx - 1.9, y + h + 1.15, "HUMAN GATE", fontsize=7,
            color=OKABE_ITO["vermillion"], weight="bold", ha="right")
    ax.text(len(stages) * 5, 2.15,
            "Dashed stage and rule: no item is gold until a human confirms it.",
            ha="center", fontsize=7, color=RULE, style="italic")
    _save(fig, "F2_pipeline")


# --------------------------------------------------------------------------
# F3 - worked example
# --------------------------------------------------------------------------
def figure_worked_example() -> None:
    """One real provision on a timeline, with the question it licenses.

    The provision, its operation and its ordinal are read from the harvested
    corpus; only the layout is designed here. If the corpus does not contain a
    substituted unit, the figure is skipped rather than illustrated with an
    invented one.
    """
    raw = ROOT / "corpus" / "raw"
    chosen = None
    for path in sorted(raw.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            for unit in row.get("amended_units", []):
                if unit["operation"] == "substitute" and row.get("heading"):
                    chosen = (row, unit)
                    break
            if chosen:
                break
        if chosen:
            break

    if not chosen:
        print("  F3 skipped: no substituted unit in the corpus to illustrate")
        return

    row, unit = chosen
    deva = _devanagari()
    ordinal = _ordinal_word(unit.get("amendment_ordinal"))
    # `unit` is a clause letter ("f") or a sub-section number ("1"). Printed
    # bare it reads as noise; the statutory shape is what a lawyer recognises.
    raw_unit = str(unit["unit"])
    unit_label = f"({raw_unit})" if raw_unit.isalpha() else f"sub-section ({raw_unit})"
    section = row["number"]
    heading = (row["heading"] or "").strip()
    if len(heading) > 46:
        heading = heading[:43].rstrip() + "..."

    fig, ax = plt.subplots(figsize=(6.5, 2.35))
    ax.set_xlim(0, 100)
    ax.set_ylim(17, 97)
    ax.axis("off")

    ax.plot([8, 92], [62, 62], color=RULE, linewidth=1.0, zorder=1)
    for x in (18, 62):
        ax.plot([x], [62], marker="|", markersize=9, color=RULE, zorder=2)

    ax.add_patch(mpatches.Rectangle((8, 66), 44, 12, facecolor=OKABE_ITO["sky"],
                                    alpha=0.20, edgecolor=OKABE_ITO["blue"],
                                    linewidth=0.9))
    ax.text(30, 72, "Version 1  (as enacted)", ha="center", fontsize=8,
            weight="bold", color=OKABE_ITO["blue"])

    ax.add_patch(mpatches.Rectangle((52, 66), 40, 12, facecolor=OKABE_ITO["orange"],
                                    alpha=0.22, edgecolor=OKABE_ITO["vermillion"],
                                    linewidth=0.9, hatch="//"))
    ax.text(72, 72, f"Version 2  (after the {ordinal} Amendment)", ha="center",
            fontsize=8, weight="bold", color=OKABE_ITO["vermillion"])

    ax.annotate("", xy=(52, 62), xytext=(52, 52),
                arrowprops=dict(arrowstyle="-|>", color=OKABE_ITO["vermillion"],
                                linewidth=1.1))
    ax.text(53.5, 54.5, f"SUBSTITUTE  {unit_label}", fontsize=7.5,
            color=OKABE_ITO["vermillion"], weight="bold")

    ax.text(8, 91, f"Section {section}  {heading}", fontsize=9, weight="bold",
            color=INK)
    if deva is not None:
        # The gloss is placed after the Devanagari is measured, because a
        # Devanagari string's width is not its character count and a guessed
        # offset put the English translation on top of the Nepali.
        nep = ax.text(8, 82.5, "बैङ्किङ्ग कसूर तथा सजाय ऐन", fontsize=8.5,
                      color=RULE, fontproperties=deva)
        fig.canvas.draw()
        end_x = nep.get_window_extent().transformed(ax.transData.inverted()).x1
        ax.text(end_x + 2.0, 82.5, "(Banking Offence and Punishment Act)",
                fontsize=7.5, color=RULE, style="italic", va="baseline")

    ax.add_patch(mpatches.FancyBboxPatch(
        (8, 20), 84, 24, boxstyle="round,pad=0.5,rounding_size=1.2",
        facecolor="#F7F7F7", edgecolor=FAINT, linewidth=0.9))
    ax.text(10.5, 37.5, "Point-in-time question (T2)", fontsize=8,
            weight="bold", color=INK)
    ax.text(10.5, 31,
            f'"What did section {section}{unit_label if raw_unit.isalpha() else ""} '
            f"require as of a date before the {ordinal} Amendment?\"",
            fontsize=8, color=INK, style="italic")
    ax.text(10.5, 24.5,
            "Correct: Version 1.   Wrong-version answer: Version 2, quoted "
            "accurately and dated wrongly.",
            fontsize=7.5, color=RULE)
    _save(fig, "F3_worked_example")


# --------------------------------------------------------------------------
# F9 - benchmark statistics
# --------------------------------------------------------------------------
def figure_benchmark_stats(n: dict) -> None:
    """Three panels: provisions per act, operations, and item types."""
    per_act, c, b = n["per_act"], n["corpus"], n["benchmark"]

    fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.5))

    # (a) provisions vs amended, per act
    ax = axes[0]
    labels = [_act_label(a["act"]) for a in per_act]
    ypos = range(len(per_act))
    ax.barh(list(ypos), [a["provisions"] for a in per_act], height=0.62,
            color=FAINT, edgecolor=RULE, linewidth=0.6, label="Provisions")
    ax.barh(list(ypos), [a["amended"] for a in per_act], height=0.62,
            color=OKABE_ITO["blue"], edgecolor=RULE, linewidth=0.6,
            hatch="//", label="Carrying an amendment footnote")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Provisions (count)")
    # Below the axes, not inside it: in the panel the legend overlapped the
    # last act's tick label and its own bars.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), frameon=False,
              fontsize=6.5, ncol=1, handlelength=1.4, borderaxespad=0.0)
    ax.set_title("(a) Corpus by act", fontsize=8, loc="left", weight="bold")

    # (b) amendment operations
    ax = axes[1]
    ops = [("Substitute", c["op_substitute"], OKABE_ITO["blue"], "//"),
           ("Insert", c["op_insert"], OKABE_ITO["green"], ".."),
           ("Repeal", c["op_repeal"], OKABE_ITO["vermillion"], "xx")]
    ax.bar([o[0] for o in ops], [o[1] for o in ops],
           color=[o[2] for o in ops], edgecolor=RULE, linewidth=0.6,
           hatch=[o[3] for o in ops], width=0.6)
    for i, o in enumerate(ops):
        ax.text(i, o[1] + max(c["amendment_units"] * 0.02, 0.3), str(o[1]),
                ha="center", fontsize=8, weight="bold", color=INK)
    ax.set_ylabel("Amendment units (count)")
    ax.set_ylim(0, max(o[1] for o in ops) * 1.22)
    ax.set_title("(b) Operations", fontsize=8, loc="left", weight="bold")
    ax.tick_params(axis="x", labelsize=7.5)

    # (c) item types and abstention
    ax = axes[2]
    types = [("T2\npoint-in-time", b["t2_point_in_time"], OKABE_ITO["sky"], ""),
             ("T3\nsupersession", b["t3_supersession"], OKABE_ITO["purple"], "\\\\")]
    ax.bar([t[0] for t in types], [t[1] for t in types],
           color=[t[2] for t in types], edgecolor=RULE, linewidth=0.6,
           hatch=[t[3] for t in types], width=0.6)
    for i, t in enumerate(types):
        ax.text(i, t[1] + b["items"] * 0.02, str(t[1]), ha="center",
                fontsize=8, weight="bold", color=INK)
    ax.axhline(b["abstention_expected"], color=OKABE_ITO["vermillion"],
               linewidth=1.1, linestyle=(0, (4, 2)))
    ax.text(1.42, b["abstention_expected"],
            f'abstention\nexpected: {b["abstention_expected"]}',
            fontsize=6.5, color=OKABE_ITO["vermillion"], va="center", ha="right")
    ax.set_ylabel("Benchmark items (count)")
    ax.set_ylim(0, max(t[1] for t in types) * 1.25)
    ax.set_title("(c) Item types", fontsize=8, loc="left", weight="bold")
    ax.tick_params(axis="x", labelsize=7.5)

    fig.tight_layout(w_pad=1.6)
    _save(fig, "F9_benchmark_stats")


# --------------------------------------------------------------------------
# F10 - amendment density by act
# --------------------------------------------------------------------------
def figure_density(n: dict) -> None:
    """Why act selection is a measurement, not an assumption.

    Amendment density is what decides whether a version-aware corpus is
    buildable from a source at all, and it varies several-fold between Acts on
    the same site. Every probed Act appears, including the low ones.
    """
    per_act = sorted(n["per_act"], key=lambda a: a["amended_pct"], reverse=True)

    fig, ax = plt.subplots(figsize=(4.4, 2.45))
    labels = [_act_label(a["act"]).replace("\n", " ") for a in per_act]
    vals = [a["amended_pct"] for a in per_act]
    bars = ax.barh(range(len(per_act)), vals, height=0.58,
                   color=OKABE_ITO["blue"], edgecolor=RULE, linewidth=0.6)
    # Distinguish by hatch as well as position, for greyscale.
    for bar, hatch in zip(bars, ("//", "..", "xx", "\\\\", "++")):
        bar.set_hatch(hatch)

    for i, a in enumerate(per_act):
        ax.text(a["amended_pct"] + max(vals) * 0.03, i,
                f'{a["amended_pct"]}%  ({a["amended"]}/{a["provisions"]})',
                va="center", fontsize=7, color=INK)

    ax.set_yticks(range(len(per_act)))
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlabel("Provisions carrying an amendment footnote (%)")
    ax.set_xlim(0, max(vals) * 1.45)
    _save(fig, "F10_density")


def main() -> int:
    _apply_style()
    n = _numbers()
    if _devanagari() is None:
        print("  WARNING: no Devanagari font found; F3 will omit the Nepali line "
              "rather than draw tofu boxes")
    print("figures ->", FIGDIR)
    figure_pipeline(n)
    figure_worked_example()
    figure_benchmark_stats(n)
    figure_density(n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
