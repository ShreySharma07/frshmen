"""Postgres SQL shared by the API and the pipeline (scripts/publish_pg.py writes the snapshot).

ORDER_KEY must match the expression in jobs_recent_idx (db/postgres/0001_schema.sql) exactly,
or Postgres sorts every open job instead of walking the index.
queries.py keeps the SQLite versions for publish_d1.py until D1 is dropped.
"""

from __future__ import annotations

from queries import FAMILIES, INTERN as _SQLITE_INTERN

ORDER_KEY = "COALESCE(posted_at, first_seen_at)"
ORDER_BY = f"ORDER BY {ORDER_KEY} DESC, id DESC"
OPEN = "status = 'open'"
# SQLite's LIKE ignores ASCII case; Postgres needs ILIKE for the same patterns.
INTERN = _SQLITE_INTERN.replace(" LIKE ", " ILIKE ")


def _family(name: str) -> str:
    members = ", ".join(f"'{m}'" for m in FAMILIES[name])
    return f"'{name}', COUNT(*) FILTER (WHERE role_match AND role_family IN ({members}))"


def _list(col: str, key: str, order: str, source: str) -> str:
    return (f"(SELECT COALESCE(jsonb_agg(jsonb_build_object('{key}', {key}, 'n', n) ORDER BY {order}), '[]') "
            f"FROM (SELECT {col} AS {key}, COUNT(*) AS n FROM {source} GROUP BY 1) s)")


_OPEN_CARDS = f"job_cards WHERE {OPEN}"

# The same snapshot shape as queries.META_SELECT, so the page doesn't change.
META_SELECT = f"""SELECT jsonb_build_object(
  'total', (SELECT COUNT(*) FROM {_OPEN_CARDS}),
  'levels', (SELECT COALESCE(jsonb_object_agg(level, n), '{{}}')
             FROM (SELECT level, COUNT(*) AS n FROM {_OPEN_CARDS} AND level IS NOT NULL GROUP BY level) s),
  'internships', (SELECT COUNT(*) FROM {_OPEN_CARDS} AND {INTERN}),
  'roles', (SELECT jsonb_build_object('target', COUNT(*) FILTER (WHERE role_match),
                                      {', '.join(_family(f) for f in FAMILIES)}) FROM {_OPEN_CARDS}),
  'companies', {_list('company', 'company', 'company', _OPEN_CARDS)},
  'countries', {_list('unnest(countries)', 'country', 'n DESC, country', _OPEN_CARDS)},
  'cities', {_list('unnest(cities)', 'city', 'n DESC, city', _OPEN_CARDS)}
)::text AS value"""

SNAPSHOT = ("INSERT INTO meta (key, value, updated_at) SELECT 'filters', (" + META_SELECT + ")::jsonb, now() "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at")
