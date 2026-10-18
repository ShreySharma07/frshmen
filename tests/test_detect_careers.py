"""Careers-system detector: recognising boards in real-world page patterns, finding careers links,
obeying robots.txt, and updating a company entry. Offline: a fake client serves the pages."""

import detect_careers as d

FIREWORKS = """<html><body><h1>Careers</h1>
<a href="https://jobs.ashbyhq.com/fireworks/aa3039fe-bd24-4b0f-8b7f-f146e0d14fb4">Research Engineer</a>
<a href="https://jobs.ashbyhq.com/fireworks/2d0a20e1-8b0a-40b0-9b5e-514bca715fba">Software Engineer</a>
</body></html>"""


def test_board_links_name_the_system_and_slug():
    found = d.fingerprint(FIREWORKS, "https://fireworks.ai/careers")
    assert {(f.system, f.slug) for f in found} == {("ashby", "fireworks")}


def test_embeds_and_redirects_are_recognised():
    cases = {
        '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>': ("greenhouse", "acme"),
        '<iframe src="https://job-boards.greenhouse.io/embed/job_board?for=acme&amp;b=x"></iframe>': ("greenhouse", "acme"),
        '<a href="https://jobs.lever.co/acme/1234-abcd">Apply</a>': ("lever", "acme"),
        '<a href="https://acme.wd5.myworkdayjobs.com/en-US/Acme_Careers/job/Pune/ML_R1">x</a>': ("workday", "acme/wd5/Acme_Careers"),
        '<a href="https://ejgk.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1">x</a>': ("oracle", "ejgk.fa.em2.oraclecloud.com/CX_1"),
        '<a href="https://zepto.darwinbox.in/ms/candidate/careers">Jobs</a>': ("darwinbox", "zepto"),
        '<a href="https://acme.keka.com/careers/">Jobs</a>': ("keka", "acme"),
        '<a href="https://wadhwaniai.zohorecruit.in/jobs/Careers">Jobs</a>': ("zoho_recruit", "wadhwaniai.zohorecruit.in"),
    }
    for html, want in cases.items():
        assert (d.fingerprint(html, "https://acme.com/careers")[0].system,
                d.fingerprint(html, "https://acme.com/careers")[0].slug) == want, html
    # A /careers page that redirected straight to the hiring system: the final URL is enough.
    assert d.fingerprint("<html></html>", "https://acme.wd3.myworkdayjobs.com/External")[0].slug == "acme/wd3/External"


def test_infrastructure_paths_are_never_taken_for_a_board():
    html = ('<script src="https://boards.greenhouse.io/embed/job_app?token=1"></script>'
            '<link href="https://acme.wd1.myworkdayjobs.com/wday/cxs/acme/x/jobs">')
    assert d.fingerprint(html, "https://acme.com/careers") == []


def test_schema_org_jobs_make_any_site_readable():
    html = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"ML Engineer"}</script>'
    found = d.fingerprint(html, "https://careers.acme.com/job/1")
    assert [(f.system, f.slug, f.supported) for f in found] == [("careersite", "careers.acme.com", True)]


def test_systems_without_an_adapter_are_recorded_for_later():
    found = d.fingerprint('<a href="https://careers-acme.icims.com/jobs/search">Jobs</a>', "https://acme.com/careers")
    assert [(f.system, f.supported) for f in found] == [("icims", False)]


def test_careers_links_by_text_or_address_same_site_or_hiring_system():
    html = """
      <a href="/about">About</a>
      <a href="/company/careers">Work with us</a>
      <a href="https://careers.acme.com/">Join the team</a>
      <a href="https://jobs.myntra.com/home">Jobs</a>
      <a href="https://www.cloudflare.com/careers/">Careers</a>
      <a href="https://boards.greenhouse.io/acme">Open roles</a>
      <a href="mailto:jobs@acme.com">jobs@acme.com</a>"""
    links = d.career_links(html, "https://www.acme.com/")
    assert links == ["https://www.acme.com/company/careers", "https://careers.acme.com/", "https://boards.greenhouse.io/acme"]


def test_registrable_domain():
    assert d.registrable("careers.acme.co.in") == "acme.co.in"
    assert d.registrable("www.acme.com") == "acme.com"


class FakeHttp:
    """Serves pages by URL; robots.txt and redirects as configured. Records what was fetched."""

    def __init__(self, pages, robots=None, redirects=None):
        self.pages, self.robots, self.redirects, self.fetched = pages, robots or {}, redirects or {}, []

    def get_text(self, url, accept=None):
        return self.robots.get(url)

    def get_page(self, url):
        self.fetched.append(url)
        final = self.redirects.get(url, url)
        return (final, self.pages[final]) if final in self.pages else None


def test_detect_follows_the_careers_link_and_stops_at_a_readable_board():
    http = FakeHttp({
        "https://acme.com": '<a href="/join">We are hiring</a>',
        "https://acme.com/join": FIREWORKS,
    })
    result = d.detect(http, "acme.com")
    assert (result.best.system, result.best.slug) == ("ashby", "fireworks")
    assert result.careers_url == "https://acme.com/join"
    assert http.fetched == ["https://acme.com", "https://acme.com/join"]  # stopped once found


def test_detect_obeys_robots_txt():
    http = FakeHttp({"https://acme.com": "<html></html>", "https://acme.com/careers": FIREWORKS},
                    robots={"https://acme.com/robots.txt": "User-agent: *\nDisallow: /careers\n"})
    result = d.detect(http, "acme.com")
    assert result.best is None and "https://acme.com/careers" in result.blocked
    assert "https://acme.com/careers" not in http.fetched


def test_detect_reads_a_redirect_to_the_hiring_system():
    http = FakeHttp({"https://acme.com": "<html></html>", "https://acme.wd3.myworkdayjobs.com/External": "<html></html>"},
                    redirects={"https://acme.com/careers": "https://acme.wd3.myworkdayjobs.com/External"})
    assert d.detect(http, "https://acme.com").best.slug == "acme/wd3/External"


def test_apply_resets_verification_only_when_the_board_changes():
    company = {"name": "Fireworks AI", "category": "infra", "hq": "us", "ats": "greenhouse", "slug": "fireworksai",
               "verified": False, "checked": "2026-10-06"}
    det = d.Detection("https://fireworks.ai", "https://fireworks.ai/careers",
                      d.fingerprint(FIREWORKS, "https://fireworks.ai/careers"), pages=2)
    updated = d.apply(company, det)
    assert (updated["ats"], updated["slug"], updated["website"]) == ("ashby", "fireworks", "fireworks.ai")
    assert "verified" not in updated and "checked" not in updated  # re-probed by verify_companies
    assert updated["careers"].startswith("ashby: ")


def test_apply_records_unknown_and_missing_careers_systems():
    company = {"name": "Acme", "category": "mnc", "hq": "us", "ats": "greenhouse", "slug": "acme", "verified": False}
    icims = d.Detection("https://acme.com", found=[d.Found("icims", None, False, "https://acme.com/careers")])
    assert d.apply(company, icims)["careers"] == "icims (no adapter yet): https://acme.com/careers"
    assert d.apply(company, icims)["ats"] == "greenhouse"  # unchanged until an adapter exists
    assert d.apply(company, d.Detection("https://acme.com", pages=6))["careers"] == "not found (6 pages read)"
