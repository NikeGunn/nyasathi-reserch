# lit_notes.md — literature scan and the novelty verdict

Searched 2026-09-19 via Consensus MCP. **This scan changed the paper's framing.**
Full verification of each entry (arXiv/DOI) happens in Phase 1; these notes are
the novelty check PAPER_PLAN.md §5 item 2 requires.

---

## VERDICT: the original topic is no longer novel. A near-identical study exists.

PAPER_PLAN.md §5 rule 2: *"If a paper already does our exact study, stop and tell
Nikhil immediately."* **Triggered.** Details below.

### The blocking papers

**1. TIDE — Sobhani et al. (2026), "Time Present and Time Past."**
This is, essentially, our proposed paper, in Bangladesh.
- 3,050 expert-verified QA pairs over 644 official customs instruments (1969–2025)
- **Version resolution** named as the central challenge — our exact framing
- **Deeply code-mixed documents** — our RQ4
- **Dated in two calendars** — our BS↔AD contribution
- Eight task types; a **hard date gate**; nine LLMs
- Results: best macro accuracy 68.5%; version-from-implicit-date 59.7%;
  **detecting that the supplied version does not govern: 26.7%**
- Data + code public (github.com/icsetepa44/TIDE)

Our draft already cites Sobhani et al. 2026 in the Introduction. **The draft was
written before the overlap was this complete.** "Two calendars + code-mixed +
version resolution + South Asian jurisdiction" is now taken.

**2. FiscalQA Pro — Guez et al. (2026), French tax law.**
Also in our draft as `[FiscalQA Pro authors]`.
- Versioned corpus: **32,436 article-versions, 93 years (1938–2031)**
- 209 expert-reviewed temporal questions
- **Static RAG retrieves the date-applicable version 0% of the time**
- Their multi-version retriever: **98.3% strict accuracy**
- Deliberately avoids LLM-as-judge ("would inherit the temporal bias it is meant
  to score") — a methodological point we should adopt

**3. Prior et al. (2026), German statutory QA.** 312 expert-validated
time-sensitive pairs; post-cutoff staleness and **recency bias**; RAG with date
extraction + version filtering. Concludes temporal validity must be a **hard
constraint**.

**4. LegalSearch-R1 — Fan et al. (2026).** In our draft already. RL framework
trained on **temporally-indexed data spanning multiple amendment periods**;
+57.7–80.3% on temporal consistency. This is our "System 2 for versioned law"
idea, already executed and trained.

**5. Apofasi — Manoharan et al. (2026), Sri Lanka.** Neuro-symbolic temporal RAG,
agentic planner + temporal knowledge graph, **0.97 temporal precision** on 320
temporally scoped queries. A South Asian mixed jurisdiction — geographically
adjacent to our claim.

**6. de Martim (2025), four papers** — SAT-Graph RAG, LRMoo-based diachronic
modelling, deterministic legal agents. A formal ontology for component-level
provision versioning, demonstrated on the Brazilian Constitution. **Our
"materialize every version of every provision" design is a known, named,
published pattern.** We should *use* and cite it, not reinvent it.

### What this means

The 2026 literature has converged on temporal/version-aware legal RAG. Our
original four contributions:

| Original contribution | Status after scan |
|---|---|
| First version-aware legal benchmark w/ dual calendars + code-mixed | **Taken** — TIDE |
| Compute-matched System 1 vs System 2 protocol | **Partly novel** — still rare, but not enough alone |
| Empirical study across retrievers | **Standard** |
| Error analysis incl. wrong-version retrieval | **Taken** — FiscalQA Pro, TIDE |

**Proceeding unchanged would produce a paper reviewers reject as derivative —
and would be much harder to defend in a PhD application than a smaller, honest,
genuinely-first result.**

---

## The Nepali literature: this is where the gap is real

**7. Wagle et al. (2026), "RAG Framework for the Nepali Legal Domain."**
(ICNLP 2026; our draft's key prior work.)
- **First** RAG for Nepali legal QA; NKP case law
- BM25 **P@1 0.91**; multilingual-E5-large **0.75**
- 74% groundedness, 85% judge truthfulness, 84% human truthfulness
- **Case law only. No statutes. No amendments. No versioning. No dates.**

**8. Acharya et al. (2026), "Towards a Standard Benchmark for Low-Resource
Nepali IR"** (SIGIR 2026).
- Explicitly states Nepali has **no** standardized IR benchmark
- Proposes monolingual + cross-lingual + **code-mixed** Nepali retrieval
- Argues Nepali is a compelling testbed for **morphology-aware retrieval**
- **A position/proposal paper at SIGIR — the benchmark does not exist yet.**
  This is an invitation, and it validates the gap rather than closing it.

**9. Dhakal et al. (2025), "Feasibility of AI-Driven Analysis in the Nepalese
Legal System"** (ICAIL 2025). GPT-4o + ada-002 RAG; F1 0.797/0.857/0.875 by query
type. Feasibility study; **no temporal dimension**.

**10. Poudel et al. (2024)** — English↔Nepali legal MT, 125k parallel sentences,
BLEU 7.98/6.63. Shows how hard Nepali legal text is.

**11. Begha et al. (2026)** — Nepali passport FAQ QA; fine-tuned SBERT > BM25;
multilingual-E5 best. Non-legal, but a Nepali IR datapoint.

**Comparators in other low-resource languages:** LEGAL-UQA (Urdu, 619 pairs,
Pakistan constitution); Rakhimova et al. 2025 (Kazakh legal QA).

### The uncontested facts

1. **No Nepali statutory corpus with amendment versioning exists.** Every Nepali
   legal NLP paper found uses case law or flat current-text statutes.
2. **No Nepali IR benchmark exists at all** — stated by a SIGIR 2026 paper.
3. **Nepali morphology + Devanagari + romanization** is named as an open
   research testbed by that same paper.
4. Wagle et al.'s **BM25 0.91 > E5 0.75** independently replicates the author's separate legal tool's
   internal finding that dense retrieval underperforms in Nepali. **Two
   independent confirmations of our weak-retriever premise.**

---

## RECOMMENDED TOPIC CHANGE

**Old:** *When Should a Legal Retrieval Agent Think Slowly? A version-aware,
multi-hop benchmark and compute-matched study of System 1 vs System 2 for
Nepali law.*
→ Competes head-on with TIDE, FiscalQA Pro, LegalSearch-R1, Apofasi.

**New (recommended):**

> **NEPVERSA: A Version-Aware Nepali Statutory Retrieval Benchmark — Amendment
> Provenance, Bikram Sambat Validity Windows, and Script Robustness in a
> Weak-Retriever Regime**

**Why this survives the scan:**

1. **Jurisdiction + language is genuinely first.** TIDE is Bangla customs;
   FiscalQA Pro is French tax; Prior et al. is German; Apofasi is Sri Lankan.
   **Nepali statutory law with amendment versioning: nobody.**
2. **Bikram Sambat is a real technical contribution, not a footnote.** BS is a
   lunisolar calendar with **variable month lengths that are tabulated, not
   computed**. TIDE's "two calendars" is Gregorian + Bengali/Hijri. A BS validity
   window is a genuinely different engineering object, and the author's separate legal tool's tested
   `BsDate`/`BsInterval` (BS 1975–2100) is an asset nobody else has.
3. **Script robustness is stated as an open problem by SIGIR 2026** (Acharya et
   al.) and we already own a tested instrument for it (`romanize.expand_query`).
4. **The weak-retriever regime is now externally corroborated** (Wagle: BM25 0.91
   vs E5 0.75). Every prior temporal-legal paper operates with strong retrievers
   in high-resource languages. **"What happens to version-aware retrieval when
   the retriever itself is weak?" is unasked** — and it is the one question our
   situation is uniquely suited to answer.
5. **The System 1 / System 2 compute-matched comparison survives as RQ, not as
   headline.** It becomes an analysis axis inside a benchmark paper.

### Revised contributions

1. **NEPVERSA** — first version-aware Nepali statutory benchmark; provision
   versions with **BS+AD validity windows** derived from amendment footnotes;
   Devanagari / romanized / code-mixed variants.
2. **A reproducible amendment-provenance extraction method** for Nepali
   consolidated Acts (footnote markers → insert/substitute/repeal operations at
   clause level) — transferable to other jurisdictions publishing consolidated
   text with footnotes.
3. **An empirical study in the weak-retriever regime**, testing whether the
   version-aware findings of TIDE / FiscalQA Pro / Prior et al. hold when
   retrieval is weak — including the compute-matched System 1 vs System 2
   comparison.
4. **Error analysis** distinguishing missed provision, wrong version, and
   hallucinated supersession, with **abstention measured as a first-class
   outcome**.

### Positioning sentence for the paper

> Prior work establishes that legal RAG must treat temporal validity as a hard
> constraint [Prior et al. 2026] and that static RAG retrieves the
> date-applicable version 0% of the time [Guez et al. 2026]. These results come
> from high-resource languages with strong retrievers. We ask whether they hold
> in a low-resource, morphologically rich language where dense retrieval
> underperforms lexical baselines [Wagle et al. 2026; and our own measurements],
> and we release the first version-aware Nepali statutory benchmark.

---

## Methods to adopt from the scan

- **Avoid LLM-as-judge for temporal correctness** (Guez et al.): a judge inherits
  the temporal bias it is meant to measure. Use deterministic nugget scoring —
  regex / exact-value matching. **This also removes our largest annotation
  dependency.**
- **Separate "meaning correct" from "time correct"** with a hard date gate
  (TIDE). Two metrics, never averaged.
- **Test rejection, not only selection.** TIDE's sharpest result is that models
  find correct versions far more readily than they reject incorrect ones
  (59.7% vs 26.7%). Our T3/abstention design targets exactly this — and
  the author's separate legal tool's gate is a natural comparator.
- **Cite de Martim's LRMoo versioning pattern** for the corpus data model rather
  than inventing a schema.

---

## Citation status

All 11 entries above are **Consensus-surfaced and not yet verified** against
arXiv/Crossref. Under Rule 3 none may enter `references.bib` until verified and
logged in `logs/citations_verified.md` (Phase 1).
