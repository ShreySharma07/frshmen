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


def test_empty_board_does_not_stop_search_for_one_with_jobs():
    get, _ = fake_get({
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs": {"jobs": []},
        "https://boards-api.greenhouse.io/v1/boards/acme": {"name": "Acme"},
        "https://api.ashbyhq.com/posting-api/job-board/acme": {"jobs": [{"title": "AI Engineer", "jobUrl": "u"}]},
    })
    board = vc.find_board(get, {"name": "Acme", "ats": "greenhouse", "slug": "acme"})
    assert (board.ats, len(board.titles)) == ("ashby", 1)


def test_empty_board_is_fallback_when_nothing_has_jobs():
    get, _ = fake_get({"https://api.lever.co/v0/postings/acme?mode=json": []})
    board = vc.find_board(get, {"name": "Acme", "ats": "ashby", "slug": "acme"})
    assert (board.ats, board.titles) == ("lever", [])


def test_empty_workable_account_is_not_a_match():
    get, _ = fake_get({"https://apply.workable.com/api/v1/widget/accounts/acme": {"name": "Acme", "jobs": []}})
    assert vc.find_board(get, {"name": "Acme", "ats": "workable", "slug": "acme"}) is None


def test_needs_check():
    assert vc.needs_check({"name": "A"})
    assert vc.needs_check({"name": "A", "verified": False})
    assert vc.needs_check({"name": "A", "verified": True, "jobs": 0})
    assert not vc.needs_check({"name": "A", "verified": True, "jobs": 3})


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return self.body


def test_fetcher_backs_off_on_429_then_succeeds(monkeypatch):
    import io
    import urllib.error

    sleeps = []
    responses = [
        urllib.error.HTTPError("u", 429, "Too Many", {"Retry-After": "7"}, io.BytesIO()),
        _Resp(b'{"jobs": []}'),
    ]

    def urlopen(req, timeout):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(vc.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(vc.time, "sleep", sleeps.append)
    assert vc.Fetcher().get_json("https://api.ashbyhq.com/x") == {"jobs": []}
    assert 7.0 in sleeps


def test_fetcher_gives_up_with_runtime_error(monkeypatch):
    import io
    import urllib.error

    def urlopen(req, timeout):
        raise urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO())

    monkeypatch.setattr(vc.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)
    try:
        vc.Fetcher().get_json("https://api.lever.co/x")
    except RuntimeError as e:
        assert "api.lever.co: HTTP 429" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
