"""Company websites for the job list's logos (scripts/find_websites.py, scripts/export_logos.py)."""

import export_logos
import find_websites as fw


def test_core_name_keeps_ai_so_lookalikes_dont_match():
    assert fw.core("Sarvam AI") == "sarvamai"
    assert fw.core("Character.AI") == "characterai"
    assert fw.core("Anysphere (Cursor)") == "anysphere"
    assert fw.core("Acme Technologies Inc") == "acme"


def test_ai_named_companies_try_dot_ai_first():
    assert fw.candidates({"name": "Sarvam AI", "slug": "sarvam"})[:2] == ["sarvam.ai", "sarvam.com"]
    assert fw.candidates({"name": "Character.AI", "slug": "character"})[0] == "character.ai"
    c = fw.candidates({"name": "Databricks", "slug": "databricks"})
    assert c[0] == "databricks.com" and len(c) == len(set(c))
    # Workday-style slugs ("tenant/wd5/site") aren't domains.
    assert not any("/" in d for d in fw.candidates({"name": "Visa", "slug": "visa/wd5/Visa"}))


def test_a_page_counts_only_when_its_title_names_the_company():
    page = "<html><head><title>Sarvam AI | Sovereign AI for India</title></head></html>"
    assert fw.names_company(page, "Sarvam AI")
    assert not fw.names_company("<title>Domain for sale</title>", "Sarvam AI")
    assert fw.names_company('<meta property="og:site_name" content="Hume AI">', "Hume AI")
    assert fw.names_company("<title>Cr&#232;me &amp; Co &mdash; Hume</title>", "Hume")
    assert not fw.names_company("<title>Character | Brand studio</title>", "Character.AI")


def test_redirects_must_stay_on_the_company_site():
    assert fw.same_site("https://www.sarvam.ai/", "sarvam.com", "Sarvam AI") == "sarvam.ai"
    assert fw.same_site("https://hume.ai:443/en", "hume.ai", "Hume AI") == "hume.ai"  # no port kept
    assert fw.same_site("https://www.linkedin.com/company/cartesia", "cartesia.ai", "Cartesia") is None
    assert fw.same_site("https://sedo.com/search?q=flint", "flint.com", "Flint") is None


def test_short_names_need_a_link_to_their_own_board():
    company = {"name": "Flint", "ats": "ashby", "slug": "flint"}
    assert fw.links_board('<a href="https://jobs.ashbyhq.com/flint">Careers</a>', company)
    assert not fw.links_board('<a href="https://jobs.ashbyhq.com/other">Careers</a>', company)
    assert len(fw.core("Flint")) < fw.DISTINCTIVE <= len(fw.core("Databricks"))


def test_domain_cleanup():
    assert export_logos.domain("https://www.Example.ai/careers") == "example.ai"
    assert export_logos.domain("not a site") is None


def test_site_copy_is_up_to_date():
    # Run scripts/export_logos.py after editing websites in config/companies.yaml.
    assert export_logos.TARGET.read_text() == export_logos.exported()
