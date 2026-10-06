"""Extractor tests: labeled real postings first, then focused pattern cases."""

import pytest

import eval_extractor
from extract.classify import classify
from extract.sections import clauses
from extract.signals import batch_years, senior_title
from extract.yoe import find_mentions

CASES = eval_extractor.load()


# --- Real postings (tests/fixtures/labeled/postings.jsonl) ------------------------

@pytest.mark.parametrize("case", CASES, ids=[f"{c['company']}|{c['title']}" for c in CASES])
def test_labeled_posting(case):
    result = classify(case["title"], case["description_text"])
    assert result.level == case["expected_level"], f"{result.reason}\nlabel note: {case['why']}"


def test_fresher_precision_never_regresses():
    assert eval_extractor.evaluate(CASES)["fresher_precision"] == 1.0


def test_label_set_covers_every_level():
    levels = {c["expected_level"] for c in CASES}
    assert levels == {"fresher", "maybe", "experienced"}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_evidence_is_verbatim(case):
    """Every snippet must be findable in the posting, or a wrong label can't be traced back."""
    result = classify(case["title"], case["description_text"])
    haystack = case["title"] + "\n" + case["description_text"]
    for e in result.evidence:
        assert e["snippet"] in haystack, e


# --- Years-of-experience patterns --------------------------------------------------

def yoe(text, heading=None):
    body = f"{heading}\n{text}" if heading else text
    return [(m.min_years, m.max_years, m.required) for m in find_mentions(clauses(body))]


@pytest.mark.parametrize("text,expected", [
    ("3+ years of experience with Python", [(3, None, True)]),
    ("2-4 years of experience", [(2, 4, True)]),
    ("2 to 3 yrs experience in ML", [(2, 3, True)]),
    ("At least 5 years of professional experience", [(5, None, True)]),
    ("Minimum of 2 years working with PyTorch", [(2, None, True)]),
    ("min. 1-2 years of experience", [(1, 2, True)]),
    ("Five years of experience in backend systems", [(5, 5, True)]),
    ("At least three years of experience", [(3, None, True)]),
    ("five (5) years of relevant experience", [(5, 5, True)]),
    ("0-1 years of experience", [(0, 1, True)]),
    ("6 months of industry experience", [(0.5, 0.5, True)]),
    ("Up to 2 years of experience", [(0, 2, True)]),
    ("3–6 years in backend engineering", [(3, 6, True)]),
    ("5 years or more of experience", [(5, None, True)]),
    ("5+ years in ML systems, with 2+ years authoring CUDA kernels", [(5, None, True), (2, None, True)]),
])
def test_yoe_patterns(text, expected):
    assert yoe(text) == expected


@pytest.mark.parametrize("text", [
    "For 10 years, Scale has provided high-quality data to the world's leading models.",
    "For the past ten years, Scale has been the leading AI data foundry.",
    "If you have applied within the past 6 months, only your first application counts.",
    "We were founded 5 years ago and work with top labs.",
    "A 4-year degree in Computer Science",
    "This is a 6-month contract with possible extension.",
    "We have grown 3x over the last 2 years.",
    "Our 9 guiding principles shape how we work.",
])
def test_numbers_that_are_not_experience(text):
    assert yoe(text) == []


@pytest.mark.parametrize("text,heading", [
    ("2+ years of experience with Kubernetes", "Nice to have:"),
    ("2+ years of experience with Kubernetes", "Bonus Points"),
    ("2+ years of experience with Kubernetes is a plus", None),
    ("0-1 years of similar experience are preferred", None),
])
def test_preferred_years(text, heading):
    assert [r for *_, r in yoe(text, heading)] == [False]


def test_ideally_heading_still_means_required():
    assert yoe("At least three years of experience", "Ideally you'd have:") == [(3, None, True)]


def test_plus_on_another_clause_does_not_soften_the_years():
    assert yoe("8+ years of SaaS marketing experience, agentic AI experience is a plus") == [(8, None, True)]


def test_parenthetical_preference_does_not_soften_the_years():
    assert yoe("5+ years of research experience (PhD or equivalent preferred) in ML") == [(5, None, True)]


def test_long_requirement_line_is_not_a_heading():
    # Not a "preferred" section heading, so the next line stays required.
    assert yoe("3+ years of experience in audit", "Articleship in Big 4 preferred") == [(3, None, True)]


# --- Titles and batch years -------------------------------------------------------

@pytest.mark.parametrize("title,senior", [
    ("Senior Software Engineer", True),
    ("Sr. ML Engineer", True),
    ("Staff Engineer", True),
    ("Tech Lead Manager", True),
    ("Engineering Manager", True),
    ("Principal Scientist", True),
    ("Software Engineer III", True),
    ("Assistant Manager - Business Finance", False),
    ("Associate Product Manager", False),
    ("Machine Learning Fellow - Human Frontier Collective", False),
    ("ML Engineer", False),
    ("Software Engineer - New Grad", False),
])
def test_senior_title(title, senior):
    assert (senior_title(title) is not None) == senior


@pytest.mark.parametrize("text,years", [
    ("Qualified CA Fresher from 2025/2026 batch.", [2025, 2026]),
    ("A graduation date in Fall 2026 or Spring 2027 with a Bachelor's degree", [2026, 2027]),
    ("Class of 2026 graduates welcome", [2026]),
    ("Founded in 2019, we are hiring.", []),
])
def test_batch_years(text, years):
    assert batch_years(clauses(text))[0] == years


# --- Decision table -----------------------------------------------------------------

@pytest.mark.parametrize("title,text,level", [
    ("ML Engineer", "Requirements:\n- 2+ years of experience with PyTorch", "experienced"),
    ("Junior ML Engineer", "Requirements:\n- 3+ years of experience", "experienced"),  # junior title can't override
    ("ML Engineer - New Grad", "Requirements:\n- 2+ years of experience", "experienced"),  # signal can't override
    ("ML Engineer", "We welcome new grads.\n- 1+ years of experience", "maybe"),  # open-ended 1+ conflicts
    ("ML Engineer", "Requirements:\n- 0-1 years of experience", "fresher"),
    ("ML Engineer", "Entry level role.\nNice to have:\n- 2+ years of experience", "fresher"),
    ("ML Engineer", "Open to 2024 batch graduates only.", "maybe"),  # other batch: not Shrey's
    ("ML Engineer", "Build models with PyTorch.", "maybe"),
    ("Senior ML Engineer", "We welcome new grads.", "experienced"),
])
def test_decision_table(title, text, level):
    assert classify(title, text).level == level


def test_preferred_years_lower_fresher_confidence():
    plain = classify("ML Engineer", "Entry level role.")
    softened = classify("ML Engineer", "Entry level role.\nNice to have:\n- 2+ years of experience")
    assert softened.level == plain.level == "fresher"
    assert softened.level_confidence < plain.level_confidence


def test_result_carries_schema_fields():
    r = classify("ML Engineer", "Requirements:\n- 3+ years of experience building ML systems")
    assert (r.yoe_min, r.yoe_max) == (3, None)
    assert r.yoe_evidence == "3+ years of experience building ML systems"
