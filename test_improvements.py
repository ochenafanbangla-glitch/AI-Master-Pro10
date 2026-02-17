import os
import sys
import json
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.model_a_core import ModelACore
from utils.multi_manager import MultiManagerSystem
from utils.db_manager import init_db, add_trade, clear_db

def test_logic():
    print("Starting Logic Test...")
    
    # Initialize
    if os.path.exists('database.db'):
        os.remove('database.db')
    init_db()
    
    model = ModelACore()
    manager = MultiManagerSystem(model, 'database.db')
    
    # 1. Test Incremental Learning (Bulk Input)
    print("\n1. Testing Incremental Learning...")
    pattern = ["BIG", "SMALL", "BIG", "SMALL", "BIG", "SMALL", "BIG", "SMALL", "BIG", "SMALL"]
    for i, res in enumerate(pattern):
        add_trade({
            "user_id": "test",
            "session_id": "test_session",
            "trade_id": f"test_{i}",
            "ai_prediction": "INITIAL",
            "ai_confidence": 0.0,
            "signal_source": "Test",
            "actual_result": res
        })
    
    success = model.train_from_db()
    print(f"Training Success: {success}")
    
    # 2. Test Prediction
    print("\n2. Testing Prediction...")
    signal = model.predict()
    print(f"Prediction: {signal['prediction']}, Confidence: {signal['confidence']}, Source: {signal['source']}")
    
    # 3. Test Loss Streak Analysis
    print("\n3. Testing Loss Streak Analysis...")
    # Add 3 losing trades
    for i in range(20, 23):
        add_trade({
            "user_id": "test",
            "session_id": "test_session",
            "trade_id": f"test_loss_{i}",
            "timestamp": f"2026-02-18 12:00:{i:02d}",
            "ai_prediction": "BIG",
            "ai_confidence": 80.0,
            "signal_source": "Test",
            "actual_result": "SMALL" # Loss
        })
    
    results = manager.get_recent_results(5)
    print(f"Recent Results: {results}")
    streak = manager.analyze_loss_streak()
    print(f"Current Loss Streak: {streak}")
    
    # 4. Test Master Selector Adaptation
    print("\n4. Testing Master Selector Adaptation...")
    raw_signal = model.predict()
    processed = manager.process_signal(raw_signal)
    print(f"Win Rate: {processed.get('current_win_rate')}%")
    print(f"Processed Prediction: {processed['prediction']}, Source: {processed['source']}")
    if processed['prediction'] == "SKIP/RISKY":
        print("SUCCESS: Master Selector correctly identified loss streak and suggested SKIP.")
    else:
        print("FAILURE: Master Selector did not adapt to loss streak.")

if __name__ == "__main__":
    test_logic()
