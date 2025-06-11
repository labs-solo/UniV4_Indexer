#!/usr/bin/env python3
"""
ETL transformation script for enriching swap data
"""

import os
import requests
import pandas as pd
import psycopg2
from web3 import Web3
from datetime import datetime

def connect_db():
    """Connect to PostgreSQL database"""
    database_url = os.getenv('DATABASE_URL', 'postgres://postgres:secret@postgres:5432/postgres')
    return psycopg2.connect(database_url)

def connect_web3():
    """Connect to Web3 RPC"""
    rpc_url = os.getenv('RPC_URL')
    if not rpc_url or '<YOUR_ALCHEMY_KEY>' in rpc_url:
        print("Warning: No valid RPC URL configured")
        return None
    return Web3(Web3.HTTPProvider(rpc_url))

def get_swaps_from_hasura():
    """Fetch swap data from Hasura GraphQL API"""
    hasura_url = os.getenv('HASURA_URL', 'http://localhost:8080/v1/graphql')
    hooked_pool = os.getenv('HOOKED_POOL', '0x410723c1949069324d0f6013dba28829c4a0562f7c81d0f7cb79ded668691e1f')
    static_pool = os.getenv('STATIC_POOL', '0x51f9d63dda41107d6513047f7ed18133346ce4f3f4c4faf899151d8939b3496e')
    
    query = """
    query GetSwaps {
      raw_unichain_swaps(where: { pool_address: {_in: ["%s", "%s"]} }) {
        block_time
        tx_hash
        log_index
        pool_address
        token0
        token1
        amount0
        amount1
        sender
      }
    }
    """ % (hooked_pool, static_pool)
    
    try:
        response = requests.post(hasura_url, json={"query": query})
        data = response.json()
        
        if 'errors' in data:
            print(f"GraphQL errors: {data['errors']}")
            return pd.DataFrame()
        
        swaps = data.get('data', {}).get('raw_unichain_swaps', [])
        return pd.DataFrame(swaps)
    
    except Exception as e:
        print(f"Error fetching swaps from Hasura: {e}")
        return pd.DataFrame()

def enrich_with_gas(swaps_df, w3):
    """Enrich swaps with gas usage data"""
    if w3 is None:
        print("No Web3 connection, skipping gas enrichment")
        swaps_df['gas_used'] = 0
        return swaps_df
    
    # Convert tx_hash to hex if it's bytes
    if 'tx_hash' in swaps_df.columns:
        swaps_df['tx_hash_hex'] = swaps_df['tx_hash'].apply(
            lambda x: x.hex() if isinstance(x, bytes) else x
        )
    
    # Get unique transactions
    unique_txs = swaps_df['tx_hash_hex'].unique()
    gas_map = {}
    
    print(f"Fetching gas data for {len(unique_txs)} transactions...")
    
    for tx_hash in unique_txs:
        try:
            if not tx_hash.startswith('0x'):
                tx_hash = '0x' + tx_hash
            
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            gas_map[tx_hash] = receipt.gasUsed
            
        except Exception as e:
            print(f"Error fetching gas for {tx_hash}: {e}")
            gas_map[tx_hash] = 0
    
    # Map gas usage back to swaps
    swaps_df['gas_used'] = swaps_df['tx_hash_hex'].map(gas_map).fillna(0)
    
    return swaps_df

def enrich_with_prices(swaps_df):
    """Enrich swaps with USD prices"""
    # Sample price data - in production this would come from the price view
    # WBTC and WETH addresses on mainnet (for reference)
    wbtc_address = '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599'
    weth_address = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
    
    # Default prices
    price_map = {
        wbtc_address.lower(): 95000.0,  # WBTC ~$95k
        weth_address.lower(): 3500.0,   # ETH ~$3.5k
    }
    
    # Add price columns
    swaps_df['price0_usd'] = swaps_df['token0'].apply(
        lambda x: price_map.get(x.lower() if isinstance(x, str) else x, 0)
    )
    swaps_df['price1_usd'] = swaps_df['token1'].apply(
        lambda x: price_map.get(x.lower() if isinstance(x, str) else x, 0)
    )
    
    return swaps_df

def enrich_with_labels(swaps_df):
    """Enrich swaps with address labels"""
    # Load address labels
    try:
        labels_df = pd.read_csv('address_labels.csv')
        labels_df['address'] = labels_df['address'].str.lower()
        
        # Normalize sender addresses
        swaps_df['trader'] = swaps_df['sender'].apply(
            lambda x: x.lower() if isinstance(x, str) else x
        )
        
        # Merge with labels
        swaps_df = swaps_df.merge(
            labels_df[['address', 'flow_source', 'is_contract']], 
            left_on='trader', 
            right_on='address', 
            how='left'
        )
        
        # Fill missing values
        swaps_df['flow_source'] = swaps_df['flow_source'].fillna('Other')
        swaps_df['is_contract'] = swaps_df['is_contract'].fillna(False)
        
    except Exception as e:
        print(f"Error loading address labels: {e}")
        swaps_df['trader'] = swaps_df['sender']
        swaps_df['flow_source'] = 'Other'
        swaps_df['is_contract'] = False
    
    return swaps_df

def compute_hop_indices(swaps_df):
    """Compute hop indices for multi-hop trades"""
    if 'tx_hash' in swaps_df.columns and 'log_index' in swaps_df.columns:
        swaps_df = swaps_df.sort_values(['tx_hash', 'log_index'])
        swaps_df['hop_index'] = swaps_df.groupby('tx_hash').cumcount() + 1
    else:
        swaps_df['hop_index'] = 1
    
    return swaps_df

def export_to_csv(swaps_df, output_file):
    """Export enriched swaps to CSV"""
    # Select and order columns
    final_columns = [
        'block_time', 'tx_hash', 'log_index', 'pool_address',
        'token0', 'token1', 'amount0', 'amount1',
        'price0_usd', 'price1_usd', 'trader', 'is_contract',
        'flow_source', 'hop_index', 'gas_used'
    ]
    
    # Ensure all required columns exist
    for col in final_columns:
        if col not in swaps_df.columns:
            swaps_df[col] = 0 if col in ['hop_index', 'gas_used'] else ''
    
    # Export to CSV
    export_df = swaps_df[final_columns].copy()
    export_df.to_csv(output_file, index=False)
    print(f"Exported {len(export_df)} swaps to {output_file}")

def main():
    """Main ETL process"""
    print("Starting ETL transformation...")
    
    # Connect to services
    w3 = connect_web3()
    
    # Get swap data
    print("Fetching swap data...")
    swaps_df = get_swaps_from_hasura()
    
    if swaps_df.empty:
        print("No swap data found")
        return
    
    print(f"Processing {len(swaps_df)} swaps...")
    
    # Enrich data
    swaps_df = enrich_with_gas(swaps_df, w3)
    swaps_df = enrich_with_prices(swaps_df)
    swaps_df = enrich_with_labels(swaps_df)
    swaps_df = compute_hop_indices(swaps_df)
    
    # Export to CSV
    output_file = f"swap_facts_unichain_{datetime.now().strftime('%Y%m%d')}.csv"
    export_to_csv(swaps_df, output_file)
    
    print("ETL transformation complete!")

if __name__ == "__main__":
    main() 