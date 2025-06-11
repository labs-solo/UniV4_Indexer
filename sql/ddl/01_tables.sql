-- UniChain Swap-Fact Pipeline Database Schema
-- Tables for raw swap events, gas data, labels, and enriched facts

-- Raw swap events from the indexer
CREATE TABLE IF NOT EXISTS raw_unichain_swaps (
    block_time TIMESTAMP NOT NULL,
    block_number BIGINT NOT NULL,
    tx_hash BYTEA NOT NULL,
    log_index INTEGER NOT NULL,
    pool_address BYTEA NOT NULL,
    token0 BYTEA NOT NULL,
    token1 BYTEA NOT NULL,
    amount0 NUMERIC NOT NULL,
    amount1 NUMERIC NOT NULL,
    sender BYTEA NOT NULL,    -- msg.sender (trader or contract)
    origin BYTEA,             -- tx.origin (EOA)
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (tx_hash, log_index)
);

-- Transaction gas usage data
CREATE TABLE IF NOT EXISTS tx_gas (
    tx_hash BYTEA PRIMARY KEY,
    gas_used BIGINT NOT NULL,
    gas_price BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Address labels and contract flags
CREATE TABLE IF NOT EXISTS address_labels (
    address BYTEA PRIMARY KEY,
    label VARCHAR(255),
    flow_source VARCHAR(100) DEFAULT 'Other',
    is_contract BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Schema for the final fact table
CREATE SCHEMA IF NOT EXISTS labs_solo;

-- Final enriched swap facts table
CREATE TABLE IF NOT EXISTS labs_solo.pool_swap_fact_unichain (
    block_time TIMESTAMP NOT NULL,
    tx_hash BYTEA NOT NULL,
    log_index INTEGER NOT NULL,
    pool_address BYTEA NOT NULL,
    token0 BYTEA NOT NULL,
    token1 BYTEA NOT NULL,
    amount0 NUMERIC NOT NULL,
    amount1 NUMERIC NOT NULL,
    price0_usd NUMERIC DEFAULT 0,
    price1_usd NUMERIC DEFAULT 0,
    trader BYTEA NOT NULL,
    is_contract BOOLEAN DEFAULT FALSE,
    flow_source VARCHAR(100) DEFAULT 'Other',
    hop_index INTEGER DEFAULT 1,
    gas_used BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (tx_hash, log_index)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_raw_swaps_pool_time ON raw_unichain_swaps (pool_address, block_time);
CREATE INDEX IF NOT EXISTS idx_raw_swaps_time ON raw_unichain_swaps (block_time);
CREATE INDEX IF NOT EXISTS idx_raw_swaps_sender ON raw_unichain_swaps (sender);
CREATE INDEX IF NOT EXISTS idx_fact_time ON labs_solo.pool_swap_fact_unichain (block_time);
CREATE INDEX IF NOT EXISTS idx_fact_pool ON labs_solo.pool_swap_fact_unichain (pool_address);
CREATE INDEX IF NOT EXISTS idx_fact_trader ON labs_solo.pool_swap_fact_unichain (trader); 