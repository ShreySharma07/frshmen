import fetch_jobs as fj
from sources.models import Job


def _job(ext_id, title="ML Engineer", url="https://x/1", company="Acme"):
    return Job("ashby", ext_id, company, "acme", title, url, "Remote", "text")


def test_dedupe_drops_repeat_ids_and_cross_posts():
    a = _job("1")
    same_id = _job("1", title="Other title")
    cross_post = _job("2", url="https://x/1?utm=abc")  # same role, new id, tracking param
    different = _job("3", title="Data Scientist", url="https://x/3")
    assert fj.dedupe([a, same_id, cross_post, different]) == [a, different]


def test_load_companies_keeps_only_fetchable(tmp_path):
    cfg = tmp_path / "companies.yaml"
    cfg.write_text(
        "companies:\n"
        "  - {name: A, category: lab, ats: ashby, slug: a, verified: true, jobs: 3}\n"
        "  - {name: B, category: lab, ats: ashby, slug: b, verified: true, jobs: 0}\n"
        "  - {name: C, category: lab, ats: ashby, slug: c, verified: false}\n"
        "  - {name: D, category: lab, ats: icims, slug: d, verified: true, jobs: 5}\n"
        "  - {name: E, category: lab, ats: lever, slug: e}\n"
    )
    assert [c.name for c in fj.load_companies(cfg)] == ["A"]
