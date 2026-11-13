"""Gem, Rippling, Teamtailor, JazzHR and YC job pages, on responses saved live on 2026-11-12
(Gem's own board, Rippling's own board, Cerrion on Teamtailor, H2O.ai on JazzHR, Brickanta on YC;
descriptions shortened)."""

import json
from pathlib import Path

from sources import ADAPTERS, gem, jazzhr, rippling, teamtailor, xmlfeed, yc_jobs
from sources.models import Company

FIX = Path(__file__).parent / "fixtures" / "sources"


def text(name):
    return (FIX / name).read_text()


class FakeHttp:
    """Serves saved bodies by URL and records what was asked."""

    def __init__(self, json_by_url=None, text_by_url=None):
        self.json_by_url, self.text_by_url, self.asked = json_by_url or {}, text_by_url or {}, []

    def get_json(self, url, fresh_days=None):
        self.asked.append(url)
        return self.json_by_url.get(url)

    def get_text(self, url, accept=None, fresh_days=None):
        self.asked.append(url)
        return self.text_by_url.get(url)


def test_every_new_reader_is_registered():
    assert {"gem", "rippling", "teamtailor", "jazzhr", "yc_jobs"} <= set(ADAPTERS)


def test_gem_job_post():
    [job] = gem.parse(json.loads(text("gem_gem.json")), Company("Gem", "gem", "gem"))
    assert job.id == "gem:gem:am9icG9zdDoxt66pB6mvVDH0kCIS4bLF"
    assert job.title == "Engineering Manager (AI Products)"
    assert job.location_raw == "San Francisco, United States"  # the office repeats the job's place: once
    assert job.ats_workplace_type == "hybrid" and job.department == "Engineering"
    assert job.posted_at == "2026-03-05T00:36:12Z"
    assert "at least 5+ years of industry experience" in job.description_text  # the YoE evidence survives


def test_gem_reads_the_documented_endpoint():
    http = FakeHttp({gem.url_for("gem"): json.loads(text("gem_gem.json"))})
    assert gem.list_titles(http, "gem") == ["Engineering Manager (AI Products)"]
    assert http.asked == ["https://api.gem.com/job_board/v0/gem/job_posts/"]


def test_rippling_fetches_details_only_for_titles_that_could_fit():
    slug = "rippling"
    listed = json.loads(text("rippling_list.json"))
    engineering = next(j for j in listed if "Engineering" in j["name"])
    detail = dict(json.loads(text("rippling_detail.json")), uuid=engineering["uuid"], name=engineering["name"])
    http = FakeHttp({rippling.list_url(slug): listed, rippling.detail_url(slug, engineering["uuid"]): detail})
    jobs = rippling.fetch(http, Company("Rippling", "rippling", slug))
    # Two sales roles in the list: no detail call for them.
    assert [u.rsplit("/", 1)[-1] for u in http.asked[1:]] == [engineering["uuid"]]
    assert [j.title for j in jobs] == [engineering["name"]]


def test_rippling_detail():
    job = rippling.parse_detail(json.loads(text("rippling_detail.json")), Company("Rippling", "rippling", "rippling"))
    assert job.id == "rippling:rippling:2f770fc2-e1f2-4538-beba-ca9cb69352a6"
    assert job.location_raw == "Boston, MA" and job.department == "Sales"
    assert job.employment_type == "Salaried, full-time"
    assert job.posted_at == "2026-10-26T18:38:33Z"
    # The role text comes first, the company blurb after it.
    assert job.description_text.index("5+ years sales experience") < job.description_text.index("About Rippling")


def test_teamtailor_feed():
    items = xmlfeed.records(text("teamtailor_cerrion.rss"), "item")
    jobs = teamtailor.parse(items, Company("Cerrion", "teamtailor", "careers.cerrion.com"))
    job = jobs[0]
    assert len(jobs) == 2
    assert job.id == "teamtailor:careers.cerrion.com:89258a2c-16a4-408a-8311-66474c008483"
    assert (job.title, job.url) == ("Growth Marketer", "https://careers.cerrion.com/jobs/8685681-growth-marketer")
    assert job.location_raw == "Zurich, Switzerland" and job.ats_workplace_type == "hybrid"
    assert job.posted_at == "2026-11-08T19:32:20Z" and job.department == "Marketing"
    assert job.description_text.startswith("About Cerrion")


def test_teamtailor_reads_the_feed_on_the_sites_own_host_and_says_none_when_there_is_no_feed():
    url = teamtailor.url_for("careers.cerrion.com")
    assert url.startswith("https://careers.cerrion.com/jobs.rss?")
    http = FakeHttp(text_by_url={url: text("teamtailor_cerrion.rss")})
    assert teamtailor.list_titles(http, "careers.cerrion.com")[0] == "Growth Marketer"
    assert teamtailor.list_titles(FakeHttp(text_by_url={teamtailor.url_for("acme.com"): "<html>404</html>"}),
                                  "acme.com") is None


def test_jazzhr_feed():
    jobs = jazzhr.parse(text("jazzhr_h2oai.xml"), Company("H2O.ai", "jazzhr", "h2oai"))
    ai = next(j for j in jobs if j.title == "AI Engineer")
    assert ai.id.startswith("jazzhr:h2oai:job_") and ai.url.startswith("https://h2oai.applytojob.com/apply/")
    assert ai.employment_type == "Full Time" and ai.description_text
    assert jazzhr.url_for("h2oai") == "https://app.jazz.co/feeds/export/jobs/h2oai"


def test_jazzhr_keeps_its_experience_field_as_evidence_and_skips_closed_jobs():
    xml = ("<jobs><job><id><![CDATA[1]]></id><status><![CDATA[Open]]></status><title><![CDATA[ML Engineer]]></title>"
           "<url><![CDATA[https://acme.applytojob.com/apply/1/ML]]></url><description><![CDATA[<p>Build models.</p>]]>"
           "</description><experience><![CDATA[Entry Level]]></experience></job>"
           "<job><id><![CDATA[2]]></id><status><![CDATA[Closed]]></status><title><![CDATA[Old]]></title>"
           "<url><![CDATA[https://acme.applytojob.com/apply/2/Old]]></url></job></jobs>")
    [job] = jazzhr.parse(xml, Company("Acme", "jazzhr", "acme"))
    assert job.description_text == "Build models.\nExperience: Entry Level"


def test_yc_company_page_lists_only_its_own_jobs():
    links = yc_jobs.job_links(text("yc_brickanta_jobs.html"), "brickanta")
    assert [w for _, w in links] == ["forward deployed construction engineer belgium", "brand marketing manager",
                                     "developer intern summer 2027", "account executive"]
    assert all(u.startswith("https://www.ycombinator.com/companies/brickanta/jobs/") for u, _ in links)


def test_yc_fetch_reads_job_pages_whose_titles_could_fit():
    company = Company("Brickanta", "yc_jobs", "brickanta")
    page = text("yc_brickanta_jobs.html")
    job_url = "https://www.ycombinator.com/companies/brickanta/jobs/dM8327V-forward-deployed-construction-engineer-belgium"
    http = FakeHttp(text_by_url={yc_jobs.list_url("brickanta"): page, job_url: text("yc_brickanta_job.html")})
    jobs = yc_jobs.fetch(http, company)
    # Marketing and sales pages are never fetched; the intern page is asked for (and has no saved body here).
    assert not any("marketing" in u or "account-executive" in u for u in http.asked)
    assert [j.id for j in jobs] == ["yc_jobs:brickanta:dM8327V"]
    job = jobs[0]
    assert job.title == "Forward Deployed Construction Engineer (Belgium)" and job.location_raw == "Remote"
    assert job.posted_at == "2026-11-12T11:43:35Z" and "Brickanta" in job.description_text


# --- iCIMS (Atlassian), saved live on 2026-11-12, description shortened ---

from sources import careersite  # noqa: E402


def test_icims_job_pages_are_fetched_from_the_inner_frame():
    # A plain client gets Atlassian's branded wrapper without the job data (seen in CI 2026-11-13).
    url = "https://careers-apac-atlassian.icims.com/jobs/26758/software-engineer/job"
    assert careersite.page_url(url) == url + "?in_iframe=1"
    assert careersite.page_url("https://careers.ey.com/ey/job/Kolkata-AI/1/") == "https://careers.ey.com/ey/job/Kolkata-AI/1/"


def test_icims_job_page_id_and_placeholder_address():
    url = "https://careers-apac-atlassian.icims.com/jobs/26758/software-engineer/job"
    job = careersite.parse_page(text("icims_atlassian_job.html"), url,
                                Company("Atlassian", "careersite", "careers-apac-atlassian.icims.com"))
    assert job.external_id == "26758"
    assert "UNAVAILABLE" not in job.location_raw and job.location_raw == "Remote"
