"""Skills counted in postings and resumes (extract/skills.py, config/skills.yaml)."""

import export_skills
from extract.skills import load_skills, skills_in


def test_finds_whole_words_only():
    text = "We use Python and PyTorch; experience with C++ and Kubernetes (k8s) is a plus."
    assert skills_in(text) == ["Python", "PyTorch", "Kubernetes", "C++"]
    # "C" inside "C++" doesn't count as anything else, and "Pythonic" isn't "Python".
    assert skills_in("Pythonic code, CI/CD") == []


def test_exact_skills_ignore_ordinary_english():
    # Ray, Spark, Rust and React are also words: only their tool spelling counts.
    assert skills_in("A ray of hope; spark curiosity; rust-free; react quickly") == []
    assert skills_in("Ray and Spark clusters, Rust services, a React app") == ["Spark", "Ray", "Rust", "React"]


def test_case_and_variants():
    assert skills_in("experience with large language models and pytorch") == ["PyTorch", "LLMs"]
    assert skills_in("Familiar with Postgres and sklearn") == ["scikit-learn", "PostgreSQL"]
    assert skills_in("") == [] and skills_in(None) == []


def test_go_needs_an_unambiguous_spelling():
    assert skills_in("Ready to go the extra mile") == []
    assert skills_in("Services in Golang") == ["Go"]


def test_catalogue_names_are_unique():
    names = [s.name for s in load_skills()]
    assert len(names) == len(set(names))


def test_site_copy_matches_config():
    # The dashboard ticks resume skills with this copy; run scripts/export_skills.py after editing.
    assert export_skills.TARGET.read_text() == export_skills.exported()

