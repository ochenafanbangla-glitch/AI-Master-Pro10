import sys
import os
import sqlite3
import json

# Add project root to path
sys.path.append(os.path.dirname(__file__))

from models.model_a_core import ModelACore
from utils.multi_manager import MultiManagerSystem
from utils.db_manager import init_db

def test_v6():
    print("--- Starting v6.0 Logic Validation ---")
    
    # 1. Initialize DB
    if os.path.exists('database.db'): os.remove('database.db')
    init_db()
    
    model = ModelACore()
    manager = MultiManagerSystem(model, 'database.db')
    
    # 2. Mock a historical error to populate Correction Table
    # Pattern "BBSS" -> Predicted "BIG" -> Actual "SMALL"
    print("\n[Step 1] Mocking historical error for pattern 'BBSS'...")
    # Increase reliability to 0.9 to trigger correction in test
    for _ in range(9):
        model.update_correction_table("BBSS", "BIG", "SMALL")
    
    correction = model.get_correction("BBSS")
    print(f"Correction Table Entry: {correction}")
    
    # 3. Test Case 1: Memory Correction (No Dragon)
    print("\n[Step 2] Testing Memory Correction (No Dragon)...")
    # Mock recent results ending in BBSS
    # We need to mock the DB for get_recent_results
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Results are ordered by timestamp DESC in MultiManager, then reversed.
    # So we insert them such that the most recent is "SMALL"
    # To avoid Risk Manager pause, we make predictions match actual results
    results = [
        ("t0", "BIG", "BIG", "2026-02-15 10:00:00"),
        ("t1", "BIG", "BIG", "2026-02-15 10:01:00"),
        ("t2", "SMALL", "SMALL", "2026-02-15 10:02:00"),
        ("t3", "SMALL", "SMALL", "2026-02-15 10:03:00")
    ]
    for tid, pred, actual, ts in results:
        cursor.execute("INSERT INTO trades (user_id, session_id, trade_id, timestamp, ai_prediction, ai_confidence, signal_source, actual_result) VALUES (?,?,?,?,?,?,?,?)",
                       ("test", "sess", tid, ts, pred, 80.0, "Test", actual))
    conn.commit()
    conn.close()
    
    raw_signal = {"prediction": "BIG", "confidence": 70.0, "source": "Base Model"}
    processed = manager.process_signal(raw_signal)
    print(f"Raw Prediction: BIG")
    print(f"Processed Prediction: {processed['prediction']}")
    print(f"Source: {processed['source']}")
    print(f"Alert: {processed.get('memory_alert')}")
    
    # 4. Test Case 2: Absolute Dragon Priority
    print("\n[Step 3] Testing Absolute Dragon Priority...")
    # Mock a Dragon (5x SMALL)
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades")
    dragon_results = ["SMALL"] * 5
    for i, r in enumerate(dragon_results):
        cursor.execute("INSERT INTO trades (user_id, session_id, trade_id, ai_prediction, ai_confidence, signal_source, actual_result) VALUES (?,?,?,?,?,?,?)",
                       ("test", "sess", f"d{i}", "SMALL", 80.0, "Test", r))
    conn.commit()
    conn.close()
    
    # Now the pattern is "SSSSS"
    # Mock a highly reliable correction that says "BIG" (Counter-trend)
    for _ in range(10):
        model.update_correction_table("SSSSS", "SMALL", "BIG")
    
    raw_signal = {"prediction": "SMALL", "confidence": 70.0, "source": "Base Model"}
    processed = manager.process_signal(raw_signal)
    print(f"Dragon Detected: {processed.get('dragon_detected')}")
    print(f"Dragon Type: SMALL")
    print(f"Memory Correction Suggests: BIG")
    print(f"Final Prediction: {processed['prediction']} (Should be SMALL)")
    print(f"Correction Status: {processed.get('correction_status')}")
    print(f"Alert: {processed.get('memory_alert')}")
    
    # 5. Test Case 3: Memory Expiry (Mocking old data)
    print("\n[Step 4] Testing Memory Expiry (Auto-Purge)...")
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Insert an old entry manually
    cursor.execute("INSERT INTO correction_table (pattern, incorrect_prediction, correct_result, last_seen) VALUES (?,?,?,?)",
                   ("OLD_PAT", "BIG", "SMALL", "2026-01-01 00:00:00"))
    conn.commit()
    
    # Trigger update_correction_table to run purge
    model.update_correction_table("NEW_PAT", "SMALL", "BIG")
    
    cursor.execute("SELECT * FROM correction_table WHERE pattern = 'OLD_PAT'")
    old_entry = cursor.fetchone()
    print(f"Old Entry Found: {old_entry is not None} (Should be False)")
    conn.close()
    
    print("\n--- Validation Complete ---")

if __name__ == "__main__":
    test_v6()
