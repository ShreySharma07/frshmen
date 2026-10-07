"""Score rules + Gemini on the labeled postings, the gate before trusting the LLM step.

For each labeled posting the rules run first; the ones they leave in `maybe` go to the
model and the verdict is applied exactly as in the pipeline. Every call must get an answer, or the eval fails. A posting's truth is its
`expected_after_llm` label when present, else `expected_level`: a `maybe` case the model
lifts to `fresher` counts as wrong until a person relabels it. Exits non-zero if fresher
precision drops below 100%.

Needs GEMINI_API_KEY. Run: python scripts/eval_llm.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_extractor import LEVELS, load  # noqa: E402
from extract import llm  # noqa: E402
from extract.classify import classify  # noqa: E402
from llm_review import CallFailed, QuotaExhausted, gemini_call  # noqa: E402


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY not set.", file=sys.stderr)
        return 2
    call = gemini_call(key)
    matrix: Counter[tuple[str, str]] = Counter()
    asked = answered = 0
    for case in load():
        rec = {**classify(case["title"], case["description_text"]).to_dict(),
               "title": case["title"], "description_text": case["description_text"]}
        note = ""
        if llm.needs_review(rec):
            asked += 1
            try:
                verdict = llm.review(rec, call)
            except (CallFailed, QuotaExhausted) as e:
                print(f"ERR {case['company']}: {case['title']}: Gemini gave no answer ({e})")
                continue
            answered += 1
            if verdict:
                rec = llm.apply(rec, verdict)
                note = f'  LLM quote: "{verdict.quote[:120]}"'
            else:
                note = "  LLM: no usable answer"
        truth = case.get("expected_after_llm", case["expected_level"])
        matrix[(truth, rec["level"])] += 1
        mark = "ok " if truth == rec["level"] else "BAD"
        print(f"{mark} {case['company']}: {case['title']} -> {rec['level']} (expected {truth}){note}")

    predicted = sum(v for (_, got), v in matrix.items() if got == "fresher")
    precision = matrix[("fresher", "fresher")] / predicted if predicted else 1.0
    model = call.models[0] if call.models else "no model"
    if asked and answered < asked:
        # A run where the model never answered says nothing about its precision.
        print(f"\n{model}: only {answered}/{asked} calls answered; eval is incomplete.")
        return 1
    print(f"\n{model}: fresher precision {precision:.0%} ({predicted} predicted fresher). Expected -> got:")
    for lvl in LEVELS:
        print(f"  {lvl:>11}: " + " ".join(f"{got}={matrix[(lvl, got)]}" for got in LEVELS))
    return 0 if precision == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
