# Human verification: what is required before NEPVERSA items become gold

**Status as of 2026-09-20: NOT PERFORMED.**

All 46 benchmark items carry `status=unverified`. No audited sample exists, no
error rate has been computed, and no inter-annotator agreement has been
calculated, because no audit has taken place. This file specifies what would
have to happen, so that the gap is a scheduled task rather than an ambiguity.

It exists because the manuscript previously described an audit in the present
tense ("We report the audited sample and its error rate") that had never been
carried out. That text is now corrected. A reviewer who asks "what was the
error rate?" must find either a number with raw data behind it, or a plain
statement that no audit was done. Never a sentence that implies the first while
meaning the second.

---

## 1. What the pipeline already guarantees, and what it does not

| Guaranteed mechanically | **Not** guaranteed |
|---|---|
| The candidate transcribes a published footnote faithfully | That the item poses a well-formed legal question |
| The cited provision exists and the citation resolves | That a lawyer would agree the cited provision governs |
| The quoted span matches the source character-for-character | That the quotation is the *relevant* span |
| The operation (insert/substitute/repeal) matches the legend | That the amendment ordinal maps to the date a user means |
| The validity window is internally consistent | That the window reflects actual commencement |

The audit exists to test the right-hand column. It cannot be replaced by more
parsing, by a second model, or by the author's own reading: the author built
the extractor, so the author checking its output is not an independent test.

## 2. Who may audit

An auditor must hold a law degree recognised in Nepal (LL.B. or higher) **or**
be a final-year law student supervised by an advocate. They must be able to
read statutory Nepali in Devanagari. They must not have contributed to the
extraction code.

Record for each auditor, in `AUDIT/annotators.csv`:

```text
annotator_id,qualification,institution,reads_devanagari,consented_to_named_credit,date_briefed
```

Use a pseudonymous `annotator_id` (`A1`, `A2`) in all published material unless
the auditor has given written consent to be named (PAPER_PLAN.md §13 rule 4 and
RELEASE_OK.md D5.5). Consent to be acknowledged is not consent to be named as
an author.

## 3. Sample size and stratification

Audit **at least 50 items**, drawn to cover the failure modes rather than by
simple random sampling, which on 46 items would leave whole categories unseen.

| Stratum | Items available | Minimum to audit |
|---|---|---|
| T2 point-in-time, answerable | 24 | 12 |
| T2 point-in-time, abstention expected | 12 | 12 (all) |
| T3 supersession (all abstention-expected) | 10 | 10 (all) |
| Items whose provenance is numbering only, no footnote | 5 | 5 (all) |
| Items from a wholly repealed section | 1 | 1 (all) |

Because the corpus is smaller than the target sample, this amounts to auditing
every item at least once, with the answerable T2 items double-audited. That is
the correct response to a small corpus: do not sample, enumerate.

**Double-annotate at least 20 items** (both auditors, independently, no
discussion) so agreement can be computed at all. Agreement on a single
annotator's labels is not a statistic.

## 4. What the auditor decides per item

For each item the auditor records, blind to the pipeline's answer where
possible:

```text
item_id
auditor_id
question_is_well_formed        yes | no | unclear
cited_provision_is_correct     yes | no | unclear
quoted_span_is_relevant        yes | no | n/a
expected_answer_agrees         yes | no | unclear
abstention_is_correct          yes | no | n/a
comment                        free text, required when anything is not "yes"
minutes_spent
```

`unclear` is a first-class outcome and must not be coerced to yes or no. An
item that a qualified reader cannot decide is itself a finding about the
source.

## 5. Statistics to compute, and only these

Computed by `analysis/compute_iaa.py` (to be written when labels exist; it must
not be written to produce placeholder output beforehand):

- **Item-level error rate**: the proportion of audited items where any field is
  `no`, with a Wilson 95% confidence interval. On 46 items the interval will be
  wide; report it rather than the point estimate alone.
- **Cohen's kappa** on the doubly-annotated subset, per field, reported with
  the raw agreement percentage beside it. Kappa is unstable on small, skewed
  samples; the two numbers together are honest, either alone is not.
- **Disagreement inventory**: every disagreeing item listed with both labels
  and the adjudicated outcome. A disagreement resolved by discussion is
  recorded as adjudicated, not as agreement.

Do not compute an F1 against the pipeline. The pipeline is the thing under
test, so scoring it against itself measures nothing.

## 6. Adjudication

Disagreements are resolved by a third qualified reader, or by the two auditors
in a recorded discussion. Record the adjudicated label **and** the original
labels. Never overwrite a label with its adjudicated value: the disagreement
rate is a result.

## 7. What changes in the manuscript afterwards

Only after the above exists:

1. Items that passed become `status=verified`, and only those.
2. Items that failed are **kept in the release** with `status=rejected` and the
   reason. A benchmark that silently drops its failures overstates its own
   quality.
3. Method gains the real sample size, error rate with CI, and kappa.
4. Limitations loses the "no human verification" paragraph and gains the true
   residual limitation (sample coverage, annotator count, disagreement rate).
5. The abstract's "all `status=unverified` pending legal audit" is replaced
   with the measured proportion.
6. `AUDIT/audit_raw/` holds the raw label files, unedited, committed.

Every one of those numbers must be computed by a script from the raw labels and
logged in `logs/PROVENANCE.md`. None may be typed into the manuscript by hand.

## 8. Cost and time, honestly

At roughly 6 to 10 minutes per item for a careful reader, 46 items double-
annotated on 20 of them is about 8 to 11 hours of qualified time, plus
adjudication. That is one to two days of a law graduate's work, and it is the
single remaining obstacle between this resource and a validated benchmark.

Until it is done, the correct description of NEPVERSA is **a method and a
corpus with mechanically derived candidates**, which is what the manuscript now
says.
