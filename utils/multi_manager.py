import sqlite3
import os
import json
from datetime import datetime

class MultiManagerSystem:
    def __init__(self, model_a, db_path):
        self.model_a = model_a
        self.db_path = db_path
        self.loss_threshold = 2  # Updated: Trigger pause after 2 losses
        self.max_loss_streak = 5 # Critical risk level
        self.win_zone_window = 20 # Window to identify win zones
        self.rolling_window = 10 # Rolling window for dynamic adaptation

    def get_recent_results(self, limit=20):
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ai_prediction, actual_result, signal_source FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return rows
        finally:
            conn.close()

    def analyze_performance(self):
        results = self.get_recent_results(20)
        if not results:
            return "STABLE", 0, 0.0

        streak = 0
        for pred, actual, _ in results:
            if pred != actual:
                streak += 1
            else:
                break
        
        wins = sum(1 for pred, actual, _ in results if pred == actual)
        win_rate = (wins / len(results)) * 100 if results else 0.0
        
        if streak >= 1:
            return "CAUTION", streak, win_rate
        return "STABLE", streak, win_rate

    def risk_manager(self, prediction_data):
        """
        Manager 1: Risk Manager
        Checks if the current market is too risky.
        Prevents consecutive losses.
        """
        results = self.get_recent_results(5)
        if not results: return prediction_data

        # Check for consecutive loss prevention
        last_trade = results[0]
        if last_trade[0] != last_trade[1]: # Last trade was a loss
            prediction_data["risk_alert"] = "সতর্কতা: পূর্ববর্তী ট্রেডে লস হয়েছে। একুরেসি অপ্টিমাইজ করা হচ্ছে।"
            # Reverse prediction if it matches the pattern that caused the last loss
            # This is a simple but effective way to avoid double losses in trending markets
            prediction_data["prediction"] = "SMALL" if prediction_data["prediction"] == "BIG" else "BIG"
            prediction_data["source"] = "রিস্ক ম্যানেজার (লস প্রতিরোধ)"
            prediction_data["confidence"] = min(95.0, prediction_data["confidence"] + 5.0)

        status, streak, win_rate = self.analyze_performance()
        if status == "CAUTION" and not prediction_data.get("risk_alert"):
            prediction_data["confidence"] = max(50.0, prediction_data["confidence"] - 10.0)
            prediction_data["risk_alert"] = "সতর্কতা: সাম্প্রতিক লস শনাক্ত হয়েছে। মার্কেট পর্যবেক্ষণ করা হচ্ছে।"
            
        return prediction_data

    def cid_scanner_manager(self, prediction_data):
        """
        Manager 2: CID Scanner (Pro Mode)
        Analyzes mathematical trends and color patterns simultaneously.
        """
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            cursor = conn.cursor()
            # Fetch more data for trend analysis
            cursor.execute("SELECT actual_result FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT 50")
            rows = cursor.fetchall()
        finally:
            conn.close()
        
        if not rows: return prediction_data
        results = ["B" if r[0] == "BIG" else "S" for r in reversed(rows)]
        
        # --- Pro Mode: Mathematical Trend & Color Pattern Analysis ---
        # 1. Mathematical Trend (Period Number Logic)
        # Since we don't have explicit period numbers, we use the sequence index as a proxy for trend
        def calculate_trend(data):
            if len(data) < 10: return 0
            # Simple moving average of 'B' (1) vs 'S' (0)
            numeric_data = [1 if x == "B" else 0 for x in data]
            sma_short = sum(numeric_data[-5:]) / 5
            sma_long = sum(numeric_data[-10:]) / 10
            return sma_short - sma_long # Positive means BIG trend, negative means SMALL trend

        trend_score = calculate_trend(results)
        
        # 2. Color Pattern Analysis (Alternating vs Streaks)
        def analyze_color_pattern(data):
            if len(data) < 6: return "NEUTRAL"
            last_6 = data[-6:]
            # Check for alternating pattern: B S B S B S
            is_alternating = all(last_6[i] != last_6[i+1] for i in range(len(last_6)-1))
            if is_alternating: return "ALTERNATING"
            
            # Check for streaks (Color clusters)
            if last_6.count("B") >= 5: return "BIG_STREAK"
            if last_6.count("S") >= 5: return "SMALL_STREAK"
            return "NEUTRAL"

        color_pattern = analyze_color_pattern(results)
        
        # Integrate Pro Mode findings into prediction
        if color_pattern == "ALTERNATING":
            prediction_data["prediction"] = "SMALL" if results[-1] == "B" else "BIG"
            prediction_data["source"] = "CID Pro (Alternating Pattern)"
            prediction_data["confidence"] = min(99.0, prediction_data["confidence"] + 10.0)
        elif color_pattern == "BIG_STREAK" and trend_score > 0:
            prediction_data["prediction"] = "BIG"
            prediction_data["source"] = "CID Pro (Trend + Color Sync)"
            prediction_data["confidence"] = min(99.0, prediction_data["confidence"] + 15.0)
        elif color_pattern == "SMALL_STREAK" and trend_score < 0:
            prediction_data["prediction"] = "SMALL"
            prediction_data["source"] = "CID Pro (Trend + Color Sync)"
            prediction_data["confidence"] = min(99.0, prediction_data["confidence"] + 15.0)
        
        # --- Dragon Breakout Logic with Adaptive Trend Following ---
        streak = 1
        last_val = results[-1]
        for i in range(len(results)-2, -1, -1):
            if results[i] == last_val: streak += 1
            else: break
            
        if streak >= 5:
            dragon_type = "BIG" if last_val == "B" else "SMALL"
            prediction_data["dragon_detected"] = True
            
            # Check win rate of recent counter-trend signals
            recent_trades = self.get_recent_results(10)
            counter_trades = [t for t in recent_trades if "Reverse" in t[2] or "Breakout" in t[2]]
            counter_wins = sum(1 for t in counter_trades if t[0] == t[1])
            counter_win_rate = (counter_wins / len(counter_trades)) if counter_trades else 1.0
            
            # Adaptive Signal: If counter-trend win rate is low (< 10%), follow the trend
            if counter_win_rate < 0.10:
                prediction_data["prediction"] = dragon_type
                prediction_data["source"] = f"CID Trend Follower ({streak}x)"
                prediction_data["dragon_alert"] = f"ADAPTIVE MODE: Counter-trend failing. Following {dragon_type} trend."
                prediction_data["confidence"] = max(prediction_data.get("confidence", 0), 85.0)
                prediction_data.pop("status", None) # Ensure it's not 'paused' or 'waiting'
                return prediction_data # Exit after adaptive trend following
            else:
                # Standard Breakout Logic
                if streak >= 8:
                    prediction_data["prediction"] = "SMALL" if dragon_type == "BIG" else "BIG"
                    prediction_data["source"] = f"CID Dragon Breakout ({streak}x)"
                    prediction_data["dragon_alert"] = f"DRAGON {streak}x: Breakout expected. Reversing signal."
                else:
                    prediction_data["dragon_alert"] = f"DRAGON {streak}x: Monitoring for breakout."

        # --- Smart Memory Correction (Persistent Correction Table) ---
        # Check for historical errors and apply corrections if trend allows
        # Convert results list back to full names for pattern matching if needed, 
        # but PCT uses full names like "BIG", "SMALL" or shorthand? 
        # Let's check ModelACore train_from_db.
        
        # In ModelACore.train_from_db: results = ["B" if r[0] == "BIG" else "S" for r in results_rows]
        # So patterns are "BBSS" etc.
        for length in range(min(10, len(results)), 2, -1):
            pattern = "".join(results[-length:])
            correction = self.model_a.get_correction(pattern)
            
            if correction:
                # Memory vs Trend Balance:
                # If a Dragon (streak >= 5) is active, trend has priority over memory
                is_dragon = prediction_data.get("dragon_detected", False)
                reliability = correction["reliability"]
                
                if is_dragon:
                    # Absolute Dragon Priority: During a dragon, memory correction is strictly secondary.
                    # We only allow memory correction if it ALIGNS with the dragon trend.
                    dragon_type = "BIG" if results[-1] == "B" else "SMALL"
                    if correction["correct_result"] != dragon_type:
                        prediction_data["memory_alert"] = f"DRAGON PRIORITY: Blocked memory correction ({pattern} -> {correction['correct_result']}) to stay with {dragon_type} trend."
                        prediction_data["correction_status"] = "BLOCKED_BY_TREND"
                        continue # Skip this correction, stay with trend
                
                # Apply correction if no dragon or if correction aligns with dragon
                old_pred = prediction_data["prediction"]
                new_pred = correction["correct_result"]
                
                if old_pred != new_pred:
                    prediction_data["prediction"] = new_pred
                    prediction_data["source"] = f"CID Smart Memory ({pattern})"
                    prediction_data["confidence"] = min(99.0, prediction_data["confidence"] + (reliability * 10))
                    prediction_data["memory_alert"] = f"Smart Correction: Pattern {pattern} historically leads to {new_pred}."
                    prediction_data["correction_status"] = "CORRECTED_BY_PCT"
                    prediction_data["original_prediction"] = old_pred
                    return prediction_data

        # --- Win Zone Identification ---
        # Prioritize patterns that worked in the last 20 signals
        error_matrix = self.model_a.patterns.get("error_matrix", {})
        for length in range(min(10, len(results)), 2, -1):
            pattern = "".join(results[-length:])
            pattern_stats = error_matrix.get(pattern)
            
            if pattern_stats:
                wins = pattern_stats.get("wins", 0)
                losses = pattern_stats.get("losses", 0)
                total = wins + losses
                if total >= 5: # Increased threshold for statistical significance
                    win_rate = wins / total
                    if win_rate >= 0.8:
                        prediction_data["source"] = f"CID Win Zone ({pattern})"
                        prediction_data["confidence"] = min(99.0, prediction_data["confidence"] + 15.0)
                        prediction_data["detected_pattern"] = pattern
                        return prediction_data
                    elif win_rate <= 0.2:
                        # High error rate zone - Reverse
                        prediction_data["prediction"] = "SMALL" if prediction_data["prediction"] == "BIG" else "BIG"
                        prediction_data["source"] = f"CID Reverse Zone ({pattern})"
                        prediction_data["risk_alert"] = f"Pattern {pattern} failing. Reversing for safety."
                        return prediction_data
        
        return prediction_data

    def probability_correlation_sensor(self, prediction_data):
        """
        Manager 3: Probability Correlation Sensor (Safety Layer)
        Calculates real-time probability and filters low-probability signals.
        """
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT actual_result FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT 100")
            rows = cursor.fetchall()
        finally:
            conn.close()
            
        if not rows: return prediction_data
        results = ["B" if r[0] == "BIG" else "S" for r in reversed(rows)]
        
        # Calculate Probability based on historical frequency of the predicted outcome
        pred = "B" if prediction_data["prediction"] == "BIG" else "S"
        total_count = len(results)
        pred_count = results.count(pred)
        
        # Base probability from frequency
        frequency_prob = (pred_count / total_count) * 100
        
        # Correlation check: How often does this prediction follow the current pattern?
        correlation_score = 0
        if len(results) >= 3:
            current_pattern = "".join(results[-3:])
            pattern_matches = 0
            success_matches = 0
            for i in range(len(results) - 4):
                if "".join(results[i:i+3]) == current_pattern:
                    pattern_matches += 1
                    if results[i+3] == pred:
                        success_matches += 1
            
            if pattern_matches > 0:
                correlation_score = (success_matches / pattern_matches) * 100
            else:
                correlation_score = frequency_prob # Fallback
        
        # Final Probability Calculation
        final_prob = (frequency_prob * 0.4) + (correlation_score * 0.6)
        prediction_data["probability"] = round(final_prob, 1)
        
        # Safety Filter: If probability is too low, mark as risky
        if final_prob < 45.0:
            prediction_data["risk_alert"] = "Low Probability Detected. Signal filtered for safety."
            prediction_data["confidence"] = max(30.0, prediction_data["confidence"] - 20.0)
            # We don't change the prediction, but we warn the user
            
        return prediction_data

    def process_signal(self, raw_signal):
        """
        Coordinates all managers with the new adaptive logic.
        """
        # Step 1: Risk Manager (Handles Pause/Loss Tracking)
        signal = self.risk_manager(raw_signal)
            
        # Step 2: CID Scanner (Adaptive Trend & Win Zone)
        signal = self.cid_scanner_manager(signal)
        
        # Step 3: Probability Correlation Sensor (Safety Layer)
        signal = self.probability_correlation_sensor(signal)
        
        return signal
