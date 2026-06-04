#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# Raven Database Initialization Script
# Automatically decides: setup or reset
# Run: ./db.sh
# ═══════════════════════════════════════════════════════════════

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
DB_NAME="raven"

echo "🔍 Checking database state..."

# Check if database exists
if psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" 2>/dev/null | grep -q 1; then
    echo "✓ Database '$DB_NAME' exists"
    
    # Check if tables exist
    if psql -d $DB_NAME -tAc "SELECT 1 FROM information_schema.tables WHERE table_name = 'frames'" 2>/dev/null | grep -q 1; then
        echo "✓ Tables exist"
        echo ""
        echo "🔄 Running reset.sh..."
        "$SCRIPT_DIR/reset.sh"
    else
        echo "✗ Tables missing"
        echo ""
        echo "🔧 Running setup.sh..."
        "$SCRIPT_DIR/setup.sh"
    fi
else
    echo "✗ Database '$DB_NAME' does not exist"
    echo ""
    echo "🚀 Running setup.sh..."
    "$SCRIPT_DIR/setup.sh"
fi
