"""What leaves for Gemini (api/src/privacy.py; docs/decisions.md, 2026-11-18, security review M4)."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api" / "src"))

import fit  # noqa: E402
import tailor  # noqa: E402
from privacy import redact  # noqa: E402

RESUME = """Asha Rao
asha.rao@example.com · +91 98765 43210 · (080) 4123-4567 · github.com/asharao
PROJECTS
Built a RAG search over 10,000 papers in Python, 2022 - 2026
Cut latency by 30% (p95 12 ms)"""


def test_emails_and_phones_go_years_and_numbers_stay():
    out = redact(RESUME)
    assert "asha.rao@example.com" not in out and "98765" not in out and "4123-4567" not in out
    assert out.count("[email]") == 1 and out.count("[phone]") == 2
    for kept in ("github.com/asharao", "10,000", "2022 - 2026", "30%", "12 ms", "Asha Rao"):
        assert kept in out, kept


def test_the_fit_check_prompt_has_no_contact_details():
    prompt = fit.build_prompt({"title": "ML Engineer", "company": "Acme", "description_text": "Python"}, RESUME)
    assert "asha.rao@example.com" not in prompt and "98765" not in prompt and "[email]" in prompt


def test_a_tailored_resume_keeps_the_real_contact_line():
    sent = []

    async def post(url, headers, body):
        sent.append(body)
        answer = {"name": "Asha Rao", "note": "n", "sections": [
            {"heading": "", "lines": [{"text": "[email] · [phone] · [phone] · github.com/asharao", "sources": [2]}]},
            {"heading": "PROJECTS", "lines": [{"text": "Built RAG search over 10,000 papers in Python", "sources": [4]}]}]}
        return 200, {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}

    result = asyncio.run(tailor.improve(RESUME, "Asha Rao", "key", post))
    assert "asha.rao@example.com" not in sent[0] and "98765" not in sent[0]
    contact = result["sections"][0]["lines"][0]
    assert contact["text"] == "asha.rao@example.com · +91 98765 43210 · (080) 4123-4567 · github.com/asharao"
    assert result["sections"][1]["lines"][0]["text"] == "Built RAG search over 10,000 papers in Python"
    assert "Cut latency by 30% (p95 12 ms)" in result["left_out"]  # unredacted, as the editor keeps it
