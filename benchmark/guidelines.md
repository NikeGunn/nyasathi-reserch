# NEPVERSA annotation guidelines

For the human auditor (Nikhil, or a law student/advocate). PAPER_PLAN.md §7
item 1.

**Your job is to audit, not to label.** Gold answers here are *derived* from
statements the law itself publishes — an amendment footnote saying a clause was
inserted, substituted or repealed. Your task is to confirm the machine read
those statements correctly. That is why this is a sample audit and not 400 hand
labels.

---

## 1. What a NEPVERSA item is made of

| Field | Meaning |
|---|---|
| `question` | What is asked |
| `citation_key` | `act:<slug>#<section>` — the provision |
| `unit` | The clause inside it, e.g. `d1`, `ङ` |
| `as_of_amendment` | The amendment ordinal the question is anchored to |
| `gold_state` | `absent` / `present_text_known` / `present_text_unknown` |
| `gold_nuggets` | The exact strings a correct answer must contain |
| `should_abstain` | Whether the honest answer is a refusal |
| `provenance` | **The published statement the item came from** |
| `source_url` | The live page — open it and check |

**Always audit against `provenance` and `source_url`.** If the footnote on the
page does not say what `provenance` claims, the item is wrong.

---

## 2. The five question types

**T1 — Lookup.** Plain retrieval. "What does दफा 7 provide?" No time element.

**T2 — Point-in-time.** "Before the First Amendment, was clause (d1) in force?"
The core task. Gold comes from an INSERT or REPEAL footnote.

**T3 — Supersession.** "Is clause (x) still in force?" Built only where the law
says a unit was repealed. **The correct answer is often a refusal** — this is
the case TIDE found models worst at (26.7%).

**T4 — Statute→case.** From a provision to the judgments interpreting it.
Sourced from NKP linkage, not from footnotes.

**T5 — Cross-act.** Requires combining provisions from two or more Acts.

---

## 3. The three amendment operations

| Footnote (Nepali) | Footnote (English) | Operation | What we know |
|---|---|---|---|
| `संशोधनद्वारा थप।` | `Added by the … Amendment.` | **INSERT** | Did not exist before; text known after |
| `संशोधनद्वारा संशोधित।` | `Amended by the … Amendment.` | **SUBSTITUTE** | Existed before; **old wording NOT printed** |
| `संशोधनद्वारा झिकिएको।` | `Deleted by the … Amendment.` | **REPEAL** | Existed before; **old wording NOT printed**; absent now |

### The rule that protects the benchmark

**We never ask for text the source does not print.** For SUBSTITUTE and REPEAL,
the superseded wording is not in the consolidated edition — the page shows a row
of dots. So those periods are marked `present_text_unknown` and **no
quote-the-text item is generated over them**.

If you see an item asking a model to state what a clause *used to say*, it is a
bug. Flag it.

---

## 4. How to audit one item

1. Open `source_url`.
2. Find the clause named in `unit`.
3. Check the inline footnote marker matches `provenance` (e.g. clause `(d1)`
   preceded by `1`, and footnote `1` reading "Added by the First Amendment").
4. Check the operation is read correctly per the table above.
5. Check `should_abstain`:
   - INSERT, period *before* → clause did not exist → **abstain = true**
   - REPEAL, period *after* → clause no longer exists → **abstain = true**
   - Otherwise → false
6. For `exact` nuggets, confirm the string appears **verbatim** on the page.

Record: `correct` / `incorrect` / `unsure`, plus a note. **Never edit the item
file.** Your labels go in `benchmark/annotated/` untouched by any script.

---

## 5. Sampling

Audit **≥50 items** drawn at random, stratified by question type and operation.
The measured error rate goes into the paper's Limitations section as-is,
whatever it is. A double-annotated subset of ≥20 items gives Cohen's κ.

Per the rule that only humans confirm gold, **only humans confirm gold.** No agreement score
is ever computed from machine labels.

---

## 6. Things that are known to go wrong

- **The visarga.** `दफा २०ः` uses `ः` (U+0903), not a colon. It silently
  dropped 8% of provisions in an earlier harvest and halved one act.
- **Lettered sections.** `12A` / `१२क` exist only because an amendment
  inserted them. If one is *not* marked as amendment-inserted, flag it.
- **Amendment ordinal without a date.** Expected. Footnotes name "First
  Amendment", not a date. `from_date_bs: null` is correct, not missing data.
- **Nepali endings.** `थप` and `थप गरिएको` are the same operation. If one form
  parses and the other does not, that is the morphology bug this project has
  hit five times — flag it loudly.

---

## 7. What to do when unsure

Mark `unsure` and write why. An item you cannot verify against the published
page **does not go into the frozen benchmark**. Under-including is safe;
including an item whose gold nobody could confirm is not.
