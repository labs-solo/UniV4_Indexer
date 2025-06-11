#!/usr/bin/env python3
"""
Fetch transaction receipts to get gas usage data
"""

import os
import psycopg2
from web3 import Web3

def connect_db():
    """Connect to PostgreSQL database"""
    database_url = os.getenv('DATABASE_URL', 'postgres://postgres:secret@postgres:5432/postgres')
    return psycopg2.connect(database_url)

def connect_web3():
    """Connect to Web3 RPC"""
    rpc_url = os.getenv('RPC_URL')
    if not rpc_url or '<YOUR_ALCHEMY_KEY>' in rpc_url:
        print("Warning: No valid RPC URL configured, skipping receipt fetching")
        return None
    return Web3(Web3.HTTPProvider(rpc_url))

def fetch_receipts():
    """Fetch transaction receipts for gas data"""
    print("Starting receipt fetching process...")
    
    # Connect to database
    conn = connect_db()
    cursor = conn.cursor()
    
    # Connect to Web3
    w3 = connect_web3()
    if not w3:
        print("Skipping receipt fetching - no RPC connection")
        return
    
    try:
        # Get transaction hashes that don't have gas data yet
        cursor.execute("""
            SELECT DISTINCT s.tx_hash 
            FROM raw_unichain_swaps s
            LEFT JOIN tx_gas g ON s.tx_hash = g.tx_hash
            WHERE g.tx_hash IS NULL
            LIMIT 100
        """)
        
        tx_hashes = cursor.fetchall()
        print(f"Fetching receipts for {len(tx_hashes)} transactions...")
        
        for (tx_hash_bytes,) in tx_hashes:
            tx_hash_hex = '0x' + tx_hash_bytes.hex()
            
            try:
                # Get transaction receipt
                receipt = w3.eth.get_transaction_receipt(tx_hash_hex)
                
                # Get transaction details for gas price
                tx = w3.eth.get_transaction(tx_hash_hex)
                
                gas_used = receipt.gasUsed
                gas_price = tx.gasPrice if hasattr(tx, 'gasPrice') else None
                
                # Insert into tx_gas table
                cursor.execute("""
                    INSERT INTO tx_gas (tx_hash, gas_used, gas_price)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (tx_hash) DO NOTHING
                """, (tx_hash_bytes, gas_used, gas_price))
                
                print(f"Fetched receipt for {tx_hash_hex}: {gas_used} gas")
                
            except Exception as e:
                print(f"Error fetching receipt for {tx_hash_hex}: {e}")
                continue
        
        conn.commit()
        print("Receipt fetching complete!")
        
    except Exception as e:
        print(f"Error in fetch_receipts: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    fetch_receipts() 