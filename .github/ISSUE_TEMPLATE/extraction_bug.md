---
name: Extraction defect
about: The parser misreads an Act
title: "[PARSER] <Act and provision>"
labels: bug, extraction
---

<!--
An Act whose footnotes the parser misreads is worth more than one it handles.
The project's record is that a footnote parser which is approximately correct
produces a corpus that looks entirely correct.
-->

**Act and provision**

**Source URL and retrieval date**

**What the parser produced**

**What the source actually says**

**How you found it**
<!-- Hand-reading, the cross-signal validator, a failing test, reproduction of
     a reported number. -->

**Does `python -m nepversa.validate corpus/raw/*.jsonl` report it?**
<!-- If not, that is itself worth knowing: the validator missing a real defect
     is a gap in the redundant-signal design. -->
