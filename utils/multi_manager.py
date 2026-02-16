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
        UPDATED: No longer returns "অপেক্ষা করুন". Shows prediction with warning.
        """
        results = self.get_recent_results(10)
        if not results: return prediction_data

        # 1. Consecutive Loss Prevention (Streak Tracking)
        loss_streak = 0
        for pred, actual, _ in results:
            if pred != actual and pred != "INITIAL":
                loss_streak += 1
            else:
                break
        
        if loss_streak >= 2:
            # prediction_data["prediction"] = "অপেক্ষা করুন" # REMOVED
            prediction_data["risk_alert"] = f"সতর্কতা: পরপর {loss_streak} বার লস হয়েছে। সাবধানে ট্রেড করুন।"
            prediction_data["confidence"] = max(10.0, prediction_data["confidence"] - 30.0)
            return prediction_data

        # 2. Volatility Check (Win Rate)
        wins = sum(1 for pred, actual, _ in results if pred == actual)
        win_rate = (wins / len(results)) * 100 if results else 100.0
        
        if win_rate < 40.0:
            # prediction_data["prediction"] = "অপেক্ষা করুন" # REMOVED
            prediction_data["risk_alert"] = "মার্কেট অত্যন্ত অস্থির। একুরেসি ৪০% এর নিচে। ট্রেড করা ঝুঁকিপূর্ণ।"
            prediction_data["confidence"] = max(10.0, win_rate)
            return prediction_data

        # 3. Single Loss Adjustment
        last_trade = results[0]
        if last_trade[0] != last_trade[1] and last_trade[0] != "INITIAL":
            prediction_data["risk_alert"] = "সতর্কতা: শেষ ট্রেডে লস হয়েছে। সাবধানে ট্রেড করুন।"
            prediction_data["confidence"] = max(10.0, prediction_data["confidence"] - 15.0)
            
        return prediction_data

    def cid_scanner_manager(self, prediction_data):
        """
        Manager 2: CID Scanner (Pro Mode)
        Analyzes mathematical trends and color patterns simultaneously.
        """
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT actual_result FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT 50")
            rows = cursor.fetchall()
        finally:
            conn.close()
        
        if not rows: return prediction_data
        results = ["B" if r[0] == "BIG" else "S" for r in reversed(rows)]
        
        def calculate_trend(data):
            if len(data) < 10: return 0
            numeric_data = [1 if x == "B" else 0 for x in data]
            sma_short = sum(numeric_data[-5:]) / 5
            sma_long = sum(numeric_data[-10:]) / 10
            return sma_short - sma_long

        trend_score = calculate_trend(results)
        
        def analyze_color_pattern(data):
            if len(data) < 6: return "NEUTRAL"
            last_6 = data[-6:]
            is_alternating = all(last_6[i] != last_6[i+1] for i in range(len(last_6)-1))
            if is_alternating: return "ALTERNATING"
            if last_6.count("B") >= 5: return "BIG_STREAK"
            if last_6.count("S") >= 5: return "SMALL_STREAK"
            return "NEUTRAL"

        color_pattern = analyze_color_pattern(results)
        
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
        
        streak = 1
        last_val = results[-1]
        for i in range(len(results)-2, -1, -1):
            if results[i] == last_val: streak += 1
            else: break
            
        if streak >= 3:
            dragon_type = "BIG" if last_val == "B" else "SMALL"
            prediction_data["dragon_detected"] = True
            if streak >= 3:
                prediction_data["prediction"] = dragon_type
                prediction_data["source"] = f"অ্যান্টি-ড্রাগন ট্রেন্ড ({streak}x)"
                prediction_data["dragon_alert"] = f"ড্রাগন শনাক্ত: {dragon_type} ট্রেন্ড অনুসরণ করা হচ্ছে।"
                prediction_data["confidence"] = min(98.0, 80.0 + (streak * 2))
                if streak >= 10:
                    prediction_data["dragon_alert"] = f"সতর্কতা: দীর্ঘ ড্রাগন ({streak}x)। ট্রেন্ড দুর্বল হতে পারে।"
                return prediction_data

        for length in range(min(10, len(results)), 2, -1):
            pattern = "".join(results[-length:])
            correction = self.model_a.get_correction(pattern)
            if correction:
                is_dragon = prediction_data.get("dragon_detected", False)
                reliability = correction["reliability"]
                if is_dragon:
                    dragon_type = "BIG" if results[-1] == "B" else "SMALL"
                    if correction["correct_result"] != dragon_type:
                        prediction_data["memory_alert"] = f"DRAGON PRIORITY: Blocked memory correction ({pattern} -> {correction['correct_result']}) to stay with {dragon_type} trend."
                        prediction_data["correction_status"] = "BLOCKED_BY_TREND"
                        continue
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

        error_matrix = self.model_a.patterns.get("error_matrix", {})
        for length in range(min(10, len(results)), 2, -1):
            pattern = "".join(results[-length:])
            pattern_stats = error_matrix.get(pattern)
            if pattern_stats:
                wins = pattern_stats.get("wins", 0)
                losses = pattern_stats.get("losses", 0)
                total = wins + losses
                if total >= 5:
                    win_rate = wins / total
                    if win_rate >= 0.8:
                        prediction_data["source"] = f"CID Win Zone ({pattern})"
                        prediction_data["confidence"] = min(99.0, prediction_data["confidence"] + 15.0)
                        prediction_data["detected_pattern"] = pattern
                        return prediction_data
                    elif win_rate <= 0.2:
                        prediction_data["prediction"] = "SMALL" if prediction_data["prediction"] == "BIG" else "BIG"
                        prediction_data["source"] = f"CID Reverse Zone ({pattern})"
                        prediction_data["risk_alert"] = f"Pattern {pattern} failing. Reversing for safety."
                        return prediction_data
        return prediction_data

    def probability_correlation_sensor(self, prediction_data):
        """
        Manager 3: Probability Correlation Sensor (Safety Layer)
        Calculates real-time probability and filters low-probability signals.
        UPDATED: No longer returns "অপেক্ষা করুন".
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
        
        pred = "B" if prediction_data["prediction"] == "BIG" else "S"
        total_count = len(results)
        pred_count = results.count(pred)
        frequency_prob = (pred_count / total_count) * 100
        
        correlation_score = 0
        if len(results) >= 4:
            current_pattern = "".join(results[-4:])
            pattern_matches = 0
            success_matches = 0
            for i in range(len(results) - 5):
                if "".join(results[i:i+4]) == current_pattern:
                    pattern_matches += 1
                    if results[i+4] == pred:
                        success_matches += 1
            if pattern_matches > 0:
                correlation_score = (success_matches / pattern_matches) * 100
            else:
                current_pattern_3 = "".join(results[-3:])
                for i in range(len(results) - 4):
                    if "".join(results[i:i+3]) == current_pattern_3:
                        pattern_matches += 1
                        if results[i+3] == pred:
                            success_matches += 1
                if pattern_matches > 0:
                    correlation_score = (success_matches / pattern_matches) * 100
                else:
                    correlation_score = frequency_prob
        
        final_prob = (frequency_prob * 0.3) + (correlation_score * 0.7)
        calibrated_confidence = min(prediction_data["confidence"], final_prob + 5.0)
        
        prediction_data["probability"] = round(final_prob, 1)
        prediction_data["confidence"] = round(calibrated_confidence, 1)
        
        # Safety Filter: REMOVED "অপেক্ষা করুন" logic
        if final_prob < 80.0:
            prediction_data["risk_alert"] = "সতর্কতা: জয়ের সম্ভাবনা ৮০% এর কম। সাবধানে ট্রেড করুন।"
            
        return prediction_data

    def process_signal(self, raw_signal):
        """
        Coordinates all managers with the new adaptive logic.
        """
        signal = self.risk_manager(raw_signal)
        signal = self.cid_scanner_manager(signal)
        signal = self.probability_correlation_sensor(signal)
        
        # Final Color Coding Logic (Silent Safety)
        # Risk High (Confidence < 75%) -> Orange
        # Risk Low (Confidence >= 75%) -> Green
        signal["warning_color"] = "Green" if signal["confidence"] >= 75.0 else "Orange"
        
        return signal
