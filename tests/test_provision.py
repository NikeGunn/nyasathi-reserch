"""Tests for provision parsing, including the wholly-repealed case."""

from __future__ import annotations

import pytest

from nepversa.provision import ProvisionParseError, parse_provision

URL = "https://nepallaws.com/Laws/banking-offence-and-punishment-act-2064/chapter-2-banking-offences/section-4"

REPEALED_IN_FULL = """
# Section 4:

Estimated reading: 1 minute
881 views

1………………………….

1 Taken out by the First Amendment.

- Tagged:
"""

BLANK_NO_REASON = """
# Section 4:

881 views

.....

- Tagged:
"""


def test_wholly_repealed_section_is_kept_not_rejected() -> None:
    """REGRESSION: the 20-char floor rejected a repealed-in-full section.

    §4 of the Banking Offences Act prints only a row of dots under
    `1 Taken out by the First Amendment.` It is the clearest T3 supersession
    item in the act — a section the law states outright no longer exists — and
    the length floor threw it away as "body too short".
    """
    p = parse_provision(REPEALED_IN_FULL, URL)
    assert p.repealed_in_full is True
    assert p.number == "4"
    assert any(f.operation.value == "repeal" for f in p.footnotes.values())


def test_blank_body_without_a_repeal_footnote_is_still_rejected() -> None:
    """MUTATION: drop the REPEAL requirement in `_is_wholly_repealed` and this fails.

    A provision that is blank for an unknown reason is a parse failure. One the
    law says was taken out is data. Only the second may enter the corpus.
    """
    with pytest.raises(ProvisionParseError, match="too short"):
        parse_provision(BLANK_NO_REASON, URL)


def test_ordinary_provision_is_not_flagged_repealed() -> None:
    md = """
# Section 9: Not to misuse banking resources

881 views

No person shall misuse the resources, means or assets of a bank or financial
institution in an unauthorised manner whatsoever.

- Tagged:
"""
    p = parse_provision(md, URL)
    assert p.repealed_in_full is False
