import yaml

import discover_companies as dc
from verify_companies import Board


def post(pid, text):
    return {"id": pid, "text": text, "created_at": "2026-10-01T16:00:00.000Z"}


def test_board_links_reads_escaped_hn_html():
    text = ('Acme AI | ML Engineer | Remote<p>Apply: <a href="https:&#x2F;&#x2F;jobs.ashbyhq.com&#x2F;acme-ai">'
            'https:&#x2F;&#x2F;jobs.ashbyhq.com&#x2F;acme-ai</a> or jobs.lever.co/acme')
    assert dc.board_links(text) == [("ashby", "acme-ai"), ("lever", "acme")]


def test_board_links_formats_workday_and_skips_ui_paths():
    text = ("https://foo.wd5.myworkdayjobs.com/en-US/External_Careers/job/x "
            "https://boards.greenhouse.io/embed/job_board?for=bar https://apply.workable.com/j/ABC123 "
            "https://jobs.eu.lever.co/eurco")
    assert dc.board_links(text) == [("workday", "foo/wd5/External_Careers"), ("greenhouse", "bar")]


def test_hn_candidates_take_the_header_name_and_first_board():
    thread = {"children": [
        post(1, "Acme AI (https://acme.ai) | ML Engineer | Bangalore<p>https://jobs.lever.co/acme"),
        post(2, "No board here | Engineer | Remote<p>email me"),
        post(3, "a reply with jobs.lever.co/x but no header"),
    ]}
    assert dc.hn_candidates([thread]) == [
        {"name": "Acme AI", "category": "hn", "hq": "global", "ats": "lever", "slug": "acme"}]


def test_dedupe_drops_known_names_boards_and_repeats():
    existing = [{"name": "Acme AI", "ats": "lever", "slug": "acme"}, {"name": "Other", "ats": "ashby", "slug": "Taken"}]
    cands = [
        {"name": "ACME ai", "ats": "ashby", "slug": "x"},
        {"name": "Renamed", "ats": "ashby", "slug": "taken"},
        {"name": "New Co", "ats": "lever", "slug": "newco"},
        {"name": "New Co", "ats": "greenhouse", "slug": "newco"},
    ]
    assert [c["name"] for c in dc.dedupe(cands, existing)] == ["New Co"]


def test_qualify_keeps_only_boards_with_target_titles(monkeypatch):
    boards = {"good": Board("lever", "good", ["Sales Lead", "ML Engineer"]),
              "sales": Board("lever", "sales", ["Account Executive"]),
              "none": None}
    monkeypatch.setattr(dc, "find_board", lambda get, c, http: boards[c["slug"]])
    http = type("Http", (), {"get_json": None})()

    def cand(slug):
        return {"name": slug, "category": "hn", "hq": "global", "ats": "ashby", "slug": slug}

    good = dc.qualify(http, cand("good"), "2026-10-07")
    assert good == {"name": "good", "category": "hn", "hq": "global", "ats": "lever", "slug": "good",
                    "verified": True, "jobs": 2, "ai_jobs": 1, "checked": "2026-10-07"}
    assert dc.qualify(http, cand("sales"), "2026-10-07") is None
    assert dc.qualify(http, cand("none"), "2026-10-07") is None


def test_pick_and_append_section_round_trip():
    found = [{"name": n, "category": "yc", "hq": "us", "ats": "ashby", "slug": n.lower(), "verified": True,
              "jobs": j, "ai_jobs": a, "checked": "2026-10-07"} for n, j, a in [("B", 5, 1), ("A", 9, 3), ("C", 2, 1)]]
    batch = dc.pick(found, 2)
    assert [c["name"] for c in batch] == ["A", "B"]
    text = "companies:\n  - {name: Old, category: lab, hq: us, ats: lever, slug: old}\n"
    out = yaml.safe_load(dc.append_section(text, batch, "2026-10-07"))["companies"]
    assert [c["name"] for c in out] == ["Old", "A", "B"]
    assert out[1]["verified"] is True and out[1]["jobs"] == 9
    assert "| A | yc | ashby | `a` | 9 | 3 |" in dc.pr_body(batch)


def test_yc_candidates_leave_verification_to_the_probe():
    data = [{"name": "Neo", "slug": "neo", "tags": ["AI"], "batch": "Fall 2026", "team_size": 12,
             "regions": ["India"], "status": "Active", "isHiring": True}]
    assert dc.yc_candidates(data, []) == [{"name": "Neo", "category": "yc", "hq": "in", "ats": "ashby", "slug": "neo"}]


def test_title_fits_uses_the_role_title_rules():
    assert dc.title_fits("Machine Learning Engineer")
    assert dc.title_fits("Android Developer")
    assert dc.title_fits("Backend Engineer (Python)")
    assert not dc.title_fits("Software Engineer")  # needs a description to qualify
    assert not dc.title_fits("Propulsion Engineer")
    assert not dc.title_fits("Account Executive")


def test_hn_header_name_falls_back_to_the_board_slug():
    thread = {"children": [post(1, "NYC | Founding Engineer | Onsite<p>https://jobs.ashbyhq.com/norm-ai")]}
    assert dc.hn_candidates([thread])[0]["name"] == "Norm Ai"
