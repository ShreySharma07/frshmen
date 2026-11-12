import verify_companies as vc
from sources.http import FetchError


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


def test_not_found_is_rechecked_weekly():
    from datetime import date
    c = {"name": "A", "verified": False, "checked": "2026-10-06"}
    assert not vc.needs_check(c, today=date(2026, 10, 10))
    assert vc.needs_check(c, today=date(2026, 10, 13))


def test_slug_variants_include_parenthetical_name():
    assert "cursor" in vc.slug_variants({"name": "Anysphere (Cursor)", "slug": "anysphere"})


def test_throttled_host_does_not_hide_board_elsewhere():
    def get(url):
        if "lever" in url:
            raise FetchError("api.lever.co: HTTP 429")
        if url == "https://api.ashbyhq.com/posting-api/job-board/acme":
            return {"jobs": [{"title": "ML Engineer", "jobUrl": "u"}]}
        return None

    assert vc.find_board(get, {"name": "Acme", "ats": "lever", "slug": "acme"}).ats == "ashby"


def test_unanswered_probes_are_not_reported_as_not_found():
    def get(url):
        if "smartrecruiters" in url:
            raise FetchError("api.smartrecruiters.com: HTTP 429")
        return None

    try:
        vc.find_board(get, {"name": "Acme", "ats": "ashby", "slug": "acme"})
    except FetchError as e:
        assert "smartrecruiters" in str(e)
    else:
        raise AssertionError("expected FetchError")


def test_workable_only_probed_when_guessed():
    get, calls = fake_get({})
    vc.find_board(get, {"name": "Acme", "ats": "ashby", "slug": "acme"})
    assert not any("workable" in u for u in calls)

    get, calls = fake_get({"https://apply.workable.com/api/v1/widget/accounts/acme": {"name": "Acme", "jobs": [{"title": "ML", "url": "u"}]}})
    assert vc.find_board(get, {"name": "Acme", "ats": "workable", "slug": "acme"}).ats == "workable"


def test_careers_site_systems_use_the_exact_slug_only():
    class Http:
        requested = []

        def post_json(self, url, body):
            return None  # search unusable: the sitemap is the fallback

        def get_text(self, url):
            self.requested.append(url)
            return ('<urlset><url><loc>https://acme.wd1.myworkdayjobs.com/Careers/job/Pune/ML-Engineer_R1</loc>'
                    '</url></urlset>')

    http = Http()
    board = vc.find_board(lambda url: None, {"name": "Acme", "ats": "workday", "slug": "acme/wd1/Careers"}, http)
    assert (board.ats, board.slug, board.titles) == ("workday", "acme/wd1/Careers", ["ML Engineer"])
    assert http.requested == ["https://acme.wd1.myworkdayjobs.com/Careers/siteMap.xml"]


def test_careers_site_403_counts_as_checked_not_an_error():
    from sources.http import FetchError

    class Http:
        def get_json(self, url):
            raise FetchError("zepto.darwinbox.in: HTTP 403")

    assert vc.find_board(lambda url: None, {"name": "Zepto", "ats": "darwinbox", "slug": "zepto"}, Http()) is None


def test_companies_added_with_only_a_website_wait_for_detection(tmp_path, monkeypatch):
    cfg = tmp_path / "companies.yaml"
    cfg.write_text("companies:\n"
                   "  - {name: Acme, category: mnc, hq: us, website: acme.com, india_only: true}\n"
                   "  - {name: Beta, category: lab, hq: us, ats: ashby, slug: beta}\n")
    probed = []
    monkeypatch.setattr(vc, "ROOT", tmp_path)
    monkeypatch.setattr(vc, "COMPANIES", cfg)
    monkeypatch.setattr(vc, "REPORT", tmp_path / "report.md")
    monkeypatch.setattr(vc, "find_board", lambda get, company, http=None: probed.append(company["name"]))
    monkeypatch.setattr("sys.argv", ["verify_companies.py"])
    vc.main()
    assert probed == ["Beta"]
    assert "| Acme | mnc | not checked yet |" in (tmp_path / "report.md").read_text()


# --- Wrong-company matches (2026-11-12): a board that answers to the name isn't proof it is theirs.

GH = "https://boards-api.greenhouse.io/v1/boards/"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/"
LEVER = "https://api.lever.co/v0/postings/{}?mode=json"
SR = "https://api.smartrecruiters.com/v1/companies/{}/postings"

# Shapes of the two boards that were taken for Indian companies of the same name.
CLEAR_US = {
    GH + "clear/jobs": {"jobs": [{"title": "Airport Ambassador", "absolute_url": "https://www.clearme.com/careers?gh_jid=1"}]},
    GH + "clear": {"name": "CLEAR - Corporate", "content": "<p>Identity for airports and stadiums.</p>"},
}
APOLLO_OTHER = {
    ASHBY + "apollo": {"jobs": [{"title": "Account Executive", "jobUrl": "https://jobs.ashbyhq.com/apollo/1",
                                 "descriptionHtml": "<p>Join the sales platform used by millions.</p>"}]},
}


def test_board_named_for_another_company_is_rejected():
    get, _ = fake_get(CLEAR_US)
    company = {"name": "Clear", "website": "clear.in", "ats": "greenhouse", "slug": "clear"}
    assert vc.find_board(get, company) is None


def test_board_named_for_another_company_is_rejected_without_a_website_too():
    get, _ = fake_get(CLEAR_US)
    assert vc.find_board(get, {"name": "Clear", "ats": "greenhouse", "slug": "clear"}) is None


def test_nameless_board_on_a_slug_shorter_than_the_website_is_rejected():
    get, _ = fake_get(APOLLO_OTHER)
    company = {"name": "Apollo", "website": "apollofirst.xyz", "ats": "ashby", "slug": "apollo"}
    assert vc.find_board(get, company) is None


def test_wrong_company_board_is_rejected_even_when_empty():
    # An empty board is kept as a fallback and marked verified; it would fill with the other company's jobs.
    get, _ = fake_get({ASHBY + "apollo": {"jobs": []}})
    company = {"name": "Apollo", "website": "apollofirst.xyz", "ats": "ashby", "slug": "apollo"}
    assert vc.find_board(get, company) is None


def test_nameless_board_whose_slug_is_the_website_name_is_accepted():
    get, _ = fake_get({LEVER.format("fampay"): [{"text": "Backend Engineer", "hostedUrl": "https://jobs.lever.co/fampay/1"}]})
    board = vc.find_board(get, {"name": "FamPay", "website": "fampay.in", "ats": "ashby", "slug": "fampay"})
    assert (board.ats, board.slug) == ("lever", "fampay")


def test_board_with_the_same_name_is_accepted():
    get, _ = fake_get({SR.format("lokal"): {"content": [{"id": "7", "name": "ML Engineer", "company": {"name": "Lokal"}}]}})
    board = vc.find_board(get, {"name": "Lokal", "ats": "ashby", "slug": "lokal"})
    assert (board.ats, board.slug, board.board_name) == ("smartrecruiters", "lokal", "Lokal")


def test_same_name_is_enough_when_the_website_is_spelled_differently():
    get, _ = fake_get({SR.format("lokal"): {"content": [{"id": "7", "name": "ML Engineer", "company": {"name": "Lokal"}}]}})
    company = {"name": "Lokal", "website": "getlokalapp.example", "ats": "smartrecruiters", "slug": "lokal"}
    assert vc.find_board(get, company).slug == "lokal"


def test_company_suffixes_and_spacing_do_not_make_a_different_name():
    for entry, board_name in [("Piramidal", "Piramidal, Inc."), ("OpenAI", "Open AI"), ("Sarvam AI", "Sarvam"),
                              ("Anysphere (Cursor)", "Cursor"), ("Observe.AI", "Observe.AI Careers"),
                              ("Rubrik", "Rubrik Job Board")]:
        assert vc.same_name(entry, board_name), (entry, board_name)
    for entry, board_name in [("Clear", "CLEAR - Corporate"), ("Apollo", "Apollo Global Management"),
                              ("Clear", "ClearTax"), ("Moveworks", "ServiceNow")]:
        assert not vc.same_name(entry, board_name), (entry, board_name)


def test_board_that_mentions_the_company_website_is_accepted():
    # Whatever the slug or board name, a link or address on the company's own domain ties the board to it.
    get, _ = fake_get({
        GH + "clear/jobs": {"jobs": [{"title": "SDE 1", "absolute_url": "https://www.clear.in/careers?gh_jid=9"}]},
        GH + "clear": {"name": "Defmacro Software", "content": None},
        ASHBY + "apollo": {"jobs": [{"title": "Founding Engineer", "jobUrl": "https://jobs.ashbyhq.com/apollo/2",
                                     "descriptionHtml": "<p>Write to jobs@apollofirst.xyz</p>"}]},
    })
    assert vc.find_board(get, {"name": "Clear", "website": "https://www.clear.in/", "ats": "greenhouse", "slug": "clear"}).slug == "clear"
    assert vc.find_board(get, {"name": "Apollo", "website": "apollofirst.xyz", "ats": "ashby", "slug": "apollo"}).slug == "apollo"


def test_a_longer_domain_is_not_a_mention_of_the_website():
    get, _ = fake_get({ASHBY + "apollo": {"jobs": [{"title": "AE", "jobUrl": "u", "descriptionHtml": "see notapollofirst.xyz and apollofirst.xyz.example.com"}]}})
    assert vc.find_board(get, {"name": "Apollo", "website": "apollofirst.xyz", "ats": "ashby", "slug": "apollo"}) is None


def test_board_the_careers_detector_found_on_the_company_site_is_trusted():
    get, _ = fake_get(APOLLO_OTHER)
    company = {"name": "Apollo", "website": "apollofirst.xyz", "ats": "ashby", "slug": "apollo",
               "careers": "ashby: https://apollofirst.xyz/careers"}
    assert vc.find_board(get, company).slug == "apollo"
    # ...but only that board: a note about a different system or an unreadable one confirms nothing.
    for note in ("greenhouse: https://apollofirst.xyz/careers", "not found (6 pages read)"):
        assert vc.find_board(get, dict(company, careers=note)) is None


def test_website_names_with_a_stock_prefix_or_suffix_still_match_the_slug():
    for website, slug in [("thinkingmachineslab.ai", "thinkingmachines"), ("getacme.com", "acme"),
                          ("essential.ai", "essentialai"), ("acme.co.in", "acme-labs")]:
        get, _ = fake_get({ASHBY + slug: {"jobs": [{"title": "ML Engineer", "jobUrl": "u"}]}})
        assert vc.find_board(get, {"name": "X", "website": website, "ats": "ashby", "slug": slug}), (website, slug)


def test_rejected_board_does_not_stop_the_search():
    get, _ = fake_get(dict(CLEAR_US, **{SR.format("clear"): {"content": [{"id": "3", "name": "SDE 1", "company": {"name": "Clear"}}]}}))
    board = vc.find_board(get, {"name": "Clear", "website": "clear.in", "ats": "greenhouse", "slug": "clear"})
    assert (board.ats, board.slug) == ("smartrecruiters", "clear")
