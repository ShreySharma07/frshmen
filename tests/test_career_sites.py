"""Career-site and Oracle Recruiting adapters, on responses saved from EY and KPMG India (2026-10-08)."""

import json

from extract.classify import classify
from sources import careersite, oracle
from sources.models import Company

FIX = "tests/fixtures/sources/"
EY = Company("EY", "careersite", "careers.ey.com", india_only=True)
KPMG = Company("KPMG India", "oracle", "ejgk.fa.em2.oraclecloud.com/CX_1", india_only=True)


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def _get(self, url):
        self.requested.append(url)
        return self.routes.get(url)

    def get_text(self, url, accept=None, fresh_days=None):
        return self._get(url)

    def get_json(self, url, fresh_days=None):
        return self._get(url)


def read(name):
    return open(FIX + name).read()


# --- careersite (SuccessFactors) ---------------------------------------------------------------

def test_microdata_job_page_parses_title_location_date_and_text():
    job = careersite.parse_page(read("careersite_ey_job.html"),
                                "https://careers.ey.com/ey/job/Bengaluru-Associate-SaT/1423670533/", EY)
    assert job.title == "Associate - SaT - TMT - SaT - TCF - Financial Diligence - Bangalore"
    assert job.location_raw == "Bengaluru, KA, IN" and job.posted_at == "2026-10-03T02:00:00Z"
    assert job.external_id == "1423670533" and job.id == "careersite:careers.ey.com:1423670533"
    assert job.description_text.startswith("Requisition Id: 1733374") and "Apply Now" in job.description_text


def test_jsonld_job_page_wins_and_reads_remote():
    page = """<html><script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
      {"@type": "Organization", "name": "Acme"},
      {"@type": "JobPosting", "title": "ML Engineer &amp; Intern", "description": "<p>0-1 years. Python.</p>",
       "datePosted": "2026-10-01", "identifier": {"@type": "PropertyValue", "value": "R-77"},
       "jobLocation": {"@type": "Place", "address": {"addressLocality": "Pune", "addressCountry": "IN"}},
       "jobLocationType": "TELECOMMUTE", "employmentType": ["FULL_TIME", "INTERN"]}]}</script>
      <span itemprop="title">ignored</span></html>"""
    job = careersite.parse_page(page, "https://jobs.acme.com/job/ml-engineer/", Company("Acme", "careersite", "jobs.acme.com"))
    assert (job.title, job.external_id, job.location_raw) == ("ML Engineer & Intern", "R-77", "Pune, IN / Remote")
    assert job.description_text == "0-1 years. Python." and job.employment_type == "FULL_TIME, INTERN"
    assert job.posted_at == "2026-10-01T00:00:00Z"


def test_pages_without_job_data_are_skipped():
    assert careersite.parse_page("<html><h1>Careers</h1></html>", "https://x.com/job/1/", EY) is None


def test_sitemap_screen_keeps_india_target_titles_newest_first():
    http = FakeHttp({"https://careers.ey.com/sitemap.xml": read("careersite_ey_sitemap.xml")})
    urls = careersite.screen(careersite.job_entries(http, "careers.ey.com"), india_only=True)
    words = [careersite._words(u) for u in urls]
    assert words and all("AI" in w or "Python" in w for w in words)  # audit/tax roles and non-India dropped
    assert not any("Assurance" in w or "Putul" in w for w in words)
    # Not india_only: the same titles screen, wherever they are.
    assert len(careersite.screen(careersite.job_entries(http, "careers.ey.com"), india_only=False)) >= len(urls)


def test_sitemap_index_is_followed():
    index = "<sitemapindex><sitemap><loc>https://c.com/sm1.xml</loc></sitemap></sitemapindex>"
    child = "<urlset><url><loc>https://c.com/job/Pune-ML-Engineer/123456/</loc><lastmod>2026-10-01</lastmod></url>" \
            "<url><loc>https://c.com/about/</loc></url></urlset>"
    http = FakeHttp({"https://c.com/sitemap.xml": index, "https://c.com/sm1.xml": child})
    assert careersite.job_entries(http, "c.com") == [("https://c.com/job/Pune-ML-Engineer/123456/", "2026-10-01")]


def test_careersite_fetch_end_to_end():
    sitemap = ("<urlset><url><loc>https://careers.ey.com/ey/job/Bengaluru-Python-AI-Engineer-KA/1423670533/</loc>"
               "<lastmod>2026-10-03</lastmod></url></urlset>")
    http = FakeHttp({"https://careers.ey.com/sitemap.xml": sitemap,
                     "https://careers.ey.com/ey/job/Bengaluru-Python-AI-Engineer-KA/1423670533/": read("careersite_ey_job.html")})
    jobs = careersite.fetch(http, EY)
    assert [j.external_id for j in jobs] == ["1423670533"]


# --- oracle ------------------------------------------------------------------------------------

def test_oracle_lists_pages_and_fetches_details_for_fitting_titles():
    listing = json.loads(read("oracle_kpmg_list.json"))
    # Make one listed title a target role so the screen keeps it.
    listing["items"][0]["requisitionList"][0]["Title"] = "Data Scientist - GenAI"
    detail = json.loads(read("oracle_kpmg_detail.json"))
    http = FakeHttp({oracle.list_url(KPMG.slug, 0): listing,
                     oracle.detail_url(KPMG.slug, "INTG10040445"): detail})
    jobs = oracle.fetch(http, KPMG)
    assert len(jobs) == 1 and http.requested[-1] == oracle.detail_url(KPMG.slug, "INTG10040445")
    assert "%22INTG10040445%22" in http.requested[-1] and "siteNumber=CX_1" in http.requested[-1]


def test_oracle_detail_parses_and_keeps_the_years_requirement():
    job = oracle.parse_detail(json.loads(read("oracle_kpmg_detail.json")), KPMG)
    assert job.title == "Executive - SFDC - Technical" and job.external_id == "INTG10048124"
    assert job.url == "https://ejgk.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/INTG10048124"
    assert job.location_raw == "Bangalore, Karnataka, India" and job.posted_at == "2026-07-24T03:27:29Z"
    assert job.description_text.count("Engineering Grad / Postgraduate") == 1  # internal copy not repeated
    assert classify(job.title, job.description_text).level == "experienced"  # "4+ years" survives the HTML


def test_oracle_list_titles_and_non_oracle_hosts():
    http = FakeHttp({oracle.list_url(KPMG.slug, 0): json.loads(read("oracle_kpmg_list.json"))})
    assert oracle.list_titles(http, KPMG.slug)[0] == "Manager - Data Engineer"
    assert oracle.list_titles(FakeHttp({}), "nope.example.com/CX_1") is None


def test_oracle_india_only_drops_other_countries():
    listing = json.loads(read("oracle_kpmg_list.json"))
    for r in listing["items"][0]["requisitionList"]:
        r["Title"], r["PrimaryLocationCountry"] = "Machine Learning Engineer", "US"
    http = FakeHttp({oracle.list_url(KPMG.slug, 0): listing})
    assert oracle.fetch(http, KPMG) == []


def test_urls_without_place_or_title_are_kept_after_india_ones():
    entries = [
        ("https://careers.hcltech.com/job/Python-AI-Engineer/1357133655/", "2026-10-07"),  # no place (HCLTech)
        ("https://jobs.zs.com/jobs/68093?lang=en-us", "2026-10-06"),  # no words at all (ZS)
        ("https://careers.hcltech.com/job/Pune-ML-Engineer/1357133656/", "2026-10-01"),  # India, older
        ("https://careers.hcltech.com/job/Dallas-ML-Engineer-USA/1357133657/", "2026-10-08"),  # elsewhere
        ("https://careers.hcltech.com/job/Pune-Tax-Auditor/1357133658/", "2026-10-08"),  # not a target title
    ]
    assert careersite.screen(entries, india_only=True) == [
        "https://careers.hcltech.com/job/Pune-ML-Engineer/1357133656/",
        "https://careers.hcltech.com/job/Python-AI-Engineer/1357133655/",
        "https://jobs.zs.com/jobs/68093?lang=en-us",
    ]
