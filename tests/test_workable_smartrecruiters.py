"""Workable and SmartRecruiters adapters, on payloads in the shapes seen live (2026-10-18:
Writesonic on Workable, Swiggy on SmartRecruiters; descriptions shortened)."""

from sources import smartrecruiters, workable
from sources.models import Company

WRITESONIC = Company("Writesonic", "workable", "writesonic")


def _wk_job(code, title, country, cc, **extra):
    return {"title": title, "shortcode": code, "employment_type": "Full-time", "telecommuting": True,
            "department": None, "url": f"https://apply.workable.com/j/{code}", "published_on": "2025-11-16",
            "created_at": "2025-11-16", "country": country, "city": "", "state": "", "experience": "Associate",
            "function": "Engineering", "locations": [{"country": country, "countryCode": cc, "city": "",
                                                       "region": None, "hidden": False}],
            "description": "<p>About the role</p><ul><li>2-5 years shipping production React apps</li></ul>",
            **extra}


WORKABLE = {"name": "Writesonic", "description": None, "jobs": [
    _wk_job("92488277FE", "Agency Partnerships Lead", "United States", "US"),
    _wk_job("92488277FE", "Agency Partnerships Lead", "India", "IN"),  # same job, second country
    _wk_job("F057CDC530", "Frontend Engineer", "India", "IN"),
]}


def test_workable_merges_a_job_listed_once_per_country():
    jobs = workable.parse(WORKABLE, WRITESONIC)
    assert [j.external_id for j in jobs] == ["92488277FE", "F057CDC530"]
    lead = jobs[0]
    assert lead.location_raw == "United States / India" and lead.ats_countries == ["US", "IN"]


def test_workable_fields():
    job = workable.parse(WORKABLE, WRITESONIC)[1]
    assert job.id == "workable:writesonic:F057CDC530"
    assert job.url == "https://apply.workable.com/j/F057CDC530"
    assert job.posted_at == "2025-11-16T00:00:00Z" and job.ats_workplace_type == "remote"
    assert "2-5 years shipping production React apps" in job.description_text  # the YoE line survives
    assert job.department == "Engineering" and job.employment_type == "Full-time"


def test_workable_missing_board_yields_no_jobs():
    assert workable.parse(None, WRITESONIC) == []


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.requested = routes, []

    def get_json(self, url, fresh_days=None):
        self.requested.append(url)
        return self.routes.get(url)


def _sr_listed(pid, name, country="in", remote=False):
    return {"id": pid, "name": name, "releasedDate": "2026-10-15T11:43:32.959Z",
            "location": {"city": "Bengaluru", "region": "KA", "country": country, "remote": remote,
                         "hybrid": False, "fullLocation": "Bengaluru, KA, India"}}


SR_DETAIL = {
    "id": "6000000001491424", "name": "Senior Manager - Applied Science",
    "location": {"city": "Bengaluru", "region": "KA", "country": "in", "remote": False, "hybrid": False,
                 "fullLocation": "Bengaluru, KA, India"},
    "releasedDate": "2026-10-15T11:43:32.959Z",
    "postingUrl": "https://jobs.smartrecruiters.com/SWIGGY/6000000001491424-senior-manager-applied-science",
    "jobAd": {"sections": {
        "companyDescription": {"title": "Company Description", "text": "<p>About Swiggy</p>"},
        "jobDescription": {"title": "Job Description", "text": "<p>Lead a team of data scientists.</p>"
                           "<p>10+ years of hands-on experience in Data Science.</p>"},
        "qualifications": {"title": "Qualifications", "text": "<p>Experience with MLOps.</p>"},
        "additionalInformation": {"title": "Additional Information", "text": "<p>Equal opportunity employer.</p>"},
        "videos": {"title": "Videos To Watch", "urls": ["https://www.youtube.com/watch?v=x"]},
    }},
    "function": {"id": "engineering", "label": "Engineering"},
    "typeOfEmployment": {"id": "permanent", "label": "Full-time"},
}
SWIGGY = Company("Swiggy", "smartrecruiters", "swiggy")


def test_smartrecruiters_detail_keeps_requirements_and_drops_company_blurb():
    job = smartrecruiters.parse_detail(SR_DETAIL, SWIGGY)
    assert job.id == "smartrecruiters:swiggy:6000000001491424"
    assert "10+ years of hands-on experience" in job.description_text
    assert "Qualifications\nExperience with MLOps." in job.description_text
    assert "About Swiggy" not in job.description_text
    assert job.location_raw == "Bengaluru, KA, India" and job.ats_countries == ["IN"]
    assert job.posted_at == "2026-10-15T11:43:32Z" and job.ats_workplace_type is None
    assert job.url.startswith("https://jobs.smartrecruiters.com/SWIGGY/")


def test_smartrecruiters_fetches_details_only_for_titles_that_could_fit():
    listing = {"offset": 0, "limit": 100, "totalFound": 3, "content": [
        _sr_listed("1", "Senior Executive - Warehouse"),
        _sr_listed("2", "Sales Manager I"),
        _sr_listed("6000000001491424", "Data Scientist - Instamart"),
    ]}
    http = FakeHttp({smartrecruiters.list_url("swiggy", 0): listing,
                     smartrecruiters.detail_url("swiggy", "6000000001491424"): SR_DETAIL})
    jobs = smartrecruiters.fetch(http, SWIGGY)
    assert [j.external_id for j in jobs] == ["6000000001491424"]
    assert http.requested == [smartrecruiters.list_url("swiggy", 0),
                              smartrecruiters.detail_url("swiggy", "6000000001491424")]


def test_smartrecruiters_india_only_boards_skip_other_countries_before_any_detail():
    bosch = Company("Bosch", "smartrecruiters", "BoschGroup", india_only=True)
    listing = {"totalFound": 3, "content": [
        _sr_listed("1", "Machine Learning Engineer", country="de"),
        _sr_listed("2", "Machine Learning Engineer", country="de", remote=True),
        _sr_listed("3", "Machine Learning Engineer"),
    ]}
    http = FakeHttp({smartrecruiters.list_url("BoschGroup", 0): listing})
    smartrecruiters.fetch(http, bosch)
    assert [u.rsplit("/", 1)[1] for u in http.requested[1:]] == ["2", "3"]


def test_smartrecruiters_pages_until_total_found():
    first = {"totalFound": 101, "content": [_sr_listed(str(i), "Engineer") for i in range(100)]}
    second = {"totalFound": 101, "content": [_sr_listed("100", "Engineer")]}
    http = FakeHttp({smartrecruiters.list_url("x", 0): first, smartrecruiters.list_url("x", 100): second})
    assert len(smartrecruiters.postings(http, "x")) == 101
    assert len(http.requested) == 2
