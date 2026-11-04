"""Company websites for the job list's logos (scripts/find_websites.py, scripts/export_logos.py)."""

import export_logos
import find_websites as fw


def test_core_name_drops_words_that_dont_tell_companies_apart():
    assert fw.core("Sarvam AI") == "sarvam"
    assert fw.core("Anysphere (Cursor)") == "anysphere"
    assert fw.core("Allen Institute for AI") == "alleninstitutefor"


def test_candidates_try_common_domains_and_the_board_slug():
    c = fw.candidates({"name": "Sarvam AI", "slug": "sarvam"})
    assert c[:4] == ["sarvam.com", "sarvam.ai", "sarvamai.com", "sarvamai.ai"]
    assert "sarvam.io" in c and len(c) == len(set(c))
    # Workday-style slugs ("tenant/wd5/site") aren't domains.
    assert not any("/" in d for d in fw.candidates({"name": "Visa", "slug": "visa/wd5/Visa"}))


def test_a_page_counts_only_when_its_title_names_the_company():
    page = "<html><head><title>Sarvam AI | Sovereign AI for India</title></head></html>"
    assert fw.names_company(page, "Sarvam AI")
    assert not fw.names_company("<title>Domain for sale</title>", "Sarvam AI")
    assert fw.names_company('<meta property="og:site_name" content="Hume AI">', "Hume AI")
    assert fw.names_company("<title>Cr&#232;me &amp; Co &mdash; Hume</title>", "Hume")


def test_domain_cleanup():
    assert export_logos.domain("https://www.Example.ai/careers") == "example.ai"
    assert export_logos.domain("not a site") is None


def test_site_copy_is_up_to_date():
    # Run scripts/export_logos.py after editing websites in config/companies.yaml.
    assert export_logos.TARGET.read_text() == export_logos.exported()
