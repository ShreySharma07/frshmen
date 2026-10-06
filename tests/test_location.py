"""Location → countries, on real strings seen in fetched postings."""

import pytest

from extract.location import REMOTE_UNSPECIFIED, extract_location


@pytest.mark.parametrize("raw,ats,countries,remote", [
    ("Bangalore, Karnataka", ["IN"], ["India"], False),
    ("Bengaluru / Chennai", ["India"], ["India"], False),
    ("Mumbai, Maharashtra / Delhi NCR / Bangalore, Karnataka", ["IN"], ["India"], False),
    ("hyderabad", ["IN"], ["India"], False),
    ("San Francisco, CA; New York, NY", [], ["United States"], False),
    ("Mountian View, CA", [], ["United States"], False),  # typo in the posting
    ("United Sates, Remote", [], ["United States"], True),  # typo in the posting
    ("Remote - US", [], ["United States"], True),
    ("US Remote", ["USA"], ["United States"], True),
    ("NYC, San Jose, or Remote", [], ["United States"], True),
    ("Mexico City, MX", [], ["Mexico"], False),
    ("Doha, Qatar; London, UK", [], ["Qatar", "United Kingdom"], False),
    ("Canada; United States", [], ["Canada", "United States"], False),
    ("Argentina; Uruguay", [], ["Argentina", "Uruguay"], False),
    ("Tokyo, Japan", [], ["Japan"], False),
    ("Remote", [], [REMOTE_UNSPECIFIED], True),
    ("", [], [], False),
])
def test_countries(raw, ats, countries, remote):
    loc = extract_location(raw, ats)
    assert (loc.countries, loc.remote) == (countries, remote)


def test_lowercase_us_is_not_a_country():
    assert extract_location("Join us in London").countries == ["United Kingdom"]


def test_evidence_keeps_raw_text_and_ats_code():
    loc = extract_location("Bangalore, Karnataka", ["IN"])
    assert {"kind": "location", "snippet": "Bangalore, Karnataka"} in loc.evidence
    assert {"kind": "ats_country", "snippet": "IN"} in loc.evidence
