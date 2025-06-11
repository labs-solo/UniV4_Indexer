-- Materialized view for daily token USD prices
-- This view will be refreshed daily to provide pricing data for enrichment

CREATE MATERIALIZED VIEW IF NOT EXISTS token_prices_usd_day AS
WITH 
-- Sample price data - in production this would be computed from swap data or oracle feeds
price_base AS (
    SELECT 
        CURRENT_DATE as price_date,
        '\x2260fac5e5542a773aa44fbcfedf7c193bc2c599'::bytea as token_address, -- WBTC
        95000.0 as price_usd  -- Placeholder price
    UNION ALL
    SELECT 
        CURRENT_DATE as price_date,
        '\xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'::bytea as token_address, -- WETH
        3500.0 as price_usd   -- Placeholder price
),
-- Generate historical dates (last 30 days)
date_range AS (
    SELECT 
        CURRENT_DATE - INTERVAL '1 day' * generate_series(0, 29) as price_date
),
-- Cross join to create price history
price_history AS (
    SELECT 
        dr.price_date,
        pb.token_address,
        pb.price_usd * (0.95 + random() * 0.1) as price_usd  -- Add some price variation
    FROM date_range dr
    CROSS JOIN (
        SELECT DISTINCT token_address, price_usd 
        FROM price_base
    ) pb
)
SELECT 
    price_date,
    token_address,
    price_usd,
    NOW() as created_at
FROM price_history
ORDER BY price_date DESC, token_address;

-- Create index for performance
CREATE UNIQUE INDEX IF NOT EXISTS idx_token_prices_date_token 
ON token_prices_usd_day (price_date, token_address);

-- Note: In production, this view would be populated with real price data
-- from DEX swaps, oracles, or external price feeds. The current implementation
-- provides placeholder data for testing purposes. 