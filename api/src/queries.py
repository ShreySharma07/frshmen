"""SQL shared by the API and the pipeline (scripts/publish_d1.py writes the filter snapshot).

ORDER_KEY must match the expression in idx_jobs_recent / idx_jobs_level exactly, or SQLite
sorts the whole table instead of walking the index.
"""

from __future__ import annotations

ORDER_KEY = "COALESCE(posted_at, first_seen_at)"
ORDER_BY = f"ORDER BY {ORDER_KEY} DESC, id DESC"
OPEN = "status = 'open'"

# Internship titles. Whole-word-ish LIKE patterns: "intern" must not match "Internal" or
# "International". SQLite's LIKE is case-insensitive for ASCII.
INTERN = ("(title LIKE '%intern' OR title LIKE '%intern %' OR title LIKE '%intern,%' OR title LIKE '%intern)%' "
          "OR title LIKE '%intern-%' OR title LIKE '%intern/%' OR title LIKE '%interns%' "
          "OR title LIKE '%trainee%' OR title LIKE '%apprentice%' OR title LIKE '%co-op%')")

# The page's Role filter. Plain SWE roles that passed the Python + AI/ML check count as AI/ML.
FAMILIES = {"ai_ml": ("ai_ml", "generic_swe"), "backend": ("backend",), "mobile": ("mobile",)}


def _family_sum(name: str) -> str:
    members = ", ".join(f"'{m}'" for m in FAMILIES[name])
    return f"'{name}', COALESCE(SUM(role_match = 1 AND role_family IN ({members})), 0)"


# One SELECT returning the whole snapshot as a JSON string, so the pipeline can store it with
# INSERT ... SELECT (one row written) and the API can run it live when no snapshot exists yet.
META_SELECT = f"""SELECT json_object(
  'total', (SELECT COUNT(*) FROM jobs WHERE {OPEN}),
  'levels', (SELECT json_group_object(level, n) FROM (SELECT level, COUNT(*) AS n FROM jobs WHERE {OPEN} GROUP BY level)),
  'internships', (SELECT COUNT(*) FROM jobs WHERE {OPEN} AND {INTERN}),
  'roles', (SELECT json_object('target', COALESCE(SUM(role_match = 1), 0), {', '.join(_family_sum(f) for f in FAMILIES)})
            FROM jobs WHERE {OPEN}),
  'companies', (SELECT json_group_array(json_object('company', company, 'n', n))
                FROM (SELECT company, COUNT(*) AS n FROM jobs WHERE {OPEN} GROUP BY company ORDER BY company)),
  'countries', (SELECT json_group_array(json_object('country', country, 'n', n))
                FROM (SELECT c.value AS country, COUNT(*) AS n FROM jobs, json_each(jobs.countries) AS c
                      WHERE {OPEN} GROUP BY c.value ORDER BY n DESC, c.value)),
  'cities', (SELECT json_group_array(json_object('city', city, 'n', n))
             FROM (SELECT c.value AS city, COUNT(*) AS n FROM jobs, json_each(jobs.cities) AS c
                   WHERE {OPEN} GROUP BY c.value ORDER BY n DESC, c.value))
) AS value"""


def snapshot_sql(now: str) -> str:
    """Statement the pipeline appends after its writes: refresh the filter snapshot."""
    return f"INSERT OR REPLACE INTO meta (key, value, updated_at) SELECT 'filters', ({META_SELECT}), '{now}';"
