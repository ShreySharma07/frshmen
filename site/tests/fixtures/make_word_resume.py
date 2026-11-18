"""Builds tests/fixtures/word-resume.pdf: a resume laid out the way Word and Google Docs users do
(bold title, dates on a right tab stop, the List Bullet style), exported to PDF by LibreOffice.
Run from site/: python3 tests/fixtures/make_word_resume.py  (needs python-docx and soffice)."""
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.shared import Cm, Pt

HERE = Path(__file__).parent
doc = Document()
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2)
style = doc.styles["Normal"]
style.font.name, style.font.size = "Liberation Sans", Pt(10.5)
RIGHT = Cm(17)


def para(text="", bold=False, size=None, italic=False, right=None, style=None):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(1)
    if right is not None:
        p.paragraph_format.tab_stops.add_tab_stop(RIGHT, WD_TAB_ALIGNMENT.RIGHT)
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if right is not None:
        p.add_run("\t" + right).italic = italic
    return p


para("Rohan Mehta", bold=True, size=20)
para("rohan.mehta@example.com | +91 98000 00000 | linkedin.com/in/rohanm")
para("EDUCATION", bold=True, size=12)
para("B.E. Information Technology", bold=True, right="2021 – 2025")
para("Sample College of Engineering", italic=True, right="Mumbai")
para("WORK EXPERIENCE", bold=True, size=12)
para("Backend Developer Intern", bold=True, right="Jan 2025 – Jun 2025")
para("Example Payments Pvt Ltd", italic=True, right="Mumbai")
para("Built a Django REST API for refunds used by 3 internal teams, with tests covering 85% of the code paths and alerts on failures.", style="List Bullet")
para("Moved nightly reports from cron to Celery, cutting their run time from 40 to 9 minutes.", style="List Bullet")
para("PROJECTS", bold=True, size=12)
para("Expense tracker app", bold=True, right="2024")
para("React Native app with a FastAPI backend; 200 users from my college.", style="List Bullet")
para("SKILLS", bold=True, size=12)
para("Python, Django, FastAPI, PostgreSQL, Docker, React Native")
docx = HERE / "word-resume.docx"
doc.save(docx)
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(HERE), str(docx)], check=True, capture_output=True)
docx.unlink()
print("wrote", HERE / "word-resume.pdf")
