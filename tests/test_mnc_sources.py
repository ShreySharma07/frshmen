"""Amazon and Eightfold adapters, on payloads in the shapes seen live (2026-10-06 survey)."""

from sources import amazon, eightfold
from sources.http import FetchError
from sources.models import Company


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def get_json(self, url):
        self.requested.append(url)
        body = self.routes.get(url)
        if isinstance(body, Exception):
            raise body
        return body


AMAZON = Company("Amazon", "amazon", "IND", india_only=True)
AMZ_JOB = {
    "id": "x1", "id_icims": "10535819", "title": "Software Development Engineer I, Alexa",
    "job_path": "/en/jobs/10535819/software-development-engineer-i-alexa", "location": "IN, KA, Bengaluru",
    "normalized_location": "Bengaluru, Karnataka, IND", "city": "Bengaluru", "country_code": "IND",
    "posted_date": "September 10, 2026", "description": "Build Alexa features in Python.",
    "basic_qualifications": "- Bachelor's degree in CS&lt;br/&gt;- 0-1 years of programming experience",
    "preferred_qualifications": "- Experience with ML", "job_category": "Software Development",
}


def test_amazon_parse_keeps_qualifications_as_text():
    job = amazon.parse([AMZ_JOB], AMAZON)[0]
    assert job.url == "https://www.amazon.jobs/en/jobs/10535819/software-development-engineer-i-alexa"
    assert job.external_id == "10535819" and job.posted_at == "2026-09-10T00:00:00Z"
    assert "Basic qualifications" in job.description_text and "0-1 years" in job.description_text
    assert "&lt;" not in job.description_text and "<br" not in job.description_text
    assert job.location_raw == "Bengaluru, Karnataka, IND" and job.ats_countries == ["IND"]


def test_amazon_pages_until_hits_and_screens_titles():
    sales = dict(AMZ_JOB, id_icims="2", title="Account Manager")
    http = FakeHttp({amazon.page_url("IND", 0): {"hits": 3, "jobs": [AMZ_JOB, sales]},
                     amazon.page_url("IND", 100): {"hits": 3, "jobs": [dict(AMZ_JOB, id_icims="3")]}})
    assert [j.external_id for j in amazon.fetch(http, AMAZON)] == ["10535819", "3"]


NETAPP = Company("NetApp", "eightfold", "netapp.eightfold.ai/netapp.com", india_only=True)
QCOM = Company("Qualcomm", "eightfold", "careers.qualcomm.com/qualcomm.com", india_only=True)


def test_eightfold_v2_tenant_uses_list_descriptions():
    pos = {"id": 7, "name": "Software Engineer - ML", "locations": ["Bengaluru, Karnataka, India"],
           "t_create": 1791138600, "job_description": "<p>Python, 0-2 years</p>", "department": "Engineering",
           "canonicalPositionUrl": "https://netapp.eightfold.ai/careers/job/7", "display_job_id": "R-7",
           "work_location_option": "onsite"}
    http = FakeHttp({eightfold.v2_url(NETAPP.slug, 0): {"positions": [pos], "count": 1}})
    job = eightfold.fetch(http, NETAPP)[0]
    assert len(http.requested) == 1  # no per-job calls on v2 tenants
    assert (job.external_id, job.location_raw, job.ats_workplace_type) == ("R-7", "Bengaluru, Karnataka, India", "onsite")
    assert "0-2 years" in job.description_text and job.posted_at == "2026-10-04T18:30:00Z"


def test_eightfold_pcsx_tenant_falls_back_and_fetches_details():
    pos = {"id": 99, "name": "Machine Learning Engineer", "locations": ["Hyderabad, Telangana, India"],
           "postedTs": 1791138600, "positionUrl": "/careers/job/99", "workLocationOption": "hybrid"}
    other = {"id": 100, "name": "Finance Manager", "locations": ["Hyderabad, Telangana, India"]}
    http = FakeHttp({
        eightfold.v2_url(QCOM.slug, 0): FetchError("careers.qualcomm.com: HTTP 403"),
        eightfold.pcsx_url(QCOM.slug, 0): {"status": 200, "data": {"positions": [pos, other], "count": 2}},
        eightfold.detail_url(QCOM.slug, 99): {"id": 99, "job_description": "Experience: 1-6 years"},
    })
    jobs = eightfold.fetch(http, QCOM)
    assert [j.title for j in jobs] == ["Machine Learning Engineer"]  # finance screened before any detail call
    assert eightfold.detail_url(QCOM.slug, 100) not in http.requested
    job = jobs[0]
    assert job.url == "https://careers.qualcomm.com/careers/job/99" and job.ats_workplace_type == "hybrid"
    assert job.description_text == "Experience: 1-6 years"


def test_eightfold_other_errors_are_not_swallowed():
    http = FakeHttp({eightfold.v2_url(QCOM.slug, 0): FetchError("careers.qualcomm.com: HTTP 500")})
    try:
        eightfold.list_titles(http, QCOM.slug)
    except FetchError:
        return
    raise AssertionError("a 500 must surface, not fall through to PCSX")
