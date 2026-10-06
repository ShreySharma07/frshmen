"""Visa sponsorship and the location rules from the profile."""

import pytest

from extract.eligibility import check_eligibility
from extract.location import REMOTE_UNSPECIFIED
from extract.visa import Visa, extract_visa


@pytest.mark.parametrize("text,sponsorship,relocation", [
    ("Visa sponsorship is available for this role.", "yes", False),
    ("We will sponsor H-1B visas.", "yes", False),
    ("We are unable to sponsor visas for this role.", "no", False),
    ("Candidates must be authorized to work in the US without sponsorship.", "no", False),
    ("This role is not eligible for visa sponsorship.", "no", False),
    # A "no" wins over a "yes" anywhere else in the posting.
    ("Visa sponsorship is available for some teams. We cannot sponsor for this position.", "no", False),
    ("We offer relocation assistance to Berlin.", "unknown", True),
    ("Python, PyTorch and LLMs.", "unknown", False),
])
def test_visa(text, sponsorship, relocation):
    v = extract_visa(text)
    assert (v.sponsorship, v.relocation) == (sponsorship, relocation)
    if sponsorship != "unknown" or relocation:
        assert v.evidence and v.evidence[0]["snippet"] in text


NONE = Visa("unknown", False)


@pytest.mark.parametrize("countries,cities,mode,visa,eligible", [
    (["India"], ["Pune"], "onsite", NONE, True),
    (["India"], ["Bengaluru"], "onsite", NONE, False),  # onsite-only in a hidden city
    (["India"], ["Bengaluru", "Hyderabad"], "onsite", NONE, False),
    (["India"], ["Bengaluru"], "hybrid", NONE, True),
    (["India"], ["Bengaluru"], None, NONE, True),  # work mode unknown: don't hide
    (["India"], ["Bengaluru", "Pune"], "onsite", NONE, True),  # Pune is an option
    ([REMOTE_UNSPECIFIED], [], "remote", NONE, True),
    (["United States"], [], "remote", NONE, False),  # remote-US still needs US work authorization
    (["United States"], [], "onsite", Visa("yes", False), True),
    (["Germany"], [], "onsite", Visa("unknown", True), True),
    (["Germany"], [], "onsite", Visa("no", True), False),  # relocation doesn't beat an explicit "no sponsorship"
    ([], [], None, NONE, True),
])
def test_eligibility(countries, cities, mode, visa, eligible):
    assert check_eligibility(countries, cities, mode, visa).eligible is eligible
