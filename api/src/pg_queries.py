"""Postgres SQL shared by the API and the pipeline (scripts/publish_pg.py writes the snapshot).

ORDER_KEY must match the expression in jobs_recent_idx (db/postgres/0001_schema.sql) exactly,
or Postgres sorts every open job instead of walking the index.
"""

from __future__ import annotations

ORDER_KEY = "COALESCE(posted_at, first_seen_at)"
ORDER_BY = f"ORDER BY {ORDER_KEY} DESC, id DESC"
OPEN = "status = 'open'"

# Internship titles. Whole-word-ish ILIKE patterns: "intern" must not match "Internal" or
# "International". ILIKE ignores case.
INTERN = ("(title ILIKE '%intern' OR title ILIKE '%intern %' OR title ILIKE '%intern,%' OR title ILIKE '%intern)%' "
          "OR title ILIKE '%intern-%' OR title ILIKE '%intern/%' OR title ILIKE '%interns%' "
          "OR title ILIKE '%trainee%' OR title ILIKE '%apprentice%' OR title ILIKE '%co-op%')")

# The page's Role filter. Plain SWE roles that passed the Python + AI/ML check count as AI/ML.
FAMILIES = {"ai_ml": ("ai_ml", "generic_swe"), "backend": ("backend",), "mobile": ("mobile",)}


# Experience bands for every level of experience (docs/decisions.md, 2026-11-13): a job sits in
# the band of the minimum years it asks. Fresher-labelled jobs with no number are 0-1; a job
# labelled experienced (e.g. a senior title) never is.
BANDS = {
    "0-1": "level <> 'experienced' AND (level = 'fresher' OR yoe_min < 1)",
    "1-3": "yoe_min >= 1 AND yoe_min < 3",
    "3-5": "yoe_min >= 3 AND yoe_min < 5",
    "5-8": "yoe_min >= 5 AND yoe_min < 8",
    "8+": "yoe_min >= 8",
}
# "Also show jobs that state no years": juniors get the unlabelled ones only (precision first);
# from 3 years up, senior titles without a number are for them too.
BAND_UNSTATED = {band: ("level = 'maybe' AND yoe_min IS NULL" if band in ("0-1", "1-3")
                        else "level <> 'fresher' AND yoe_min IS NULL") for band in BANDS}


def _family(name: str) -> str:
    members = ", ".join(f"'{m}'" for m in FAMILIES[name])
    return f"'{name}', COUNT(*) FILTER (WHERE role_match AND role_family IN ({members}))"


def _list(col: str, key: str, order: str, source: str) -> str:
    return (f"(SELECT COALESCE(jsonb_agg(jsonb_build_object('{key}', {key}, 'n', n) ORDER BY {order}), '[]') "
            f"FROM (SELECT {col} AS {key}, COUNT(*) AS n FROM {source} GROUP BY 1) s)")


_OPEN_CARDS = f"job_cards WHERE {OPEN}"


def _within(years: int) -> str:
    return f"level = 'fresher' OR (yoe_min IS NOT NULL AND yoe_min <= {years}) OR (level = 'maybe' AND yoe_min IS NULL)"

# One SELECT returning the page's whole filter snapshot as JSON text; the pipeline stores it once
# per run (SNAPSHOT) and the API runs it live when no snapshot exists yet.
META_SELECT = f"""SELECT jsonb_build_object(
  'total', (SELECT COUNT(*) FROM {_OPEN_CARDS}),
  'levels', (SELECT COALESCE(jsonb_object_agg(level, n), '{{}}')
             FROM (SELECT level, COUNT(*) AS n FROM {_OPEN_CARDS} AND level IS NOT NULL GROUP BY level) s),
  'internships', (SELECT COUNT(*) FROM {_OPEN_CARDS} AND {INTERN}),
  -- Jobs open to someone with N years, counted the way /api/jobs?experience=0-N&include_unstated
  -- filters them (the landing page's "your experience" picker shows these).
  'within_years', (SELECT jsonb_build_object({', '.join(f"'{n}', COUNT(*) FILTER (WHERE {_within(n)})" for n in range(6))})
                   FROM {_OPEN_CARDS}),
  -- Open roles that sponsor a visa or offer relocation (the landing page's globe section).
  'visa_or_relocation', (SELECT COUNT(*) FROM {_OPEN_CARDS} AND (visa_sponsorship = 'yes'
                         OR evidence -> 'location' @> '[{{"kind": "relocation"}}]')),
  'roles', (SELECT jsonb_build_object('target', COUNT(*) FILTER (WHERE role_match),
                                      {', '.join(_family(f) for f in FAMILIES)}) FROM {_OPEN_CARDS}),
  'bands', (SELECT jsonb_build_object({', '.join(f"'{b}', COUNT(*) FILTER (WHERE {sql})" for b, sql in BANDS.items())})
             FROM {_OPEN_CARDS}),
  'categories', (SELECT COALESCE(jsonb_object_agg(category, n), '{{}}')
                 FROM (SELECT category, COUNT(*) AS n FROM {_OPEN_CARDS} AND category IS NOT NULL GROUP BY category) s),
  'companies', {_list('company', 'company', 'company', _OPEN_CARDS)},
  'countries', {_list('unnest(countries)', 'country', 'n DESC, country', _OPEN_CARDS)},
  'cities', {_list('unnest(cities)', 'city', 'n DESC, city', _OPEN_CARDS)}
)::text AS value"""

SNAPSHOT = ("INSERT INTO meta (key, value, updated_at) SELECT 'filters', (" + META_SELECT + ")::jsonb, now() "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at")
