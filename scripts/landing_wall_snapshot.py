"""Writes the landing page's starter wall: the deciding line of every real posting in the test
fixtures, labelled by Kario's own extractor. The page shows these before /api/evidence answers
(and when it can't), so the wall is real text even offline.

  python scripts/landing_wall_snapshot.py   # writes site/src/components/landing/wall-snapshot.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extract.classify import classify  # noqa: E402
from sources import ashby, greenhouse, lever  # noqa: E402
from sources.models import Company  # noqa: E402

FIX = ROOT / "tests/fixtures"
OUT = ROOT / "site/src/components/landing/wall-snapshot.json"
KINDS = ("yoe_required", "batch", "fresher_text", "yoe_preferred")


def postings():
    for line in (FIX / "labeled/postings.jsonl").read_text().splitlines():
        p = json.loads(line)
        yield p["company"], p["title"], p["description_text"]
    src = FIX / "sources"
    for parse, file, company in ((greenhouse.parse, "greenhouse_humeai.json", Company("Hume AI", "greenhouse", "humeai")),
                                 (lever.parse, "lever_cred.json", Company("CRED", "lever", "cred")),
                                 (ashby.parse, "ashby_pinecone.json", Company("Pinecone", "ashby", "pinecone"))):
        for j in parse(json.loads((src / file).read_text()), company):
            yield j.company, j.title, j.description_text


def main() -> int:
    lines, seen = [], set()
    for company, title, text in postings():
        label = classify(title, text)
        ev = next((e for k in KINDS for e in label.evidence if e.get("kind") == k and e.get("snippet")), None)
        if not ev or ev["snippet"] in seen:
            continue
        seen.add(ev["snippet"])
        lines.append({"company": company, "title": title, "level": label.level,
                      "yoe_min": label.yoe_min, "yoe_max": label.yoe_max, "text": ev["snippet"][:200]})
    OUT.write_text(json.dumps(lines, ensure_ascii=False, indent=0) + "\n")
    print(f"{len(lines)} lines -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
