"""Supabase publisher: repost matching and id resolution (the SQL is run against a local
Postgres by hand; see the PR)."""

import publish_pg as p

TEXT = " ".join(f"word{i}" for i in range(200))  # a long, distinctive description


def row(id_, text=TEXT, posted="2026-10-01T00:00:00Z", title="SDE Fresher", company="A", loc="Pune"):
    return {"id": id_, "description_text": text, "posted_at": posted,
            "repost_key": p.repost_key(company, title, loc)}


def test_repost_key_ignores_case_spacing_and_punctuation():
    assert p.repost_key("Acme", "SDE - Fresher", "Pune, India") == p.repost_key("acme ", "sde fresher", "pune india")
    assert p.repost_key("Acme", "SDE Fresher", "Pune") != p.repost_key("Acme", "SDE Fresher", "Delhi")


def test_same_posting_needs_near_identical_text():
    assert p.same_posting(TEXT, TEXT + " apply now")
    assert not p.same_posting(TEXT, " ".join(f"other{i}" for i in range(200)))
    assert not p.same_posting("", "")  # no evidence, no merge


def test_new_listing_of_a_stored_job_merges_into_it():
    new = row("ashby:a:2", posted="2026-10-16T00:00:00Z")
    targets, aliases = p.resolve([new], known={"ashby:a:1"}, aliases={},
                                 candidates={new["repost_key"]: [("ashby:a:1", TEXT)]})
    assert aliases == {"ashby:a:2": "ashby:a:1"} and targets == {"ashby:a:1": new}


def test_different_text_under_the_same_title_stays_a_separate_job():
    new = row("ashby:a:2", text=" ".join(f"batch2_{i}" for i in range(200)))
    targets, aliases = p.resolve([new], known={"ashby:a:1"}, aliases={},
                                 candidates={new["repost_key"]: [("ashby:a:1", TEXT)]})
    assert aliases == {} and set(targets) == {"ashby:a:2"}


def test_known_alias_and_both_listings_live_keep_one_job_with_the_newer_date():
    old, new = row("ashby:a:1", posted="2026-09-16T00:00:00Z"), row("ashby:a:2", posted="2026-10-16T00:00:00Z")
    targets, aliases = p.resolve([old, new], known={"ashby:a:1"}, aliases={"ashby:a:2": "ashby:a:1"}, candidates={})
    assert aliases == {} and targets == {"ashby:a:1": new}


def test_board_prefixes_match_only_that_boards_ids():
    prefixes = p.board_prefixes([{"source": "lever", "company_slug": "acme"}])
    assert "lever:acme:123".startswith(prefixes) and not "lever:acme2:1".startswith(prefixes)
