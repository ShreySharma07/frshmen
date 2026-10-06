"""Score the classifier on the labeled real postings in tests/fixtures/labeled/.

Prints the confusion matrix, fresher precision/recall, and every mismatch with
the evidence the classifier used. Exits non-zero if fresher precision < 1.0,
since a non-fresher job in the fresher bucket is the bug this project exists to avoid.

Run: python scripts/eval_extractor.py [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `extract` imports when run as a plain script

from extract.classify import classify  # noqa: E402

LABELED = ROOT / "tests" / "fixtures" / "labeled" / "postings.jsonl"
LEVELS = ["fresher", "maybe", "experienced"]


def load(path: Path = LABELED) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def evaluate(cases: list[dict]) -> dict:
    pairs = []
    for case in cases:
        result = classify(case["title"], case["description_text"])
        pairs.append((case, result))
    matrix = Counter((c["expected_level"], r.level) for c, r in pairs)
    predicted_fresher = sum(v for (_, got), v in matrix.items() if got == "fresher")
    actual_fresher = sum(v for (exp, _), v in matrix.items() if exp == "fresher")
    true_fresher = matrix[("fresher", "fresher")]
    return {
        "pairs": pairs,
        "matrix": matrix,
        "accuracy": sum(matrix[(lvl, lvl)] for lvl in LEVELS) / max(len(cases), 1),
        "fresher_precision": true_fresher / predicted_fresher if predicted_fresher else 1.0,
        "fresher_recall": true_fresher / actual_fresher if actual_fresher else 1.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verbose", action="store_true", help="show evidence for every case, not just mismatches")
    args = parser.parse_args()

    report = evaluate(load())
    m = report["matrix"]
    header = "expected \\ got"
    print(f"{header:>16} " + " ".join(f"{lvl:>11}" for lvl in LEVELS))
    for exp in LEVELS:
        print(f"{exp:>16} " + " ".join(f"{m[(exp, got)]:>11}" for got in LEVELS))
    print(f"\naccuracy {report['accuracy']:.0%}   fresher precision {report['fresher_precision']:.0%}"
          f"   fresher recall {report['fresher_recall']:.0%}   ({len(report['pairs'])} postings)")

    for case, r in report["pairs"]:
        if not args.verbose and case["expected_level"] == r.level:
            continue
        mark = "OK " if case["expected_level"] == r.level else "BAD"
        print(f"\n{mark} {case['company']} | {case['title']}\n    expected {case['expected_level']}, got {r.level}"
              f" ({r.level_confidence}): {r.reason}\n    label note: {case['why']}")
        for e in r.evidence[:5]:
            print(f"    [{e['kind']}] {e['snippet'][:160]}")
    return 0 if report["fresher_precision"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
