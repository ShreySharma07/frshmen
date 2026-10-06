import yaml

import import_yc as yc


def co(name, slug=None, tags=("AI",), batch="Summer 2024", team=20, regions=("United States of America",), status="Active"):
    return {"name": name, "slug": slug or name.lower(), "tags": list(tags), "batch": batch, "team_size": team,
            "regions": list(regions), "status": status, "isHiring": True}


def test_filter_keeps_recent_hiring_ai_startups():
    data = [
        co("Keep"),
        co("NotAI", tags=("Fintech",)),
        co("TooOld", batch="Winter 2019"),
        co("TooSmall", team=3),
        co("SmallButIndia", team=3, regions=("India", "South Asia")),
        co("Dead", status="Inactive"),
    ]
    names = [e["name"] for e in yc.new_entries(data, [])]
    assert sorted(names) == ["Keep", "SmallButIndia"]


def test_skips_companies_already_listed_by_name_or_slug():
    existing = [{"name": "Simple AI", "slug": "simple-ai"}, {"name": "Other", "slug": "acme"}]
    data = [co("Simple AI", slug="simple-ai-2"), co("Acme Labs", slug="acme"), co("New Co", slug="new-co")]
    assert [e["name"] for e in yc.new_entries(data, existing)] == ["New Co"]


def test_hq_from_regions():
    assert yc.hq(co("A", regions=("India", "South Asia"))) == "in"
    assert yc.hq(co("B", regions=("Germany", "Europe"))) == "eu"
    assert yc.hq(co("C", regions=("Unspecified",))) == "global"


def test_appended_section_parses_and_entries_start_unverified():
    text = "companies:\n  - {name: X, category: lab, hq: us, ats: ashby, slug: x, verified: true}\n"
    out = yc.append_section(text, yc.new_entries([co("New Co", slug="new-co")], []), "2026-10-06")
    rows = yaml.safe_load(out)["companies"]
    assert rows[-1] == {"name": "New Co", "category": "yc", "hq": "us", "ats": "ashby", "slug": "new-co",
                        "verified": False}
