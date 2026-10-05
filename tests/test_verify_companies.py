import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import verify_companies as vc  # noqa: E402


def fake_get(responses):
    calls = []

    def get(url):
        calls.append(url)
        return responses.get(url)

    return get, calls


def test_guessed_board_is_tried_first_and_wins():
    get, calls = fake_get({
        "https://api.ashbyhq.com/posting-api/job-board/openai": {"jobs": [{"title": "ML Engineer", "jobUrl": "u"}]},
    })
    board = vc.find_board(get, {"name": "OpenAI", "ats": "ashby", "slug": "openai"})
    assert (board.ats, board.slug, board.titles) == ("ashby", "openai", ["ML Engineer"])
    assert len(calls) == 1


def test_wrong_ats_guess_falls_back_to_other_ats():
    get, _ = fake_get({"https://api.lever.co/v0/postings/acme?mode=json": [{"text": "AI Engineer", "hostedUrl": "h"}]})
    board = vc.find_board(get, {"name": "Acme", "ats": "ashby", "slug": "acme"})
    assert (board.ats, board.slug) == ("lever", "acme")


def test_slug_variant_from_name():
    get, _ = fake_get({"https://api.ashbyhq.com/posting-api/job-board/scale-ai": {"jobs": []}})
    board = vc.find_board(get, {"name": "Scale AI", "ats": "ashby", "slug": "wrong"})
    assert (board.ats, board.slug, board.titles) == ("ashby", "scale-ai", [])


def test_empty_smartrecruiters_is_not_a_match():
    get, _ = fake_get({"https://api.smartrecruiters.com/v1/companies/x/postings": {"content": []}})
    assert vc.find_board(get, {"name": "X", "ats": "smartrecruiters", "slug": "x"}) is None


def test_rewrite_keeps_comments_and_updates_only_checked_lines():
    text = "# header\ncompanies:\n  # group\n  - {name: A, category: lab, hq: us, ats: ashby, slug: a}\n  - {name: B, category: lab, hq: us, ats: lever, slug: b}\n"
    out = vc.rewrite_yaml(text, {"A": {"name": "A", "category": "lab", "hq": "us", "ats": "lever", "slug": "a2",
                                        "verified": True, "jobs": 3, "ai_jobs": 1}})
    assert out.startswith("# header\ncompanies:\n  # group\n")
    assert "  - {name: A, category: lab, hq: us, ats: lever, slug: a2, verified: true, jobs: 3, ai_jobs: 1}\n" in out
    assert "  - {name: B, category: lab, hq: us, ats: lever, slug: b}\n" in out


def test_real_config_round_trips_unchanged():
    text = vc.COMPANIES.read_text()
    import yaml
    companies = {c["name"]: c for c in yaml.safe_load(text)["companies"]}
    assert vc.rewrite_yaml(text, companies) == text
