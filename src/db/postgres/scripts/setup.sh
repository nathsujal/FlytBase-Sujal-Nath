#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Raven PostgreSQL Setup Script
# Run: ./setup.sh
# ═══════════════════════════════════════════════════════════════

set -e  # Exit on error

# Configuration
DB_NAME="raven"
ADMIN_USER="admin"
ADMIN_PASS="admin_password"
WRITER_USER="writer"
WRITER_PASS="writer_password"
READER_USER="reader"
READER_PASS="reader_password"

echo "🚀 Starting PostgreSQL setup..."

# ═══════════════════════════════════════════════════════════════
# Step 1: Create database
# ═══════════════════════════════════════════════════════════════
echo "Step 1: Creating database..."

if psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
    echo "  Database '$DB_NAME' already exists"
else
    psql -d postgres -c "CREATE DATABASE $DB_NAME"
    echo "  Created database: $DB_NAME"
fi

# ═══════════════════════════════════════════════════════════════
# Step 2: Create users/roles
# ═══════════════════════════════════════════════════════════════
echo "Step 2: Creating users..."

psql -d $DB_NAME -c "
DO \$\$ BEGIN
    CREATE ROLE $ADMIN_USER WITH LOGIN PASSWORD '$ADMIN_PASS';
EXCEPTION WHEN duplicate_object THEN NULL;
END \$\$;
"

psql -d $DB_NAME -c "
DO \$\$ BEGIN
    CREATE ROLE $WRITER_USER WITH LOGIN PASSWORD '$WRITER_PASS';
EXCEPTION WHEN duplicate_object THEN NULL;
END \$\$;
"

psql -d $DB_NAME -c "
DO \$\$ BEGIN
    CREATE ROLE $READER_USER WITH LOGIN PASSWORD '$READER_PASS';
EXCEPTION WHEN duplicate_object THEN NULL;
END \$\$;
"
echo "  Users created: $WRITER_USER, $READER_USER"

# ═══════════════════════════════════════════════════════════════
# Step 3: Create tables
# ═══════════════════════════════════════════════════════════════
echo "Step 3: Creating tables..."

psql -d $DB_NAME -c "
CREATE TABLE IF NOT EXISTS frames (
    id BIGINT PRIMARY KEY,
    timestamp_sec DOUBLE PRECISION NOT NULL,
    captured_at TIMESTAMP,
    image_path TEXT
);

CREATE TABLE IF NOT EXISTS objects (
    id BIGINT PRIMARY KEY,
    label TEXT NOT NULL,
    summary_text TEXT
);

CREATE TABLE IF NOT EXISTS events (
    object_id BIGINT REFERENCES objects(id) ON DELETE CASCADE,
    frame_id BIGINT REFERENCES frames(id) ON DELETE CASCADE,
    event_description TEXT,
    PRIMARY KEY (object_id, frame_id)
);
"
echo "  Tables created: frames, objects, events"

# ═══════════════════════════════════════════════════════════════
# Step 4: Grant privileges
# ═══════════════════════════════════════════════════════════════
echo "Step 4: Granting privileges..."

psql -d $DB_NAME -c "
ALTER DATABASE $DB_NAME OWNER TO $ADMIN_USER;
GRANT USAGE ON SCHEMA public TO $WRITER_USER, $READER_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $WRITER_USER;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO $READER_USER;
"
echo "  Privileges granted"

echo ""
echo "✅ Database setup complete!"
echo ""
echo "Connection strings:"
echo "  Writer: postgresql://$WRITER_USER:$WRITER_PASS@localhost:5432/$DB_NAME"
echo "  Reader: postgresql://$READER_USER:$READER_PASS@localhost:5432/$DB_NAME"
