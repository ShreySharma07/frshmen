"""Reading Shrey's HR and YC founder CSVs (api/src/contacts_csv.py): forgiving about headers,
strict about values, and every refused row says why."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api" / "src"))

from contacts_csv import parse  # noqa: E402

HR = """Full Name,Organisation,Designation,Email ID,Mobile,LinkedIn URL,City
Priya Sharma,Razorpay,Talent Acquisition Lead,Priya.Sharma@Razorpay.com,+91 98765 43210,https://linkedin.com/in/priyas,Bengaluru
Rahul Verma,Zoho,Campus Recruiter,,,,Chennai
,Nobody Inc,HR,x@y.com,,,
Bad Email,Acme,HR,not-an-email,,,
"""

FOUNDERS = """name,company,batch,website,email,notes
Ana Diaz,Brickanta,W25,https://brickanta.com,ana@brickanta.com,Construction AI; hiring engineers
"""


def test_reads_common_header_names_and_normalises_values():
    rows, errors = parse(HR, "hr")
    assert [r["name"] for r in rows] == ["Priya Sharma", "Rahul Verma"]
    priya = rows[0]
    assert priya == {"kind": "hr", "name": "Priya Sharma", "company": "Razorpay", "title": "Talent Acquisition Lead",
                     "email": "priya.sharma@razorpay.com", "phone": "+91 98765 43210",
                     "linkedin": "https://linkedin.com/in/priyas", "location": "Bengaluru", "yc_batch": None,
                     "company_url": None, "notes": None, "description": None}
    assert rows[1]["email"] is None  # a contact without an email is still a name to ask for


def test_refused_rows_say_which_row_and_why():
    _, errors = parse(HR, "hr")
    assert errors == [{"row": 4, "reason": "name is missing"}, {"row": 5, "reason": "email 'not-an-email' is not an address"}]


def test_founder_columns():
    rows, errors = parse(FOUNDERS, "founder")
    assert errors == []
    assert (rows[0]["yc_batch"], rows[0]["company_url"], rows[0]["notes"]) == ("W25", "https://brickanta.com", "Construction AI; hiring engineers")


def test_a_file_without_name_or_company_columns_is_refused_whole():
    rows, errors = parse("first,last\nA,B\n", "hr")
    assert rows == [] and errors[0]["row"] == 1 and errors[0]["reason"].startswith("no name column (expected one of: name, full name")


def test_bom_and_semicolons_from_excel_exports():
    rows, errors = parse("﻿Name;Company;Email\nA B;C Corp;a@c.com\n", "hr")
    assert errors == [] and rows[0]["email"] == "a@c.com"


def test_unsafe_links_are_dropped_not_kept():
    rows, _ = parse("name,company,linkedin\nA,B,javascript:alert(1)\n", "hr")
    assert rows[0]["linkedin"] is None


YC_EXPORT = ("Founder Name,Email,Company,Title,YC Batch,Company Status,LinkedIn,Twitter,Company Website,Email Domain\n"
             "Ana Diaz,ana@brickanta.com,Brickanta,Co-founder,W25,Active,https://linkedin.com/in/ana,https://x.com/ana,"
             "https://brickanta.com,brickanta.com\n")


def test_reads_a_yc_founders_export():
    # Shrey's YC list (2026-11-14): "Founder Name" was refused as "no name column".
    rows, errors = parse(YC_EXPORT, "founder")
    assert errors == []
    r = rows[0]
    assert (r["name"], r["company"], r["title"], r["email"], r["yc_batch"]) == ("Ana Diaz", "Brickanta", "Co-founder", "ana@brickanta.com", "W25")
    assert (r["linkedin"], r["company_url"], r["notes"]) == ("https://linkedin.com/in/ana", "https://brickanta.com", "Company status: Active")


def test_missing_column_error_lists_the_columns_found():
    _, errors = parse("first,last\nA,B\n", "hr")
    assert "found: first, last" in errors[0]["reason"]


def test_founder_description_and_tags_are_kept():
    rows, errors = parse("Founder Name,Company,One-liner,Tags,Industry\n"
                         "Ana Diaz,Pinecone,Vector database for AI apps,\"AI, Databases\",B2B\n", "founder")
    assert not errors
    assert rows[0]["description"] == "Vector database for AI apps"
    assert rows[0]["notes"] == "Tags: AI, Databases; Industry: B2B"
