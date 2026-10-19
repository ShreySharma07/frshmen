"""The stored description: about the role, required, preferred; nothing the label relies on is lost."""

from extract import stored_text as st
from extract.classify import classify

POSTING = """About Acme
Acme builds search for enterprises. We raised $100M.
About the role
You will build retrieval systems used by millions.
What you'll do
- Train ranking models in PyTorch
- Ship features end to end
What we're looking for
- 0-2 years of experience with Python
- Strong CS fundamentals
Nice to haves
- Experience with LLM evals
Benefits
- Free lunch
Compensation & Benefits
$120,000—$150,000 USD
Equal opportunity
Acme is an equal opportunity employer."""


def test_keeps_the_three_sections_and_drops_the_rest():
    text = st.compact(POSTING)
    assert text.startswith("About the role\nYou will build retrieval systems")
    assert "- Train ranking models in PyTorch" in text
    assert "Required\n- 0-2 years of experience with Python" in text
    assert "Preferred\n- Experience with LLM evals" in text
    for dropped in ("We raised", "Free lunch", "$120,000", "equal opportunity employer"):
        assert dropped not in text


def test_ideally_youd_have_is_required_not_preferred():
    """Scale AI uses it for the main requirements (as extract/sections.py knows)."""
    sections = st.split("About the role\nLabel data.\nIdeally you'd have:\n- 3+ years of experience\nNice to haves:\n- A PhD")
    assert "3+ years" in sections["required"] and "PhD" in sections["preferred"]


def test_the_yoe_line_behind_the_label_is_always_kept():
    """Under a heading we drop, the requirement would vanish; evidence brings it back."""
    posting = "About the role\nBuild agents.\nWhy join us\n- You have 3+ years of experience in data science."
    label = classify("Data Scientist", posting)
    assert label.yoe_evidence and label.yoe_evidence not in st.compact(posting)
    stored = st.compact(posting, label.evidence)
    assert label.yoe_evidence in stored
    assert classify("Data Scientist", stored).level == label.level == "experienced"


def test_compacting_stored_text_changes_nothing():
    label = classify("ML Engineer", POSTING)
    once = st.compact(POSTING, label.evidence)
    assert st.compact(once, label.evidence) == once


def test_a_posting_without_headings_keeps_its_opening():
    text = st.compact("We are hiring a backend engineer to build payment APIs in Go and Python. " * 60)
    assert text.startswith("About the role\nWe are hiring a backend engineer")
    assert len(text) <= len("About the role\n") + st.LIMITS["about"]
    assert text.endswith(" …")
