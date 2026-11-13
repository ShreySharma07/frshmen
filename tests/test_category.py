"""Every job gets one general category from its title (config/role_families.yaml), for people
whose roles aren't Shrey's. First listed category wins, so the order in the file matters."""

import pytest

from extract.category import CATEGORIES, category


@pytest.mark.parametrize("title,expected", [
    # AI/ML before platform/infra and data: "ML Platform Engineer" is an ML role.
    ("Machine Learning Engineer", "ai_ml"),
    ("ML Platform Engineer", "ai_ml"),
    ("Senior Data Scientist", "ai_ml"),
    ("Applied Scientist II", "ai_ml"),
    ("GenAI Engineer (LLM)", "ai_ml"),
    ("Research Scientist, Computer Vision", "ai_ml"),
    ("Data Engineer", "data"),
    ("Business Analyst", "data"),
    ("Analytics Engineer", "data"),
    ("Full Stack Developer", "fullstack"),
    ("Software Engineer, Full-Stack", "fullstack"),
    ("Frontend Engineer (React)", "frontend"),
    ("UI Developer", "frontend"),
    ("Backend Engineer - Payments", "backend"),
    ("Java Developer", "backend"),
    ("Golang Engineer", "backend"),
    ("Android Developer", "mobile"),
    ("iOS Engineer", "mobile"),
    ("React Native Developer", "mobile"),
    ("Site Reliability Engineer", "devops"),
    ("DevOps Engineer", "devops"),
    ("Cloud Infrastructure Engineer", "devops"),
    ("SDET", "qa"),
    ("QA Automation Engineer", "qa"),
    ("Security Engineer", "security"),
    ("Embedded Software Engineer", "hardware"),
    ("Firmware Engineer", "hardware"),
    ("VLSI Design Engineer", "hardware"),
    ("Product Manager", "product"),
    ("Product Designer", "design"),
    ("UX Researcher", "design"),
    ("Software Engineer (Python, Go, Ansible | 8-12 yrs)", "software"),
    ("SDE 1", "software"),
    ("Member of Technical Staff", "software"),
    ("Account Executive", "other"),
    ("Talent Acquisition Partner", "other"),
    ("Mechanical Engineer", "other"),
    ("Business Developer", "other"),
    ("Sales Engineer", "other"),
])
def test_category_from_title(title, expected):
    assert category(title) == expected


def test_every_result_is_a_listed_category():
    assert {"ai_ml", "software", "other"} <= set(CATEGORIES)
    assert category("Chef") in CATEGORIES
