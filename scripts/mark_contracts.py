#!/usr/bin/env python3
"""
Mark contract addresses in the address_labels table
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
        print("Warning: No valid RPC URL configured, skipping contract marking")
        return None
    return Web3(Web3.HTTPProvider(rpc_url))

def mark_contracts():
    """Identify and mark contract addresses"""
    print("Starting contract marking process...")
    
    # Connect to database
    conn = connect_db()
    cursor = conn.cursor()
    
    # Connect to Web3
    w3 = connect_web3()
    if not w3:
        print("Skipping contract marking - no RPC connection")
        return
    
    try:
        # Get addresses that might be contracts but aren't marked yet
        cursor.execute("""
            SELECT DISTINCT s.sender 
            FROM raw_unichain_swaps s
            LEFT JOIN address_labels l ON s.sender = l.address
            WHERE l.address IS NULL OR l.is_contract = FALSE
            LIMIT 100
        """)
        
        addresses = cursor.fetchall()
        print(f"Checking {len(addresses)} addresses for contract code...")
        
        for (address_bytes,) in addresses:
            address_hex = '0x' + address_bytes.hex()
            
            try:
                # Check if address has code
                code = w3.eth.get_code(address_hex)
                is_contract = len(code) > 2  # More than just '0x'
                
                # Upsert into address_labels table
                cursor.execute("""
                    INSERT INTO address_labels (address, is_contract, flow_source)
                    VALUES (%s, %s, CASE WHEN %s THEN 'Contract' ELSE 'EOA' END)
                    ON CONFLICT (address) 
                    DO UPDATE SET 
                        is_contract = EXCLUDED.is_contract,
                        flow_source = CASE 
                            WHEN EXCLUDED.is_contract THEN 'Contract' 
                            ELSE COALESCE(address_labels.flow_source, 'EOA') 
                        END,
                        updated_at = NOW()
                """, (address_bytes, is_contract, is_contract))
                
                print(f"Marked {address_hex}: {'Contract' if is_contract else 'EOA'}")
                
            except Exception as e:
                print(f"Error checking address {address_hex}: {e}")
                continue
        
        conn.commit()
        print("Contract marking complete!")
        
    except Exception as e:
        print(f"Error in mark_contracts: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    mark_contracts() 