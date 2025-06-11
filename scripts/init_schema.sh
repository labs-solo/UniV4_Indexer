#!/bin/bash
# Initialize the database schema for UniChain Swap-Fact pipeline

set -e

# Database connection parameters
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASSWORD:-secret}"

# Export password for psql
export PGPASSWORD

echo "Initializing database schema..."

# Wait for database to be ready
echo "Waiting for database to be ready..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
    echo "Database is not ready yet. Waiting..."
    sleep 2
done

echo "Database is ready. Creating schema..."

# Run DDL files
echo "Creating tables..."
for ddl_file in /workdir/sql/ddl/*.sql; do
    if [ -f "$ddl_file" ]; then
        echo "Running $ddl_file..."
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$ddl_file"
    fi
done

# Run view creation
echo "Creating views..."
for view_file in /workdir/sql/views/*.sql; do
    if [ -f "$view_file" ]; then
        echo "Running $view_file..."
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$view_file"
    fi
done

# Insert sample address labels
echo "Inserting sample address labels..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << EOF
INSERT INTO address_labels (address, label, flow_source, is_contract)
VALUES 
    ('\x1111111254fb6c44bac0bed2854e76f90643097d'::bytea, '1inch V4 Router', 'Aggregator', TRUE),
    ('\x68b3465833fb72a70ecdf485e0e4c7bd8665fc45'::bytea, 'Uniswap V3 Router', 'Aggregator', TRUE),
    ('\x0000000000000000000000000000000000000000'::bytea, 'Null Address', 'Other', FALSE)
ON CONFLICT (address) DO NOTHING;
EOF

echo "Schema initialization complete!" 