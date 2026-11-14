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
                     "company_url": None, "notes": None}
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
    assert rows == [] and errors == [{"row": 1, "reason": "no name column (expected one of: name, full name, contact name)"}]


def test_bom_and_semicolons_from_excel_exports():
    rows, errors = parse("﻿Name;Company;Email\nA B;C Corp;a@c.com\n", "hr")
    assert errors == [] and rows[0]["email"] == "a@c.com"


def test_unsafe_links_are_dropped_not_kept():
    rows, _ = parse("name,company,linkedin\nA,B,javascript:alert(1)\n", "hr")
    assert rows[0]["linkedin"] is None
