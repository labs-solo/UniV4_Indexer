#!/usr/bin/env python3
"""
Validation script for UniChain Swap-Fact pipeline
"""

import os
import psycopg2
import pandas as pd
from datetime import datetime, timedelta

def connect_db():
    """Connect to PostgreSQL database"""
    database_url = os.getenv('DATABASE_URL', 'postgres://postgres:secret@postgres:5432/postgres')
    return psycopg2.connect(database_url)

def check_swap_counts():
    """Check total swap counts across tables"""
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        # Count raw swaps
        cursor.execute("SELECT COUNT(*) FROM raw_unichain_swaps")
        raw_count = cursor.fetchone()[0]
        
        # Count enriched facts
        cursor.execute("SELECT COUNT(*) FROM labs_solo.pool_swap_fact_unichain")
        fact_count = cursor.fetchone()[0]
        
        print(f"Raw swaps: {raw_count}")
        print(f"Enriched facts: {fact_count}")
        
        if raw_count == 0:
            print("❌ No raw swaps found - indexer may not be working")
            return False
        
        if fact_count == 0:
            print("❌ No enriched facts found - ETL may not have run")
            return False
        
        if fact_count < raw_count:
            print(f"⚠️  Enriched facts ({fact_count}) < Raw swaps ({raw_count})")
            print("   This may be expected if ETL is still processing")
        else:
            print("✅ Swap counts look good")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking swap counts: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def check_data_freshness():
    """Check if data is fresh (recent swaps)"""
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        # Check latest swap timestamp
        cursor.execute("SELECT MAX(block_time) FROM raw_unichain_swaps")
        latest_swap = cursor.fetchone()[0]
        
        if latest_swap is None:
            print("❌ No swaps found")
            return False
        
        age = datetime.now() - latest_swap
        age_hours = age.total_seconds() / 3600
        
        print(f"Latest swap: {latest_swap} ({age_hours:.1f} hours ago)")
        
        if age_hours > 24:
            print("⚠️  Data is more than 24 hours old - indexer may be behind")
            return False
        else:
            print("✅ Data freshness looks good")
            return True
        
    except Exception as e:
        print(f"❌ Error checking data freshness: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def check_pool_coverage():
    """Check that both target pools have data"""
    conn = connect_db()
    cursor = conn.cursor()
    
    hooked_pool = bytes.fromhex('410723c1949069324d0f6013dba28829c4a0562f7c81d0f7cb79ded668691e1f')
    static_pool = bytes.fromhex('51f9d63dda41107d6513047f7ed18133346ce4f3f4c4faf899151d8939b3496e')
    
    try:
        # Check swaps per pool
        cursor.execute("""
            SELECT encode(pool_address, 'hex') as pool, COUNT(*) 
            FROM raw_unichain_swaps 
            WHERE pool_address IN (%s, %s)
            GROUP BY pool_address
        """, (hooked_pool, static_pool))
        
        pool_counts = cursor.fetchall()
        
        print("Pool coverage:")
        for pool_hex, count in pool_counts:
            pool_type = "Hooked" if pool_hex.startswith('410723') else "Static"
            print(f"  {pool_type} pool (0x{pool_hex}): {count} swaps")
        
        if len(pool_counts) == 2:
            print("✅ Both target pools have data")
            return True
        else:
            print("⚠️  Not all target pools have data")
            return False
        
    except Exception as e:
        print(f"❌ Error checking pool coverage: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def check_enrichment_quality():
    """Check quality of enriched data"""
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        # Check price enrichment
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN price0_usd > 0 THEN 1 END) as with_price0,
                COUNT(CASE WHEN price1_usd > 0 THEN 1 END) as with_price1,
                COUNT(CASE WHEN gas_used > 0 THEN 1 END) as with_gas
            FROM labs_solo.pool_swap_fact_unichain
        """)
        
        stats = cursor.fetchone()
        total, with_price0, with_price1, with_gas = stats
        
        if total == 0:
            print("❌ No enriched facts to validate")
            return False
        
        print(f"Enrichment quality (out of {total} swaps):")
        print(f"  Price0 enriched: {with_price0} ({100*with_price0/total:.1f}%)")
        print(f"  Price1 enriched: {with_price1} ({100*with_price1/total:.1f}%)")
        print(f"  Gas enriched: {with_gas} ({100*with_gas/total:.1f}%)")
        
        # Check address labeling
        cursor.execute("""
            SELECT 
                flow_source,
                COUNT(*) as count,
                COUNT(CASE WHEN is_contract THEN 1 END) as contracts
            FROM labs_solo.pool_swap_fact_unichain
            GROUP BY flow_source
            ORDER BY count DESC
        """)
        
        labels = cursor.fetchall()
        print("\nAddress labeling:")
        for flow_source, count, contracts in labels:
            print(f"  {flow_source}: {count} swaps ({contracts} from contracts)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking enrichment quality: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def check_hop_indices():
    """Check hop index logic for multi-hop trades"""
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        # Find transactions with multiple swaps
        cursor.execute("""
            SELECT encode(tx_hash, 'hex') as tx, COUNT(*) as swap_count
            FROM labs_solo.pool_swap_fact_unichain
            GROUP BY tx_hash
            HAVING COUNT(*) > 1
            ORDER BY swap_count DESC
            LIMIT 5
        """)
        
        multi_hop_txs = cursor.fetchall()
        
        if not multi_hop_txs:
            print("No multi-hop transactions found")
            return True
        
        print(f"Multi-hop transactions found: {len(multi_hop_txs)}")
        
        # Check hop indices for sample transaction
        tx_hash = multi_hop_txs[0][0]
        cursor.execute("""
            SELECT log_index, hop_index
            FROM labs_solo.pool_swap_fact_unichain
            WHERE tx_hash = decode(%s, 'hex')
            ORDER BY log_index
        """, (tx_hash,))
        
        hops = cursor.fetchall()
        print(f"Sample multi-hop tx {tx_hash}:")
        for log_idx, hop_idx in hops:
            print(f"  Log {log_idx} -> Hop {hop_idx}")
        
        # Validate hop indices are sequential
        hop_indices = [hop[1] for hop in hops]
        expected = list(range(1, len(hop_indices) + 1))
        
        if hop_indices == expected:
            print("✅ Hop indices are correct")
            return True
        else:
            print(f"❌ Hop indices incorrect: got {hop_indices}, expected {expected}")
            return False
        
    except Exception as e:
        print(f"❌ Error checking hop indices: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def check_csv_export():
    """Check if CSV export exists and has correct format"""
    today = datetime.now().strftime('%Y%m%d')
    csv_file = f"swap_facts_unichain_{today}.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV export not found: {csv_file}")
        return False
    
    try:
        df = pd.read_csv(csv_file)
        
        expected_columns = [
            'block_time', 'tx_hash', 'log_index', 'pool_address',
            'token0', 'token1', 'amount0', 'amount1',
            'price0_usd', 'price1_usd', 'trader', 'is_contract',
            'flow_source', 'hop_index', 'gas_used'
        ]
        
        print(f"CSV export found: {csv_file}")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
        
        missing_cols = set(expected_columns) - set(df.columns)
        if missing_cols:
            print(f"❌ Missing columns: {missing_cols}")
            return False
        
        print("✅ CSV format looks good")
        return True
        
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return False

def main():
    """Run all validation checks"""
    print("🔍 Running UniChain Swap-Fact Pipeline Validation")
    print("=" * 50)
    
    checks = [
        ("Swap counts", check_swap_counts),
        ("Data freshness", check_data_freshness),
        ("Pool coverage", check_pool_coverage),
        ("Enrichment quality", check_enrichment_quality),
        ("Hop indices", check_hop_indices),
        ("CSV export", check_csv_export),
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        print(f"\n📋 {check_name}:")
        try:
            if check_func():
                passed += 1
        except Exception as e:
            print(f"❌ Check failed with error: {e}")
    
    print("\n" + "=" * 50)
    print(f"Validation Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All validations passed! Pipeline is working correctly.")
        return True
    else:
        print("⚠️  Some validations failed. Check the issues above.")
        return False

if __name__ == "__main__":
    main() 