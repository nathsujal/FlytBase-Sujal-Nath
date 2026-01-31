#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# FlytBase PostgreSQL Reset Script
# Drops indexes and truncates all tables for a clean run
# Run: ./reset.sh
# ═══════════════════════════════════════════════════════════════

set -e  # Exit on error

# Configuration
DB_NAME="flytbase"

echo "🔄 Resetting FlytBase database..."

# Check if database exists
if ! psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
    echo "❌ Database '$DB_NAME' does not exist!"
    echo "   Run ./setup.sh first to create it."
    exit 1
fi

# Drop all custom indexes (except primary keys and unique constraints)
echo "Dropping indexes..."
psql -d $DB_NAME -c "
DO \$\$
DECLARE
    idx RECORD;
BEGIN
    FOR idx IN
        SELECT indexname, tablename
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND indexname NOT LIKE '%_pkey'
        AND indexname NOT LIKE '%_unique'
    LOOP
        EXECUTE 'DROP INDEX IF EXISTS ' || quote_ident(idx.indexname);
        RAISE NOTICE 'Dropped index: %', idx.indexname;
    END LOOP;
END \$\$;
"

# Truncate all tables
echo "Truncating tables..."
psql -d $DB_NAME -c "TRUNCATE events, objects, frames RESTART IDENTITY CASCADE"

echo ""
echo "✅ Reset complete!"
echo "   - All custom indexes dropped"
echo "   - All tables truncated"
