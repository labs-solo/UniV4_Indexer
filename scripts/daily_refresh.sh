#!/bin/bash
# Daily refresh script for UniChain Swap-Fact pipeline
# Runs enrichment and export tasks

set -e

# Database connection parameters
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASSWORD:-secret}"

# Export password for psql
export PGPASSWORD

echo "[$(date)] Starting daily refresh..."

# Step 1: Refresh price view
echo "[$(date)] Refreshing token prices..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "REFRESH MATERIALIZED VIEW token_prices_usd_day;"

# Step 2: Update address labels and contracts
echo "[$(date)] Updating address labels..."
python3 /workdir/scripts/mark_contracts.py

# Step 3: Fetch gas data for new transactions
echo "[$(date)] Fetching gas data..."
python3 /workdir/scripts/fetch_receipts.py

# Step 4: Insert new facts
echo "[$(date)] Inserting enriched swap facts..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f /workdir/sql/02_fact_insert.sql

# Step 5: Export to CSV
echo "[$(date)] Exporting to CSV..."
export_date=$(date +%Y%m%d)
export_file="/workdir/swap_facts_unichain_${export_date}.csv"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
COPY (
  SELECT 
    block_time,
    encode(tx_hash, 'hex') as tx_hash,
    log_index,
    encode(pool_address, 'hex') as pool_address,
    encode(token0, 'hex') as token0,
    encode(token1, 'hex') as token1,
    amount0,
    amount1,
    price0_usd,
    price1_usd,
    encode(trader, 'hex') as trader,
    is_contract,
    flow_source,
    hop_index,
    gas_used
  FROM labs_solo.pool_swap_fact_unichain
  ORDER BY block_time DESC, tx_hash, log_index
) TO STDOUT WITH CSV HEADER" > "$export_file"

echo "[$(date)] Export complete: $export_file"

# Step 6: Cleanup old exports (keep last 7 days)
find /workdir -name "swap_facts_unichain_*.csv" -mtime +7 -delete

echo "[$(date)] Daily refresh complete!" 