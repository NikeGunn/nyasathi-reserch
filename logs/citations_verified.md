# citations_verified.md

PAPER_PLAN.md §1 rule 3: every entry in `references.bib` is verified against
arXiv, Crossref, or the publisher page, with the verification URL recorded here.
**If it cannot be verified, it is removed.**

Method: `export.arxiv.org/api/query` with an explicit non-urllib User-Agent
(root `CLAUDE.md`: a default `Python-urllib` UA gets refused by some endpoints
*before* the request is evaluated — establish which layer refused). Author lists
are copied from the API response, never from memory.

Verified **2026-09-19**.

## VERIFIED — usable in the manuscript

| Key | arXiv ID | Verified title (as returned) | Authors (as returned) | URL |
|---|---|---|---|---|
| `sobhani2026tide` | 2608.08512v3 | Time Present and Time Past: Benchmarking Large Language Models on Temporally Evolving Document Understanding | Mahbub E Sobhani; Md. Faiyaz Abdullah Sayeedi; Fahmid Hasan Chowdhury; Md Adnan Arefeen; Farig Sadeque; Md. Faizul Bari | https://arxiv.org/abs/2608.08512 |
| `cymbler2026fiscalqa` | 2608.09393v1 | Temporal Misgrounding in Legal RAG: A Versioned-Corpus Benchmark for French Tax Law | Rose Cymbler; Daniel Guez; Laurent Fabre | https://arxiv.org/abs/2608.09393 |
| `prior2026asking` | 2605.23497v1 | Asking For An Old Friend: Diagnosing and Mitigating Temporal Failure Modes in LLM-based Statutory Question Answering | Max Prior; Andreas Schultz; Matthias Grabmair | https://arxiv.org/abs/2605.23497 |
| `fan2026timetravel` | 2605.25920v1 | Can LLMs Time Travel? Enhancing Temporal Consistency in Legal Agentic Search through Reinforcement Learning | Wei Fan; Yining Zhou; Mufan Zhang; Yanbing Weng; Yiran Hu; Tianshi Zheng | https://arxiv.org/abs/2605.25920 |
| `wagle2026nepali` | 2606.07523v1 | Retrieval Augmented Generation Framework for the Nepali Legal Domain Question Answering | Samir Wagle; Abiral Adhikari; Reewaj Khanal; Batsal Bhandari; Prashant Manandhar; Praveen Acharya; **Bal Krishna Bal** | https://arxiv.org/abs/2606.07523 |
| `thapa2026nepkanun` | 2609.15999v1 | NepKANUN: A RAG-Based Nepali Legal Assistant | Bhabuk Thapa; Prasiddha Koirala; Ranjit Raut; Sunil Regmi; **Bal Krishna Bal** | https://arxiv.org/abs/2609.15999 |
| `lewis2020rag` | 2005.11401v4 | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | Patrick Lewis; Ethan Perez; Aleksandra Piktus; Fabio Petroni; + 8 | https://arxiv.org/abs/2005.11401 |
| `trivedi2023ircot` | 2212.10509v2 | Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions | Harsh Trivedi; Niranjan Balasubramanian; Tushar Khot; Ashish Sabharwal | https://arxiv.org/abs/2212.10509 |
| `jiang2023flare` | 2305.06983v2 | Active Retrieval Augmented Generation | Zhengbao Jiang; Frank F. Xu; Luyu Gao; Zhiqing Sun; + 5 | https://arxiv.org/abs/2305.06983 |
| `jeong2024adaptiverag` | 2403.14403v2 | Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity | Soyeong Jeong; Jinheon Baek; Sukmin Cho; Sung Ju Hwang; Jong C. Park | https://arxiv.org/abs/2403.14403 |
| `yao2023react` | 2210.03629v3 | ReAct: Synergizing Reasoning and Acting in Language Models | Shunyu Yao; Jeffrey Zhao; Dian Yu; Nan Du; + 3 | https://arxiv.org/abs/2210.03629 |
| `jin2025searchr1` | 2503.09516v5 | Search-R1: Training LLMs to Reason and Leverage Search Engines with Reinforcement Learning | Bowen Jin; Hansi Zeng; Zhenrui Yue; Jinsung Yoon; + 4 | https://arxiv.org/abs/2503.09516 |

`anthropic2026claude` — tool citation required by APA §9.5; not a research
paper, verified as the product page https://claude.ai.

## Draft placeholders RESOLVED by this pass

| Draft placeholder | Resolution |
|---|---|
| `[NepKANUN authors]` | Thapa, Koirala, Raut, Regmi, Bal (2026), arXiv:2609.15999 |
| `[first author]` / Wagle et al. 2026 | Wagle, Samir — full list verified, arXiv:2606.07523 |
| `[Sobhani et al. 2026]` | Verified — TIDE, arXiv:2608.08512 |
| `[FiscalQA Pro authors]` | Cymbler, Guez, Fabre — **note: draft assumed "Guez et al."; Cymbler is first author.** Correct to (Cymbler et al., 2026). |
| `[Lewis et al. 2020]` | Verified, arXiv:2005.11401 |
| `[Trivedi et al. 2023]` | Verified, arXiv:2212.10509 |
| `[Jiang et al. 2023]` | Verified — FLARE, arXiv:2305.06983 |
| `[Jeong et al. 2024]` | Verified, arXiv:2403.14403 |
| `[Yao et al. 2024]` | **Corrected to Yao et al. 2023** (ReAct, ICLR 2023), arXiv:2210.03629. The draft's year was wrong. |
| `[Jin et al. 2025]` | Verified — Search-R1, arXiv:2503.09516 |

## Corrections made to the drafts' assumptions

1. **`(Guez et al., 2026)` → `(Cymbler et al., 2026)`.** Rose Cymbler is first
   author of the FiscalQA Pro paper. The Consensus listing surfaced Guez first;
   the arXiv API is authoritative.
2. **`(Yao et al., 2024)` → `(Yao et al., 2023)`.** ReAct is ICLR 2023.
3. **NepKANUN is an *assistant*, not a benchmark.** Fine-tuned LLM + RAG,
   BERTScore-evaluated, custom QA pairs. **No amendments, no versions, no
   validity windows, no temporal dimension.** It does not pre-empt NEPVERSA.

## AUTHORSHIP GUARD — active

**Prof. Bal Krishna Bal is the last author of BOTH verified Nepali legal NLP
papers** (`wagle2026nepali`, `thapa2026nepkanun`).

PAPER_PLAN.md §14 rule 3: he **must not** be named as author, mentor, or
acknowledged unless Nikhil confirms he has agreed. **Cited only.** No contact,
no acknowledgement, no byline. This guard stays active for the whole project.

## NOVELTY GUARD — searched, nothing found

arXiv full-text queries run 2026-09-19:

| Query | Hits | Result |
|---|---|---|
| `all:Nepali AND all:amendment AND all:statute` | **0** | — |
| `all:"Bikram Sambat" OR all:"Nepali calendar"` | **0** | — |
| `all:Nepali AND all:statutory AND all:corpus` | **0** | — |
| `all:Nepali AND (all:temporal OR all:"point-in-time")` | 3 | ASR, emotion analysis, multimodal — **none legal** |

**Conclusion: no prior work on Nepali version-aware statutory retrieval, and no
prior NLP work using Bikram Sambat validity windows.** NEPVERSA's core claim
stands. Re-run this guard before submission.

## PENDING — verify before citing

Surfaced by Consensus but not confirmed against a primary index. These are
**not** in the usable section of `references.bib`.

| Work | Where to verify |
|---|---|
| Acharya et al. (2026), Nepali IR benchmark | **SIGIR 2026 proceedings / ACM DL** — 0 arXiv hits. Important: it is our "no Nepali IR benchmark exists" citation. |
| de Martim (2025) ×4 — SAT-Graph RAG, LRMoo versioning | arXiv/ACM, each separately |
| Manoharan et al. (2026) Apofasi | IEEE ISCAIE 2026 |
| Dhakal et al. (2025) | ACM DL (ICAIL 2025) |
| Zheng et al. (2025) legal retrieval benchmark | ACM DL (CS&Law 2025) |
| Poudel et al. (2024) Nepali legal MT | ACL Anthology (SIGUL @ LREC-COLING) |
| Faisal et al. (2024) LEGAL-UQA; Rakhimova et al. (2025); Begha et al. (2026) | arXiv / publisher |
