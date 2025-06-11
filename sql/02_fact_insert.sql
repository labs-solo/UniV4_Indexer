-- Insert enriched swap facts into the final fact table
-- This query joins raw swaps with prices, gas, and labels

INSERT INTO labs_solo.pool_swap_fact_unichain (
    block_time,
    tx_hash,
    log_index,
    pool_address,
    token0,
    token1,
    amount0,
    amount1,
    price0_usd,
    price1_usd,
    trader,
    is_contract,
    flow_source,
    hop_index,
    gas_used
)
SELECT 
    s.block_time,
    s.tx_hash,
    s.log_index,
    s.pool_address,
    s.token0,
    s.token1,
    s.amount0,
    s.amount1,
    COALESCE(p0.price_usd, 0) as price0_usd,
    COALESCE(p1.price_usd, 0) as price1_usd,
    s.sender as trader,
    COALESCE(l.is_contract, FALSE) as is_contract,
    COALESCE(l.flow_source, 'Other') as flow_source,
    ROW_NUMBER() OVER (PARTITION BY s.tx_hash ORDER BY s.log_index) as hop_index,
    g.gas_used
FROM raw_unichain_swaps s
-- Join with gas data
LEFT JOIN tx_gas g ON s.tx_hash = g.tx_hash
-- Join with token0 prices
LEFT JOIN token_prices_usd_day p0 ON s.token0 = p0.token_address 
    AND DATE(s.block_time) = p0.price_date
-- Join with token1 prices  
LEFT JOIN token_prices_usd_day p1 ON s.token1 = p1.token_address 
    AND DATE(s.block_time) = p1.price_date
-- Join with address labels
LEFT JOIN address_labels l ON s.sender = l.address
-- Only process swaps for our target pools
WHERE s.pool_address IN (
    '\x410723c1949069324d0f6013dba28829c4a0562f7c81d0f7cb79ded668691e1f'::bytea, -- hooked pool
    '\x51f9d63dda41107d6513047f7ed18133346ce4f3f4c4faf899151d8939b3496e'::bytea  -- static pool
)
-- Avoid duplicates
ON CONFLICT (tx_hash, log_index) DO NOTHING; 