"""Role filter on real titles (Glean, Scale AI, Sarvam, Meesho, Hume AI, Pinecone)."""

import pytest

from extract.profile import load_profile
from extract.role import match_role

P = load_profile()
PY_AI = "Requirements:\n- Strong Python\n- Experience with LLMs and evaluations"
PY = "Strong Python: FastAPI, asyncio, Pydantic"
NO_PY = "Experience with Go and Java. You will build AI products."


@pytest.mark.parametrize("title,desc,target,family", [
    ("Machine Learning Engineer, Search Quality", NO_PY, True, "ai_ml"),
    ("Software Engineer, AI/ML Infrastructure", NO_PY, True, "ai_ml"),
    ("ML Ops Engineer, Chanakya", NO_PY, True, "ai_ml"),
    ("Researcher, Vision", NO_PY, True, "ai_ml"),
    ("Applied AI Engineer, Global Public Sector", NO_PY, True, "ai_ml"),
    ("Data Scientist - Evaluations, Chanakya", NO_PY, True, "ai_ml"),
    ("Backend Engineer, Chanakya", PY, True, "backend"),
    ("Software Engineer, Backend", PY, True, "backend"),
    ("Backend Engineer - Studio Media Platform", NO_PY, False, "backend"),  # not a Python stack
    ("Software Engineer - New Grad", PY_AI, True, "generic_swe"),
    ("Software Engineer, Platform", NO_PY, False, "generic_swe"),
    ("Frontend Engineer, Chanakya", PY_AI, False, None),
    ("Software Engineer, Frontend", PY_AI, False, None),
    ("Quality Assurance Engineer", PY_AI, False, None),
    ("Product Marketing Manager, AI", PY_AI, False, None),
    ("Product Designer", PY_AI, False, None),
    ("AI Success Manager, West", PY_AI, False, None),
    ("Product Operations Lead, Generative AI", PY_AI, False, None),
    ("Account Executive", PY_AI, False, None),
])
def test_role(title, desc, target, family):
    r = match_role(title, desc, P)
    assert (r.is_target, r.family) == (target, family), r.reason


def test_intern_needs_stated_conversion():
    no = match_role("Machine Learning Intern", "Summer internship working on LLM evals.", P)
    yes = match_role("Machine Learning Intern", "Strong performers receive a pre-placement offer (PPO).", P)
    assert not no.is_target and "conversion" in no.reason
    assert yes.is_target
    assert any(e["kind"] == "conversion" for e in yes.evidence)


def test_backend_evidence_is_the_python_line():
    r = match_role("Backend Engineer", "About us\n- 3+ years with Python and FastAPI\n- Postgres", P)
    assert {"kind": "python_stack", "snippet": "- 3+ years with Python and FastAPI"} in r.evidence


def test_generic_swe_can_be_switched_off(tmp_path):
    cfg = tmp_path / "profile.yaml"
    cfg.write_text(open("config/profile.yaml").read().replace("enabled: true", "enabled: false"))
    off = load_profile(cfg)
    assert not match_role("Software Engineer - New Grad", PY_AI, off).is_target


@pytest.mark.parametrize("title,description,target", [
    ("Android Developer", "Kotlin, Jetpack Compose", True),
    ("Mobile Engineer (iOS/Android)", "", True),  # naming Android beats the iOS/mobile excludes
    ("React Native Developer", "", True),
    ("Mobile Engineer", "We build our app in React Native.", True),
    ("Mobile Engineer", "Swift and SwiftUI only.", False),  # generic title needs an Android / RN stack
    ("Senior iOS Engineer", "", False),
    ("Flutter Developer", "", False),
    ("Frontend Engineer (React Native)", "", False),  # still a frontend title
    ("QA Engineer - Android", "", False),
    ("Android Developer Intern", "Kotlin", False),  # interns still need stated conversion
])
def test_mobile_family(title, description, target):
    r = match_role(title, description, P)
    assert r.is_target is target
    if target:
        assert r.family == "mobile"
