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
  'companies', {_list('company', 'company', 'company', _OPEN_CARDS)},
  'countries', {_list('unnest(countries)', 'country', 'n DESC, country', _OPEN_CARDS)},
  'cities', {_list('unnest(cities)', 'city', 'n DESC, city', _OPEN_CARDS)}
)::text AS value"""

SNAPSHOT = ("INSERT INTO meta (key, value, updated_at) SELECT 'filters', (" + META_SELECT + ")::jsonb, now() "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at")
