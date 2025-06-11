# UniChain Swap-Fact Pipeline Setup

Quick setup guide for the UniChain Swap-Fact pipeline.

## Prerequisites

- Docker and Docker Compose
- Git
- RPC access to UniChain (Alchemy or public RPC)

## Quick Start

1. **Clone and configure environment:**
   ```bash
   cp env.template .env
   # Edit .env with your RPC URLs and any API keys
   ```

2. **Start the pipeline:**
   ```bash
   docker compose up -d
   ```

3. **Initialize the database:**
   ```bash
   docker compose exec refresher sh scripts/init_schema.sh
   ```

4. **Monitor the indexer:**
   ```bash
   docker compose logs -f hyperindex
   ```

5. **Access Hasura GraphQL Console:**
   Open http://localhost:8080 in your browser

6. **Run validation:**
   ```bash
   docker compose exec refresher python3 scripts/validate_pipeline.py
   ```

## Manual Operations

- **Run daily refresh manually:**
  ```bash
  docker compose exec refresher sh scripts/daily_refresh.sh
  ```

- **Export CSV manually:**
  ```bash
  docker compose exec refresher python3 scripts/etl_transform.py
  ```

- **Check database directly:**
  ```bash
  docker compose exec postgres psql -U postgres -c "SELECT COUNT(*) FROM raw_unichain_swaps;"
  ```

## Configuration Notes

- Update RPC URLs in `.env` with valid UniChain endpoints
- The indexer will backfill from block 1000000 by default
- Cron runs daily at 02:00 UTC for refresh and CSV export
- CSV files are saved as `swap_facts_unichain_YYYYMMDD.csv`
- Service ports:
  - `8080`: Hasura GraphQL interface
  - `9898`: Metrics endpoint (configurable via `METRICS_PORT`)
  - `5432`: PostgreSQL database

## Troubleshooting

- If no swaps appear, check RPC connectivity and pool addresses
- If enrichment fails, verify price view and address labels
- If port 9898 is in use, set `METRICS_PORT` in `.env` to a different port
- Monitor logs with `docker compose logs <service>`
- Check validation results to identify issues
- For port conflicts:
  ```bash
  # Check for running indexer processes
  pkill -f "envio dev"
  # Or change metrics port in .env
  echo "METRICS_PORT=9899" >> .env
  ```

## Architecture

- **postgres**: Database for raw and enriched data
- **hyperindex**: Uniswap v4 indexer (Envio) for real-time sync
- **refresher**: ETL service with cron for daily processing

The pipeline continuously indexes swap events, enriches them with gas/price/label data, and exports daily CSV files suitable for Dune upload. 