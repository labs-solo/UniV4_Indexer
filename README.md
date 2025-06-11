# UniChain Swap-Fact Pipeline

A production-ready pipeline for indexing, enriching, and exporting UniChain swap data from Uniswap v4 pools. Built using the stock Envio indexer with zero code modifications.

## 🎯 Overview

This pipeline indexes swap events from two specific UniChain WBTC/ETH pools (hooked and static), enriches the data with gas usage, USD prices, and trader classifications, and produces daily CSV files suitable for Dune Analytics.

### Target Pools
- **Hooked Pool**: `0x410723c1949069324d0f6013dba28829c4a0562f7c81d0f7cb79ded668691e1f`
- **Static Pool**: `0x51f9d63dda41107d6513047f7ed18133346ce4f3f4c4faf899151d8939b3496e`

## 🚀 Quick Start

See [SETUP.md](SETUP.md) for detailed setup instructions. Basic steps:

```bash
# 1. Clone and configure
cp env.template .env
# Edit .env with your RPC URLs

# 2. Start services
docker compose up -d

# 3. Initialize database
docker compose exec refresher sh scripts/init_schema.sh

# 4. Monitor indexing
docker compose logs -f hyperindex
```

## 📊 Pipeline Components

- **PostgreSQL Database**: Stores raw events and enriched data
- **HyperIndex Service**: Envio Uniswap v4 indexer for real-time sync
- **Refresher Service**: ETL cron job for daily enrichment and export

See [PIPELINE_SUMMARY.md](PIPELINE_SUMMARY.md) for complete architecture details.

## 📁 Project Structure

```
UniV4_Indexer/
├── env.template                 # Environment configuration template
├── docker-compose.yml          # Docker services orchestration
├── infra/hyperindex/           # Indexer configuration
├── sql/                        # Database schema and queries
├── scripts/                    # ETL and utility scripts
└── docs/                       # Additional documentation
```

## 🔍 Features

- Real-time indexing of UniChain swap events
- Automated data enrichment:
  - Gas usage from transaction receipts
  - USD prices via daily price view
  - Address labels and contract detection
  - Multi-hop trade sequencing
- Daily CSV exports with Dune-compatible schema
- Comprehensive validation suite
- Production-ready monitoring

## 📈 Output Schema

The pipeline produces daily CSV files (`swap_facts_unichain_YYYYMMDD.csv`) with the following schema:

| Column | Description |
|--------|-------------|
| `block_time` | Timestamp of the swap |
| `tx_hash` | Transaction hash |
| `log_index` | Event log index |
| `pool_address` | Pool ID (32-byte hex) |
| `token0`, `token1` | Token addresses |
| `amount0`, `amount1` | Swap amounts |
| `price0_usd`, `price1_usd` | USD prices |
| `trader` | Trader address (msg.sender) |
| `is_contract` | Boolean contract flag |
| `flow_source` | Trader classification |
| `hop_index` | Multi-hop sequence number |
| `gas_used` | Transaction gas usage |

## 🛠️ Operations

- Access GraphQL API: http://localhost:8080
- Monitor logs: `docker compose logs -f <service>`
- Manual refresh: `docker compose exec refresher sh scripts/daily_refresh.sh`
- Validate data: `docker compose exec refresher python3 scripts/validate_pipeline.py`

See [SETUP.md](SETUP.md) for troubleshooting and manual operations.

## 📚 Documentation

- [SETUP.md](SETUP.md): Quick setup guide and operations manual
- [PIPELINE_SUMMARY.md](PIPELINE_SUMMARY.md): Detailed architecture and implementation
- [queries.graphql](queries.graphql): Sample GraphQL queries for data access

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
