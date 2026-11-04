"""The tailored resume's no-new-claims check (api/src/tailor.py)."""

import tailor

LINES = [
    "Asha Verma",
    "asha@example.com | +91 98765 43210",
    "Built a chatbot using LangChain that served 200 daily users",
    "Python, PyTorch, FastAPI",
    "B.Tech Computer Science (AI), 2026",
    "Volunteer at the college library",
]


def answer(*lines, heading="Projects", name="Asha Verma"):
    return {"name": name, "note": "Moved projects up.", "sections": [{"heading": heading, "lines": list(lines)}]}


def test_a_faithful_rewording_is_kept():
    out = tailor.guard(answer({"text": "Built a LangChain chatbot serving 200 daily users", "sources": [3]}), LINES, "Asha")
    line = out["sections"][0]["lines"][0]
    assert line["text"] == "Built a LangChain chatbot serving 200 daily users" and not line["kept_original"]
    assert line["original"] == LINES[2]
    assert out["kept_original"] == 0


def test_calling_the_chatbot_rag_is_a_new_claim():
    # "RAG" is a catalogued skill that line 3 never states, so the rewording goes back.
    out = tailor.guard(answer({"text": "Built a RAG chatbot with LangChain serving 200 daily users", "sources": [3]}), LINES, "Asha")
    assert out["sections"][0]["lines"][0]["kept_original"]


def test_a_line_that_adds_a_skill_goes_back_to_the_original():
    out = tailor.guard(answer({"text": "Built a chatbot with LangChain on Kubernetes for 200 daily users", "sources": [3]}), LINES, "Asha")
    line = out["sections"][0]["lines"][0]
    assert line["kept_original"] and line["text"] == LINES[2] and "Kubernetes" in line["reason"]
    assert out["kept_original"] == 1


def test_a_line_that_adds_a_number_goes_back_to_the_original():
    out = tailor.guard(answer({"text": "Built a chatbot using LangChain that served 2,000 daily users", "sources": [3]}), LINES, "Asha")
    line = out["sections"][0]["lines"][0]
    assert line["kept_original"] and "2000" in line["reason"]


def test_a_skill_must_come_from_the_lines_cited_not_just_anywhere():
    # PyTorch is on the resume, but not on line 3: the claim "the chatbot used PyTorch" is new.
    out = tailor.guard(answer({"text": "Built a PyTorch chatbot using LangChain for 200 daily users", "sources": [3]}), LINES, "Asha")
    assert out["sections"][0]["lines"][0]["kept_original"]
    # Citing both lines is honest about where each part comes from.
    out = tailor.guard(answer({"text": "Built a chatbot using LangChain for 200 daily users; Python, PyTorch", "sources": [3, 4]}), LINES, "Asha")
    assert not out["sections"][0]["lines"][0]["kept_original"]


def test_lines_without_valid_sources_are_dropped():
    out = tailor.guard(answer({"text": "Led a team of 5", "sources": []}, {"text": "Shipped X", "sources": [99]},
                              {"text": "Python, PyTorch, FastAPI", "sources": [4]}), LINES, "Asha")
    assert [l["text"] for l in out["sections"][0]["lines"]] == ["Python, PyTorch, FastAPI"] and out["dropped"] == 2


def test_headings_and_names_cannot_smuggle_claims():
    out = tailor.guard(answer({"text": "Python, PyTorch, FastAPI", "sources": [4]}, heading="Kubernetes Expert", name="Dr. Asha Verma"), LINES, "Asha V.")
    assert out["sections"][0]["heading"] == "" and out["name"] == "Asha V."


def test_left_out_lines_are_listed():
    out = tailor.guard(answer({"text": "Python, PyTorch, FastAPI", "sources": [4]}), LINES, "Asha")
    assert "Volunteer at the college library" in out["left_out"] and "Python, PyTorch, FastAPI" not in out["left_out"]


def test_unusable_answers_are_refused():
    assert tailor.guard("not json", LINES, "Asha") is None
    assert tailor.guard({"sections": [{"heading": "X", "lines": [{"text": "a", "sources": []}]}]}, LINES, "Asha") is None


def test_prompt_numbers_the_resume_lines():
    prompt = tailor.build_prompt({"title": "ML Engineer", "company": "Acme", "description_text": "Python"}, LINES)
    assert "3: Built a chatbot" in prompt and "ML Engineer at Acme" in prompt
