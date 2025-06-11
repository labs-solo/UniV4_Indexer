Great. I’ll now create a complete, step-by-step guide and supporting assets that show how to build a `swap_facts_unichain` CSV using the stock Envio Uniswap v4 indexer—without modifying its code. This includes setting up a public GitHub repo, extracting swap data for the two specified UniChain pools, enriching the data (gas, USD price, address labels), and producing a pipeline suitable for Dune upload.

I'll share a full Markdown playbook, GraphQL query sheets, enrichment logic in Python, validation checklist, and a minimal ops playbook.

I’ll get started and will notify you once the deliverables are ready.


# UniChain Swap-Fact Pipeline – Step-by-Step Guide

## 1. Setup Guide: Environment & Indexer Configuration

1. **Create a Project Repository:** Start a new GitHub repository for the pipeline (it will host your Docker configs, SQL, and scripts). Clone the repository locally and ensure you have **Docker** and **Docker Compose** installed. This pipeline will use Docker to run a Postgres database, the Envio Uniswap v4 indexer, and a refresher cron job.

2. **Include the Uniswap v4 Indexer:** Add the stock Envio **Uniswap v4 indexer** (from `enviodev/uniswap-v4-indexer`) to your project. For example, you can include it as a Git submodule or have a Docker build step that pulls the indexer code. In this guide, we'll use Docker Compose with a custom build:

   * Create a directory `infra/hyperindex/` in your repo. Inside it, add a `Dockerfile` that pulls the indexer code and installs dependencies (using Node 18+ and `pnpm`). Ensure this Dockerfile clones the indexer repository and sets up the build context.
   * Also in `infra/hyperindex/`, prepare a **configuration** (if required by the indexer). The Envio indexer may detect networks via environment variables. Since UniChain (chain ID 130) might not be predefined, explicitly configure it:

     * In the `.env` file (next step) set `CHAIN_ID=130` and provide RPC endpoints. The indexer will use these to connect to UniChain.
     * If the indexer needs a config YAML or mapping, place it in this directory. For example, a `config.yaml` can define the chain and contract addresses to index, and a `mappings.ts` can filter events. However, **no modification of the indexer core code** is needed – you use configuration and environment variables to point it at UniChain and the target pools.

3. **Configure Environment Variables:** Copy the sample environment file and fill in real values:

   ```bash
   cp .env.template .env
   ```

   Open `.env` and set the connection details:

   * **RPC URLs:** Provide the HTTP and WebSocket RPC endpoints for UniChain. For example, using an Alchemy API (if available) or public RPC:

     ```dotenv
     RPC_URL="https://unichain-mainnet.g.alchemy.com/v2/<YOUR_ALCHEMY_KEY>"
     RPC_WS="wss://unichain-mainnet.g.alchemy.com/v2/<YOUR_ALCHEMY_KEY>"
     ```

     (Alternatively, use a public RPC like `https://mainnet.unichain.org` if no Alchemy key.)

   * **Postgres DB:** Use default credentials or adjust as needed. For example:

     ```dotenv
     DATABASE_URL="postgres://postgres:secret@postgres:5432/postgres"
     POSTGRES_PASSWORD="secret"
     ```

     These will be used by the indexer and scripts to connect to the database.

   * **Chain and Pools:** Set the UniChain chain ID and the two target **pool IDs** (provided as 32-byte hex strings). For UniChain, use chain ID 130. For the pools, use the addresses given:

     ```dotenv
     CHAIN_ID=130
     HOOKED_POOL=0x410723c1949069324d0f6013dba28829c4a0562f7c81d0f7cb79ded668691e1f
     STATIC_POOL=0x51f9d63dda41107d6513047f7ed18133346ce4f3f4c4faf899151d8939b3496e
     ```

     Make sure these are exact and not quoted (they will be read by the indexer config). The `HOOKED_POOL` and `STATIC_POOL` correspond to the two WBTC/ETH 0.05% pools (one with a hook, one without).

   > **Note:** The `.env.template` in the project contains placeholders – you **must** replace them with real values (API keys, actual pool IDs) before running the pipeline. Leaving placeholder text will cause the indexer to fail to connect or not find the pools.

4. **Define Docker Compose Services:** In your repository root, create a `docker-compose.yml` that defines three services and a network (e.g., `etl_net`):

   * **Postgres Database:** Use the official Postgres 16 Alpine image. Mount a volume (e.g., `pgdata`) for persistence. Set the `POSTGRES_PASSWORD` from `.env`. For example:

     ```yaml
     services:
       postgres:
         image: postgres:16-alpine
         environment:
           - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
         volumes:
           - pgdata:/var/lib/postgresql/data
         networks:
           - etl_net
     ```

   * **HyperIndex (Uniswap v4 Indexer):** Build this service from the local `infra/hyperindex/` Dockerfile. This container will run the indexer code and stream swap events into Postgres in real time. Connect it to the same network and pass the environment variables:

     ```yaml
       hyperindex:
         build: ./infra/hyperindex
         env_file: .env
         depends_on:
           - postgres
         networks:
           - etl_net
         volumes:
           - hyperindex_cache:/app/cache    # cache ABI/metdata
     ```

     Ensure the Dockerfile installs Node, pulls the `enviodev/uniswap-v4-indexer` code, and runs `pnpm install`. It should invoke the indexer in dev mode (which typically starts Hasura and the indexer process). For example, the entrypoint might run `pnpm envio dev` (as per the indexer README) to launch Hasura and start indexing.

   * **Refresher (ETL Cron):** Use an Alpine image with cron to run enrichment and export tasks daily. For instance:

     ```yaml
       refresher:
         build:
           context: .
           dockerfile: Dockerfile.refresher
         env_file: .env
         volumes:
           - .:/workdir      # mount the repo files into the container
         depends_on:
           - postgres
         networks:
           - etl_net
     ```

     The `Dockerfile.refresher` will install Python and psql client, then set up a crontab. For example, to run the daily refresh at 02:00 UTC, it adds an entry like:

     ```Dockerfile
     RUN echo "0 2 * * * /workdir/scripts/daily_refresh.sh >> /workdir/logs/daily_refresh.log 2>&1" > /etc/crontabs/root
     ```

     with `crond` as the entrypoint. This means every day at 02:00 UTC the script will run inside the container.

   * **Volumes & Network:** Declare volumes for database and any cache (as above) and a dedicated Docker network for isolation:

     ```yaml
     networks:
       etl_net:
         driver: bridge
     volumes:
       pgdata:
       hyperindex_cache:
     ```

   Your repo should now have a structure like:

   ```text
   repo/
   ├─ infra/
   │   └─ hyperindex/        # Dockerfile and any indexer config/mapping
   ├─ sql/
   │   ├─ ddl/               # SQL schema files (tables, etc.)
   │   └─ views/             # SQL for materialized views (pricing)
   ├─ scripts/               # ETL scripts (init, refresh, export, etc.)
   ├─ docker-compose.yml     # Compose file defining services
   └─ .env                   # Environment variables (RPC URLs, keys, IDs)
   ```

   *(This mirrors Solo Labs’ internal project structure.)*

5. **Initialize the Database Schema:** Start up the services and set up the schema:

   ```bash
   docker compose up -d       # Launch Postgres, HyperIndex, and refresher
   docker compose exec refresher sh scripts/init_schema.sh   # Create tables/views
   ```

   The `init_schema.sh` script should use `psql` to run all SQL files in `sql/ddl/` and `sql/views/`. This will create:

   * A table `raw_unichain_swaps` for raw swap events (with columns as defined in the spec, e.g., tx hash, block time, token0, token1, amounts, sender, etc.).
   * A table `tx_gas` to store transaction gas usage.
   * A table `address_labels` to store address labels and a flag for contracts.
   * A materialized view `token_prices_usd_day` for daily token USD prices (to be populated from price feeds or swaps).
   * A final fact table `labs_solo.pool_swap_fact_unichain` with the schema for enriched swaps (13 columns such as prices, flow\_source, gas, etc.). This table will be filled by an ETL process later.
   * Appropriate indexes for performance (already defined in the SQL).

6. **Verify Indexer Operation:** Once the containers are running and schema is ready, monitor the indexer logs:

   ```bash
   docker compose logs -f hyperindex
   ```

   The **HyperIndex** service should connect to the UniChain RPC and begin indexing Uniswap v4 swap events. It streams real-time data into the `raw_unichain_swaps` table. On first run, it will **backfill** from the pools’ creation block up to the latest block (this might take some time, but the indexer is designed to sync quickly). You should see log output confirming it’s processing blocks and indexing swaps (e.g., messages like “Indexed swap: ... from pool ...”).

   Also, check the **refresher** logs (though initially it might be idle until 02:00 cron):

   ```bash
   docker compose logs -f refresher
   ```

   This ensures the cron scheduler is running. You can run a manual refresh (see Ops section) to test it.

7. **Access GraphQL Console:** The indexer launches a Hasura GraphQL UI on port 8080 by default. Open [http://localhost:8080](http://localhost:8080) in your browser. You should see the Hasura console connected to your Postgres. In the **GraphQL API** explorer, you can query the data to ensure everything is hooked up (see the next section for example queries).

   At this point, if backfill is complete, the `raw_unichain_swaps` table should contain swap records for the two pools. Verify by running a test query (e.g., count the rows or fetch a sample). Once confirmed, you have a running indexer pipeline capturing UniChain swaps into the database.

## 2. GraphQL Query Sheet: Retrieving Pools and Swaps

Use Hasura’s GraphQL API to query data. Below are sample queries to get pool info and swap events for the target pools:

* **Pool Metadata Lookup:** Retrieve basic metadata for a given pool (such as its tokens and fee tier). This assumes the indexer has a `pool` entity in the GraphQL schema. For example, if the indexer tracks Uniswap v4 pools, you might query by pool ID (address/bytes32):

  ```graphql
  query getPoolMetadata($poolId: Bytes!) {
    pool(id: $poolId) {
      id
      token0 {
        address
        symbol
        name
      }
      token1 {
        address
        symbol
        name
      }
      feeBps    # fee in basis points (e.g., 500 for 0.05%)
      totalSwapCount
      totalVolumeUSD
    }
  }
  ```

  *Usage:* Provide the full 32-byte pool ID as the `poolId` variable (e.g., `"0x410723c19490...691e1f"` for the hooked pool).

* **Swap Events for a Pool:** Query the raw swap events for one of the pools. For example, to fetch recent swaps from the *hooked* pool:

  ```graphql
  query recentSwaps($poolId: String!, $limit: Int!) {
    raw_unichain_swaps(
      where: { pool_address: { _eq: $poolId } }
      order_by: { block_time: desc }
      limit: $limit
    ) {
      block_time
      tx_hash
      log_index
      token0
      token1
      amount0
      amount1
      sender   # msg.sender of swap (trader or contract)
      origin   # transaction.origin (EOA that initiated the tx)
    }
  }
  ```

  Here `pool_address` is the 32-byte ID of the pool (as a hex string). This query will return the latest `$limit` swaps including their timestamps, transaction hashes, token addresses, amounts, and trader info. You can use similar queries for the static pool by changing the `poolId` variable (e.g., to the static pool’s ID).

* **Combined Query (both pools):** You can also fetch swaps from both pools in one query using an `_in` filter:

  ```graphql
  query allSwapsBothPools {
    raw_unichain_swaps(where: { pool_address: { _in: [
      "0x410723c1949069324d0f6013dba28829c4a0562f7c81d0f7cb79ded668691e1f",
      "0x51f9d63dda41107d6513047f7ed18133346ce4f3f4c4faf899151d8939b3496e"
    ]}}) {
      tx_hash
      block_time
      pool_address
      amount0
      amount1
    }
  }
  ```

  This will retrieve all swap events (careful, it could be a lot of data). In practice, you might add filters on `block_time` or use pagination for large datasets.

**Tips:** Using the Hasura console’s GraphiQL explorer, you can interactively build these queries and see the results. Make sure the GraphQL endpoint is accessible (by default, `http://localhost:8080/v1/graphql`). The indexer’s GraphQL schema includes tables for all indexed data, so you can also query the `token_prices_usd_day` view and the final fact table once it’s populated.

## 3. Transformation Script (ETL) – Enriching and Exporting Swaps

After indexing raw swaps, the next step is to **enrich** the data with gas usage, USD prices, address labels, and hop indices, then output the **`swap_facts_unichain.csv`** file. This can be done with a Python script (using GraphQL and RPC calls) or via SQL inside the database. We outline a Python-based approach here, referencing SQL for clarity:

**a. Pull raw swaps into pandas:** Use the Hasura GraphQL API (or direct SQL) to extract swap data for the two pools. For example, using Python’s `requests` library:

```python
import os, requests
import pandas as pd

HASURA_URL = os.getenv("HASURA_URL", "http://localhost:8080/v1/graphql")
query = """
query GetSwaps($hooked: String!, $static: String!) {
  raw_unichain_swaps(where: { pool_address: {_in: [$hooked, $static]} }) {
    block_time
    tx_hash
    log_index
    pool_address
    token0
    token1
    amount0
    amount1
    sender   # trader address (bytes)
  }
}
"""
variables = {
  "hooked": "0x410723c1949069324d0f6013dba28829c4a0562f7c81d0f7cb79ded668691e1f",
  "static": "0x51f9d63dda41107d6513047f7ed18133346ce4f3f4c4faf899151d8939b3496e"
}
resp = requests.post(HASURA_URL, json={"query": query, "variables": variables})
data = resp.json()["data"]["raw_unichain_swaps"]
swaps_df = pd.DataFrame(data)
```

This pulls all swap records for the two pool IDs into a DataFrame. (In practice, you might pull only new swaps since the last export for efficiency.)

**b. Fetch gas usage for each transaction:** The raw swaps data does not include `gas_used`. We obtain it via Ethereum JSON-RPC. For each unique transaction hash in the swaps, call `eth_getTransactionReceipt`. For example, using `web3.py`:

```python
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
# Ensure tx_hash is hex string:
swaps_df["tx_hash_hex"] = swaps_df["tx_hash"].apply(lambda x: x.hex() if isinstance(x, bytes) else x)
# Fetch gas for each unique tx
unique_txs = swaps_df["tx_hash_hex"].unique()
gas_used_map = {}
for tx in unique_txs:
    receipt = w3.eth.get_transaction_receipt(tx)
    gas_used_map[tx] = receipt.gasUsed

# Add gas_used column to DataFrame
swaps_df["gas_used"] = swaps_df["tx_hash_hex"].map(gas_used_map)
```

This uses an RPC provider (the same `RPC_URL` from .env) to get the receipt. If you prefer not to use web3, you can use `requests` to post a JSON-RPC payload for `eth_getTransactionReceipt`. *(Note: Solo Labs’ pipeline instead uses a helper script to batch fetch receipts and then COPYs results into a `tx_gas` table.)*

**c. Join USD price data:** We need to enrich each swap with `price0_usd` and `price1_usd`, the USD prices of token0 and token1 on the swap date. Solo’s approach is to maintain a **materialized view** `token_prices_usd_day` that stores a daily price for each token. This view is refreshed from known price sources (e.g. using WBTC/USDC and ETH/USDC pool data). You can query this view via GraphQL or SQL. For example:

```sql
SELECT token_address, price_date, price_usd
FROM token_prices_usd_day
WHERE token_address IN (<WBTC_ADDRESS>, <WETH_ADDRESS>)
  AND price_date = <swap_date>;
```

In Python, you could pull the prices into a DataFrame and merge. Since our two pools involve WBTC and WETH, fetch those prices for the dates of interest:

```python
# Suppose price_df has columns: token_address, price_date, price_usd
# Merge price for token0
swaps_df['date'] = pd.to_datetime(swaps_df['block_time']).dt.date
swaps_df = swaps_df.merge(price_df, how='left',
                          left_on=['token0','date'], 
                          right_on=['token_address','price_date'])
swaps_df.rename(columns={'price_usd': 'price0_usd'}, inplace=True)
# Merge price for token1 similarly (or use price_df pivoted by token)
...
# Fill any missing prices with 0 or carry over as appropriate
swaps_df['price0_usd'].fillna(0, inplace=True)
swaps_df['price1_usd'].fillna(0, inplace=True)
```

Under the hood, the price is computed via Uniswap’s methodology: e.g., `Token.derivedETH * Bundle.ethPriceUSD` for each token. In practice, the pipeline uses on-chain data: it derives WBTC→USD and WETH→USD rates (likely from stablecoin pools or oracle) daily, then multiplies by amounts to get USD values.

**d. Address labeling and contract flag:** The pipeline enriches each swap’s trader address with a **label** (flow source) and an **is\_contract** boolean:

* **Address labels CSV:** Prepare a CSV (or table) of known addresses with labels. Solo Labs combines Dune labels and custom labels for categories like *Aggregator (1inch, Matcha)*, *MEV bot*, *CEX*, etc. Include a column for `flow_source` and an `is_contract` flag if known. For example:

  ```csv
  address,label,flow_source,is_contract
  0x1111....,Uniswap V4 Router,Aggregator,TRUE
  0x2222....,JaneDoe EOA,EOA,FALSE
  0x3333....,CowSwap Settlement,Aggregator,TRUE
  ```
* **Mark contracts:** For any new trader addresses not in the label file, determine if they are contracts by checking bytecode. You can do this by calling `eth_getCode` on the address via RPC. If the result is non-empty (length > 2 hex chars), it’s a contract. Solo’s `mark_contracts.py` script automates this by scanning the `address_labels` table for entries with `is_contract = FALSE` and updating those that have code. You can run this periodically to keep the labels up-to-date.
* **Apply labels to swaps:** Join the labels with the swap DataFrame. In SQL, the enrichment does a left join from swaps to the `address_labels` table on the sender address. In pandas:

  ```python
  labels_df = pd.read_csv("address_labels.csv")
  labels_df['address_lower'] = labels_df['address'].str.lower()
  swaps_df['trader'] = swaps_df['sender'].str.lower()  # normalize addresses
  swaps_df = swaps_df.merge(labels_df, left_on='trader', right_on='address_lower', how='left')
  swaps_df['flow_source'] = swaps_df['flow_source'].fillna('Other')
  swaps_df['is_contract'] = swaps_df['is_contract'].fillna(False)
  ```

  Here we treat the swap’s `sender` as the **trader** (this is the `msg.sender` who triggered the swap, which could be an EOA or a contract like a router). After the merge, any address not found in the label list is classified as `'Other'` and assumed to be EOA unless we later find otherwise.

**e. Compute hop indices:** In multi-hop trades (where one transaction contains multiple swap events, e.g., a routed trade), we assign an **order** to each swap. The `hop_index` is `1` for the first swap in a transaction, `2` for the second, and so on. We can compute this by grouping swaps by `tx_hash` and sorting by `log_index` (since within a transaction, event log index indicates order):

```python
swaps_df = swaps_df.sort_values(['tx_hash','log_index'])
swaps_df['hop_index'] = swaps_df.groupby('tx_hash').cumcount() + 1
```

In SQL, this is done with `ROW_NUMBER() OVER (PARTITION BY tx_hash ORDER BY log_index)`.

**f. Assemble the final fact table:** Ensure the DataFrame now has all required **columns** for the fact CSV:

* `block_time` (timestamp),
* `tx_hash` (transaction hash),
* `log_index` (event index in tx),
* `pool_address` (pool ID),
* `token0`, `token1` (addresses of tokens in the pool),
* `amount0`, `amount1` (swap token amounts),
* `price0_usd`, `price1_usd` (daily price of each token in USD),
* `trader` (the swap’s `sender` address),
* `is_contract` (boolean flag for trader),
* `flow_source` (categorical label for trader),
* `hop_index` (as computed above),
* `gas_used` (from the transaction receipt).

Reorder and rename columns as needed to match the schema definition. For example:

```python
final_cols = ["block_time","tx_hash","log_index","pool_address",
              "token0","token1","amount0","amount1",
              "price0_usd","price1_usd",
              "trader","is_contract","flow_source",
              "hop_index","gas_used"]
fact_df = swaps_df[final_cols].copy()
fact_df.to_csv("swap_facts_unichain.csv", index=False)
```

This will produce `swap_facts_unichain.csv` in the current directory. The CSV will have a header row with the column names and each enriched swap as one line of data.

> **Note:** The official pipeline performs these enrichments in SQL for efficiency (see the `INSERT ... SELECT` in `02_fact_insert.sql` which joins the price view, labels, and gas table in one query). You can choose the approach that’s best for your team – for clarity, Python/pandas is easier to follow, whereas a SQL approach can run directly inside the database. Either way, the result should conform to the specified schema and values.

## 4. Validation Checklist (Comparing with Legacy Data)

Before deploying this pipeline, validate that its output aligns with Solo Labs’ legacy output and known data. Use the following checklist to verify data integrity:

* **Swap Count Matches:** After backfilling, query the total number of swaps in the fact table and compare it to known counts (e.g., from a legacy system or Dune). The count of rows in `pool_swap_fact_unichain` should match the total swaps observed in those two pools historically. If there's a discrepancy, investigate missing events or duplicates.

* **Volume and Price Sanity:** Calculate aggregate metrics (e.g., total volume in USD for each pool, daily volume) from the new fact table and compare them against the legacy dashboard or known Uniswap analytics. The sums of `amount0*price0_usd` (and similarly for token1) over all swaps should be in line with expected total volume. Large deviations could indicate pricing or amount scaling issues.

* **Multi-hop Trade Linking:** Identify a sample transaction that contains multiple swaps (a multi-hop trade). Verify that in the CSV, those swaps have incrementing `hop_index` values (e.g., 1, 2, 3 for a 3-hop trade) and share the same `tx_hash`. This confirms the hop indexing logic is correct.

* **Address Classification Accuracy:** Spot-check a few swap records for known addresses:

  * If `trader` is a known aggregator or contract, ensure `is_contract` is `TRUE` and `flow_source` matches the expected category (e.g., a 1inch router address labeled as "Aggregator").
  * If `trader` is an EOA (user wallet), verify `is_contract` is `FALSE` and `flow_source` is "EOA" or "Other". Also, if labels were provided from Dune, confirm those appear correctly.

* **Gas Usage Consistency:** Take a random transaction hash from the CSV and cross-verify the `gas_used` value via an explorer or by re-querying the RPC. It should match exactly. Also check that all swaps from the same transaction report the same `gas_used` (since gas is per transaction).

* **Schema and Format Checks:** Ensure the CSV has all required columns (15 columns as specified) with correct data types and no obvious placeholders. The timestamp (`block_time`) should be in a proper UTC format. Bytea fields (addresses, tx\_hash) might be encoded as hex in the CSV – ensure consistent encoding (e.g., lowercase hex string). The CSV should use UTF-8 encoding and have no extra delimiters or quoting issues.

* **Historical Totals vs Legacy:** If a legacy CSV or Dune table exists for the same data, compare totals for a given day or month. They should be nearly identical. Small differences might arise from slight price source variations or late arrivals of data, but there should be no systematic offset.

By checking off all the above, you validate that the new pipeline’s output is correct and complete, matching Solo’s current analytical needs. This gives confidence before automating the pipeline.

## 5. Ops Playbook: Maintenance, Scheduling, and Monitoring

Now that the pipeline is set up and validated, establish operational practices for ongoing runs:

* **Daily Refresh Cron:** The pipeline is configured to refresh daily at 02:00 UTC via cron (inside the `refresher` service). The `daily_refresh.sh` script encapsulates the ETL steps: catching up the indexer, refreshing the price view, updating labels, fetching new receipts, inserting new facts, and exporting the CSV. Ensure this cron is active. You can verify by checking the `refresher` logs after 02:00 UTC to see that each step ran in order (or run `docker compose exec refresher sh scripts/daily_refresh.sh` manually to test). Key steps in that script include:

  1. `hyperindex catchup` – sync indexer to the latest block (in case it fell behind).
  2. `REFRESH MATERIALIZED VIEW token_prices_usd_day;` – update price data.
  3. Import new address labels (if you have periodic label updates from Dune or others) and run the `mark_contracts.py` to flag any new contract addresses.
  4. Use the `fetch_receipts.py` (or similar) to get gas for new transactions and upsert into `tx_gas`.
  5. Run the SQL transform (or call the Python script) to insert new rows into the fact table.
  6. Export the full fact table to a dated CSV file.

  All these are automated in the script. Make sure to adjust cron timing or script if needed (for example, to avoid overlap if the backfill is large). If the dataset grows, monitor that the daily job finishes before the next day.

* **Hourly Delta Sync (Optional):** If your analytics require more frequent updates (hourly near-real-time data), you can schedule an **hourly job** to top-up the fact table:

  * **Indexer**: The HyperIndex service is continuous, so new swaps are indexed in real-time. However, the enrichment step (inserting into `pool_swap_fact_unichain`) is currently daily. You can run a lightweight version of `daily_refresh.sh` every hour (sans the CSV export) to insert recent swaps. For example, a separate cron job or GitHub Action can execute the SQL `02_fact_insert.sql` to insert any swaps from the last hour (it’s written to ignore duplicates via `ON CONFLICT DO NOTHING`).
  * Alternatively, query the `raw_unichain_swaps` for the last hour via GraphQL and manually enrich as in the script, then append to the CSV or database. This can be scripted if needed.
  * **Automation:** If using GitHub Actions for this, set up a **scheduled workflow** (cron schedule in GitHub Actions) that uses repository secrets for RPC and DB connection. The workflow could run a slim Docker container or Python environment that calls the Hasura API or runs SQL against the cloud DB to do the hourly insert and perhaps post a log or alert if something fails.

* **Health Checks:** It’s crucial to monitor the pipeline’s health:

  * **Indexer Liveness:** The HyperIndex container should always be running and catching up to the latest blocks. You can implement a simple health check by querying the latest indexed block from the database. For example, periodically run:

    ```sql
    SELECT MAX(block_number) FROM raw_unichain_swaps;
    ```

    and compare it to the current chain height (from an external RPC call). A large gap indicates the indexer is lagging or stopped. This check can be done via a cron or an external monitor. The indexer might also provide a status endpoint or you could parse its logs for errors.
  * **Hasura/GraphQL Health:** You can use Hasura’s health endpoint (e.g., `/healthz`) or simply perform a lightweight GraphQL query on a schedule to ensure the API responds. If not, the service may need a restart.
  * **Container Restart Policies:** Set `restart: unless-stopped` (or always) for the containers in docker-compose, so they come back up if the host reboots or if a crash occurs.
  * **Alerts:** Integrate with a monitoring tool or use GitHub Actions to send a notification (Slack/Email) if, for instance, no new swaps have been indexed in X hours during active trading times, or if the daily job fails (you could detect absence of the new CSV on a given day).

* **Daily CSV Exports & Storage:** Each run produces a CSV file named `swap_fact_YYYYMMDD.csv`. Decide where to store these:

  * If uploading to **Dune** is the goal, you can automate that via the Dune API or continue manual uploads. A manual step can be part of daily ops at 02:15 UTC to upload the new CSV to the Dune table (or use a script if Dune’s API allows programmatic updates).
  * Also consider archiving these CSVs. The guide suggests uploading them to a GitHub Release or cloud storage for backup. You can implement a GitHub Action that, whenever a new CSV is produced, attaches it to a release or pushes it to an S3 bucket. This ensures data is backed up outside the database.
  * Monitor the CSV file size. Dune has a 500 MB limit per file; if the daily CSV grows too large, implement a strategy (such as monthly partitioning of data into separate files).

* **GitHub CI/CD:** Leverage GitHub Actions for continuous integration:

  * Set up a **linting workflow** for your SQL and scripts (for example, using `sqlfluff` to lint SQL on pull requests). This helps maintain code quality.
  * Add a Docker build test action – e.g., build the `hyperindex` image in CI to ensure the Dockerfile is always up to date and the indexer builds correctly on changes.
  * If using GH Actions for scheduling as mentioned, ensure secrets (RPC URL, DB password) are stored in GitHub and the action runner has permissions to access them.

* **Manual Ops and Recovery:** Document procedures for common maintenance tasks:

  * How to re-run a **full backfill** if needed (e.g., if you had to wipe the DB). Typically: bring up fresh DB, run `hyperindex catchup` to backfill, then run `daily_refresh.sh` manually.
  * How to apply schema changes: via `scripts/init_schema.sh` or psql migrations if new columns or indexes are added.
  * Rotating the RPC if the current one becomes unreliable (update `.env` and restart indexer).
  * Checking contract bytecode for new addresses (run `mark_contracts.py` manually as needed if many new traders appear).

By following this playbook, a new engineer can maintain the UniChain swap-fact pipeline with confidence. The system will continuously index swaps, enrich the data, and publish daily CSVs for analysts — all while being robust and transparent. With clear monitoring and automation in place, the pipeline should require minimal manual intervention, yet any issues (data delays, service downtime) will be promptly detected and resolved. Enjoy your **UniChain swap-facts** pipeline, and happy indexing! 🚀
