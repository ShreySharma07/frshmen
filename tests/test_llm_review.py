import json
from datetime import datetime, timezone

import pytest

import llm_review
from extract import llm
from extract.classify import classify

NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
DESC = ("We are building agents for finance teams. You will ship Python services and evals. "
        "Recent graduates and freshers are encouraged to apply. "
        "You should have 3+ years of experience building production ML systems.")


def answer(lo=None, hi=None, fresher=False, quote="Recent graduates and freshers are encouraged to apply."):
    return json.dumps({"yoe_required_min": lo, "yoe_required_max": hi, "fresher_friendly": fresher,
                       "evidence_quote": quote})


def record(level="maybe", reason=llm.NO_MENTION_REASON, yoe_min=None, desc=DESC, **kw):
    base = {"id": "x", "title": "AI Engineer", "description_text": desc, "content_hash": "h1", "level": level,
            "level_confidence": 0.5, "reason": reason, "yoe_min": yoe_min, "yoe_max": None, "yoe_evidence": None,
            "evidence": [], "role_match": True, "eligible": True, "posted_at": "2026-10-01T00:00:00Z"}
    return {**base, **kw}


def test_parse_rejects_a_quote_not_in_the_posting():
    assert llm.parse(answer(quote="Freshers from any background are welcome here."), DESC) is None
    assert llm.parse(answer(quote="Python"), DESC) is None  # too short to prove anything
    assert llm.parse("not json", DESC) is None


def test_parse_accepts_whitespace_and_case_differences():
    v = llm.parse(answer(fresher=True, quote="recent  graduates and FRESHERS are encouraged to apply."), DESC)
    assert v is not None and v.fresher_friendly is True


def test_parse_drops_nonsense_numbers():
    v = llm.parse(answer(lo=-1, hi=99), DESC)
    assert v.yoe_min is None and v.yoe_max is None
    assert llm.parse(answer(lo=3, hi=1), DESC).yoe_max is None


def test_two_plus_years_makes_it_experienced_and_raises_yoe():
    v = llm.parse(answer(lo=3, quote="You should have 3+ years of experience building production ML systems."), DESC)
    out = llm.apply(record(), v)
    assert out["level"] == "experienced" and out["yoe_min"] == 3
    assert out["evidence"][-1] == {"kind": "llm", "snippet": v.quote}


def test_fresher_only_when_the_rules_found_no_experience_mention():
    v = llm.parse(answer(fresher=True), DESC)
    assert llm.apply(record(), v)["level"] == "fresher"
    # The rules found a requirement ("1+ years"): the LLM may not override it.
    assert llm.apply(record(reason="requires 1+ years", yoe_min=1.0), v)["level"] == "maybe"
    assert llm.apply(record(reason="only preferred experience stated"), v)["level"] == "maybe"


def test_fresher_needs_at_most_one_year():
    v = llm.parse(answer(lo=0, hi=2, fresher=True), DESC)
    out = llm.apply(record(), v)
    assert out["level"] == "maybe" and out["yoe_min"] == 0 and out["yoe_max"] == 2


def test_stored_minimum_is_only_raised():
    v = llm.parse(answer(lo=0, hi=1), DESC)
    assert llm.apply(record(reason="requires 1+ years", yoe_min=1.0), v)["yoe_min"] == 1.0


def test_llm_never_makes_a_two_year_posting_fresher():
    # CLAUDE.md: never `fresher` when an explicit 2+ year requirement exists. The rules settle it
    # before the LLM is asked, so the job never reaches review.
    rules = classify("Associate ML Engineer", DESC).to_dict()
    assert rules["level"] == "experienced"
    assert not llm.needs_review({**rules, "description_text": DESC})


class FakeModel:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt, schema):
        self.prompts.append(prompt)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def test_run_reviews_only_shown_maybe_jobs_and_caches():
    recs = [record(id="a", content_hash="a"),
            record(id="b", content_hash="b", level="fresher"),
            record(id="c", content_hash="c", eligible=False),
            record(id="d", content_hash="d", posted_at="2026-08-01T00:00:00Z")]
    model, cache = FakeModel(answer(fresher=True)), {}
    out, stats = llm_review.run(recs, model, cache, max_calls=10, now=NOW)
    assert len(model.prompts) == 1 and stats["asked"] == 1 and stats["changed_level"] == 1
    assert out[0]["level"] == "fresher" and out[1:] == recs[1:]

    # Second run: served from the cache, no request.
    out2, stats2 = llm_review.run(recs, FakeModel(), cache, max_calls=10, now=NOW)
    assert stats2["cached"] == 1 and stats2["asked"] == 0 and out2[0]["level"] == "fresher"


def test_run_caches_rejected_answers_and_stops_on_quota():
    recs = [record(id=i, content_hash=i, posted_at=f"2026-10-0{n}T00:00:00Z") for n, i in [(3, "a"), (2, "b"), (1, "c")]]
    model, cache = FakeModel(answer(quote="This sentence is not in the posting at all."),
                             llm_review.QuotaExhausted("HTTP 429")), {}
    out, stats = llm_review.run(recs, model, cache, max_calls=10, now=NOW)
    assert stats["asked"] == 1 and stats["accepted"] == 0
    assert cache == {f"v{llm.PROMPT_VERSION}:a": None}  # "b" hit the quota; "c" never asked
    assert out == recs


def test_run_respects_the_call_cap():
    recs = [record(id=i, content_hash=i) for i in "abc"]
    model = FakeModel(answer(), answer())
    _, stats = llm_review.run(recs, model, {}, max_calls=2, now=NOW)
    assert stats["asked"] == 2


@pytest.mark.parametrize("posted,expected", [(None, True), ("2026-09-10T00:00:00Z", True), ("2026-09-01T00:00:00Z", False)])
def test_shown_uses_the_page_age_window(posted, expected):
    assert llm_review.shown(record(posted_at=posted), NOW) is expected


def test_failed_calls_are_not_cached_and_stop_after_a_streak():
    recs = [record(id=i, content_hash=i) for i in "abcde"]
    fail = llm_review.CallFailed("HTTP 500")
    model, cache = FakeModel(fail, fail, fail), {}
    out, stats = llm_review.run(recs, model, cache, max_calls=10, now=NOW)
    assert stats["failed"] == llm_review.MAX_FAILURES and stats["asked"] == 0
    assert cache == {} and out == recs  # retried next run, labels untouched


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_gemini_call_falls_back_to_the_next_model_on_404(monkeypatch):
    import io
    import urllib.error

    seen = []

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        assert "key=" not in req.full_url and req.get_header("X-goog-api-key") == "k"
        if "old-model" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {},
                                         io.BytesIO(b'{"error": {"message": "model not found"}}'))
        return FakeResponse({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    monkeypatch.setattr(llm_review.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_review, "PACE_SECONDS", 0)
    call = llm_review.gemini_call("k", ["old-model", "new-model"])
    assert call("p", {}) == "{}" and call("p", {}) == "{}"
    assert [u.split("/models/")[1].split(":")[0] for u in seen] == ["old-model", "new-model", "new-model"]
    assert call.models == ["new-model"]


def test_gemini_call_with_no_model_left_stops_the_run(monkeypatch):
    import io
    import urllib.error

    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(llm_review.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_review, "PACE_SECONDS", 0)
    with pytest.raises(llm_review.QuotaExhausted):
        llm_review.gemini_call("k", ["a", "b"])("p", {})
