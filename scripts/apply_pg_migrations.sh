#!/usr/bin/env bash
# Applies new db/postgres/*.sql files to Supabase Postgres, oldest first, once each.
# Usage: SUPABASE_DB_URL=postgres://... scripts/apply_pg_migrations.sh
#
# Each file runs in one transaction together with its row in schema_migrations, so a failing
# file leaves nothing half-applied and is retried on the next run.
set -euo pipefail

: "${SUPABASE_DB_URL:?set SUPABASE_DB_URL}"
# Anything else (a leading space, quotes, a "KEY=" prefix) makes psql silently try a local
# socket instead, with an error that doesn't mention the secret.
case "$SUPABASE_DB_URL" in
  postgres://* | postgresql://*) ;;
  *) echo "SUPABASE_DB_URL must start with postgresql:// (no quotes, spaces or prefix)" >&2; exit 1 ;;
esac
dir="$(dirname "$0")/../db/postgres"
psql_() { psql "$SUPABASE_DB_URL" -X -q -v ON_ERROR_STOP=1 "$@"; }

# RLS on with no policy: Supabase's public Data API can't read or change the ledger.
psql_ -c "CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now());
          ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY;"

applied="$(psql_ -At -c "SELECT filename FROM schema_migrations")"
for file in $(ls "$dir"/*.sql | sort); do
  name="$(basename "$file")"
  if grep -qxF "$name" <<<"$applied"; then
    echo "skip   $name"
    continue
  fi
  echo "apply  $name"
  psql_ --single-transaction -f "$file" \
        -c "INSERT INTO schema_migrations (filename) VALUES ('$name')"
done
