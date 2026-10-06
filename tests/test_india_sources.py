"""Workday, Darwinbox, Keka and Zoho Recruit adapters.

Workday, Darwinbox and Keka fixtures are real responses (fetched 2026-10-06),
trimmed; the Darwinbox entries' titles/department were edited to exercise the
title screen. The Zoho page is synthetic, in the documented shape, until a live
page is captured.
"""

import json
from pathlib import Path

from extract.location import extract_location
from sources import ADAPTERS, darwinbox, keka, workday, zoho_recruit
from sources.models import Company
from sources.prefilter import could_be_target, experience_line

FIX = Path(__file__).parent / "fixtures" / "sources"


class FakeHttp:
    """Serves fixtures by URL and records what was requested."""

    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def get_json(self, url):
        self.requested.append(url)
        body = self.routes.get(url)
        return json.loads(body) if isinstance(body, str) else body

    def get_text(self, url):
        self.requested.append(url)
        return self.routes.get(url)


def text(name):
    return (FIX / name).read_text()


def test_new_adapters_are_registered():
    assert {"workday", "darwinbox", "keka", "zoho_recruit"} <= set(ADAPTERS)


def test_title_screen_and_experience_line():
    assert could_be_target("ML Engineer") and could_be_target("Data Scientist II")
    assert not could_be_target("Senior Lead - Strategy") and not could_be_target("Account Manager")
    assert experience_line("3-5") == "Experience: 3-5 years"
    assert experience_line("2 - 5 Years") == "Experience: 2 - 5 Years"
    assert experience_line("Fresher") == "Experience: Fresher"
    assert experience_line("") == "" and experience_line("Negotiable") == ""


# --- Workday -------------------------------------------------------------------

BS = Company("BrowserStack", "workday", "browserstack/wd3/External")


def test_workday_titles_from_sitemap_paths():
    paths = workday.job_paths(text("workday_browserstack_sitemap.xml"), "External")
    assert paths[0] == "/job/India-Remote/Engineering-Manager_JR103661"
    assert [workday.title_from_path(p) for p in paths] == [
        "Engineering Manager", "Senior Lead   Strategy", "Engineer   Datacenter Operations",
        "Senior Associate   Strategy   Operations"]


def test_workday_fetch_only_requests_details_for_possible_targets():
    detail = workday.detail_url(BS.slug, "/job/India-Remote/Engineering-Manager_JR103661")
    assert detail == ("https://browserstack.wd3.myworkdayjobs.com/wday/cxs/browserstack/External"
                      "/job/India-Remote/Engineering-Manager_JR103661")
    http = FakeHttp({workday.sitemap_url(BS.slug): text("workday_browserstack_sitemap.xml"),
                     detail: text("workday_browserstack_detail.json")})
    jobs = workday.fetch(http, BS)
    # Strategy/operations titles are screened out before any detail request.
    assert not any("Strategy" in u for u in http.requested)
    job = jobs[0]
    assert (job.title, job.external_id, job.location_raw, job.posted_at) == (
        "Engineering Manager", "JR103661", "India Remote", "2026-10-05T00:00:00Z")
    assert job.ats_countries == ["India"] and "8-12 years" in job.description_text
    assert job.url.endswith("/External/job/India-Remote/Engineering-Manager_JR103661")


def test_workday_missing_sitemap_is_not_a_board():
    assert workday.list_titles(FakeHttp({}), BS.slug) is None


# --- Darwinbox -----------------------------------------------------------------

ZEPTO = Company("Zepto", "darwinbox", "zepto")


def test_darwinbox_fetch_merges_list_and_detail_and_keeps_experience_as_text():
    http = FakeHttp({darwinbox.list_url("zepto", 1): text("darwinbox_spinzone_list.json"),
                     darwinbox.detail_url("zepto", "a6abcb9fe0cca8"): text("darwinbox_zepto_detail.json")})
    jobs = darwinbox.fetch(http, ZEPTO)
    assert [j.title for j in jobs] == ["Data Scientist II"]  # "City Supply Head" screened out
    job = jobs[0]
    assert job.description_text.startswith("Experience: 2 - 5 Years")
    assert "Python" in job.description_text
    assert job.location_raw == "Bengaluru, Karnataka, India"
    assert job.posted_at == "2026-10-04T18:30:00Z"  # unix seconds: midnight IST on Oct 5
    assert job.url == "https://zepto.darwinbox.in/ms/candidatev2/main/careers/jobDetails/a6abcb9fe0cca8"
    assert extract_location(job.location_raw).cities == ["Bengaluru"]


def test_darwinbox_pages_until_jobscount():
    page = lambda ids, total: {"status": "success", "message": {"jobscount": total, "jobs": [{"id": i, "title": "x"} for i in ids]}}
    http = FakeHttp({darwinbox.list_url("acme", 1): page(["a", "b"], 3), darwinbox.list_url("acme", 2): page(["c"], 3)})
    assert darwinbox.list_titles(http, "acme") == ["x", "x", "x"]


def test_darwinbox_full_host_slug():
    assert darwinbox.host("straive.darwinbox.com") == "straive.darwinbox.com"
    assert darwinbox.host("zepto") == "zepto.darwinbox.in"


def test_darwinbox_falls_back_to_list_experience_when_detail_failed():
    item = json.loads(text("darwinbox_spinzone_list.json"))["message"]["jobs"][1]
    job = darwinbox.parse(item, {}, ZEPTO)
    assert job.description_text == "Experience: 2 - 5 Years"


# --- Keka ----------------------------------------------------------------------

JUPITER = Company("Jupiter", "keka", "jupiter/b5279857-cf81-4dde-a215-fc48957ee2b5")


def test_keka_parse():
    jobs = keka.parse(json.loads(text("keka_jupiter.json")), JUPITER)
    devops, support = jobs
    assert devops.url == "https://jupiter.keka.com/careers/jobdetails/134831"
    assert devops.location_raw == "Bengaluru, India" and devops.ats_countries == ["IN"]
    assert devops.description_text.startswith("Experience: 3-5 years")
    assert support.description_text.startswith("Experience: 0-1 years")
    assert devops.posted_at == "2026-07-15T07:26:49Z"


def test_keka_reads_portal_guid_from_careers_page_when_slug_has_none():
    guid = "b5279857-cf81-4dde-a215-fc48957ee2b5"
    page = f'<script src="https://jupiter.keka.com/careers/api/embedjobs/js/{guid}"></script>'
    http = FakeHttp({"https://jupiter.keka.com/careers/": page,
                     keka.list_url("jupiter", guid): text("keka_jupiter.json")})
    assert keka.list_titles(http, "jupiter") == ["Devops Engineer - SDE 2", "Customer support executive"]


# --- Zoho Recruit --------------------------------------------------------------

WADHWANI = Company("Wadhwani AI", "zoho_recruit", "wadhwaniai.zohorecruit.in")


def test_zoho_reads_jobs_embedded_in_careers_page():
    jobs = zoho_recruit.parse(zoho_recruit.embedded_jobs(text("zoho_recruit_synthetic.html")), WADHWANI)
    ml, pm = jobs
    assert ml.title == "Machine Learning Engineer" and ml.location_raw == "New Delhi, Delhi, India"
    assert ml.url == "https://wadhwaniai.zohorecruit.in/jobs/Careers/2000001/Machine-Learning-Engineer"
    assert ml.description_text.startswith("Experience: 0-1 year")
    assert pm.location_raw == "Remote" and pm.ats_workplace_type == "remote"


def test_zoho_page_without_jobs_is_not_a_board():
    assert zoho_recruit.embedded_jobs("<html></html>") is None


def test_zoho_job_page_record_is_decoded_from_its_js_string():
    # Shape seen live on a Wadhwani AI job page: a JS single-quoted literal with \\x22 quotes.
    record = '[{"id":"146520000003734311","Job_Description":"<p>Python, 0-1 years</p>","Work_Experience":"Fresher","Date_Opened":"2026-02-26","State":"Delhi","Publish":true}]'
    literal = record.replace('"', "\\x22").replace("-", "\\-").replace("/", "\\/")
    page = f"<script>var jobs = JSON.parse('{literal}');\nvar page_id = '1';</script>"
    row = zoho_recruit.job_record(page, "146520000003734311")
    assert row["Work_Experience"] == "Fresher" and row["Date_Opened"] == "2026-02-26"
    item = {"id": "146520000003734311", "Posting_Title": "Trainee Roles", "City": "New Delhi", "Country": "India",
            "Publish": "True", "Remote_Job": "False"}
    http = FakeHttp({zoho_recruit.page_url(WADHWANI.slug): '<input id="jobs" value="' + json.dumps([item]).replace('"', "&quot;") + '">',
                     zoho_recruit.job_page_url(WADHWANI.slug, item["id"]): page})
    job = zoho_recruit.fetch(http, WADHWANI)[0]
    assert job.description_text.startswith("Experience: Fresher") and "0-1 years" in job.description_text
    assert job.location_raw == "New Delhi, Delhi, India" and job.posted_at == "2026-02-26T00:00:00Z"
    assert job.ats_workplace_type is None  # "False" as a string is not remote


def test_keka_live_html_description_becomes_text():
    raw = [{"id": 1, "title": "ML Engineer", "description": "<div>Who we are</div><div>0-1 years</div>", "experience": "0-1",
            "jobLocations": []}]
    job = keka.parse(raw, JUPITER)[0]
    assert "<div>" not in job.description_text and "Who we are" in job.description_text


def test_workday_india_only_board_screens_paths_by_location():
    assert workday.location_from_path("/job/India-Bangalore/ML-Engineer_R1") == "India Bangalore"
    assert workday.india_rank("/job/Bengaluru/ML-Engineer_R1") == 0
    assert workday.india_rank("/job/India-Remote/ML-Engineer_R1") == 0
    assert workday.india_rank("/job/IN-KA-BANGALORE-Home-Office/ML-Engineer_R3") == 0
    assert workday.india_rank("/job/BangaloreIND/ML-Engineer_R4") == 1  # unreadable: kept, checked later
    assert workday.india_rank("/job/ML-Engineer_R5") == 1  # no location segment (Samsung)
    assert workday.india_rank("/job/Santa-Clara-CA/ML-Engineer_R2") is None
    company = Company("BrowserStack", "workday", BS.slug, india_only=True)
    http = FakeHttp({workday.sitemap_url(BS.slug): text("workday_browserstack_sitemap.xml")})
    workday.fetch(http, company)
    # Dublin's engineering role is never requested; India Remote's is.
    assert not any("Dublin" in u for u in http.requested)
    assert any("India-Remote" in u for u in http.requested)
