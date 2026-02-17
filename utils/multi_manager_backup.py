import sqlite3
import os
import json
from datetime import datetime
from utils.db_manager import get_db_connection

class MultiManagerSystem:
    def __init__(self, model_a, db_path):
        self.model_a = model_a
        self.db_path = db_path
        self.loss_threshold = 2
        self.max_loss_streak = 5
        self.win_zone_window = 20
        self.rolling_window = 10

    def get_recent_results(self, limit=50):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ai_prediction, actual_result, signal_source FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [tuple(row) for row in rows]
        finally:
            conn.close()

    def main_engine(self, prediction_data):
        """Engine 1: Normal Logic (Base AI Prediction)"""
        prediction_data["main_engine_pred"] = prediction_data["prediction"]
        return prediction_data

    def cid_scanner_engine(self, prediction_data):
        """Engine 2: CID Scanner (Reverse Logic / Pattern Trap Detector)"""
        results = self.get_recent_results(20)
        if not results: return prediction_data
        
        recent_data = ["B" if r[1] == "BIG" else "S" for r in reversed(results)]
        pattern = "".join(recent_data[-4:]) if len(recent_data) >= 4 else "".join(recent_data)
        
        error_matrix = self.model_a.patterns.get("error_matrix", {})
        pattern_stats = error_matrix.get(pattern, {"wins": 0, "losses": 0})
        
        if pattern_stats["losses"] > pattern_stats["wins"] and (pattern_stats["losses"] + pattern_stats["wins"]) >= 3:
            original = prediction_data["prediction"]
            reversed_pred = "SMALL" if original == "BIG" else "BIG"
            prediction_data["cid_engine_pred"] = reversed_pred
            prediction_data["cid_trap_detected"] = True
        else:
            prediction_data["cid_engine_pred"] = prediction_data["prediction"]
            prediction_data["cid_trap_detected"] = False
            
        return prediction_data

    def trend_follower_engine(self, prediction_data):
        """Engine 3: Trend Follower (Dragon / Streak Detector)"""
        results = self.get_recent_results(15)
        if not results: 
            prediction_data["trend_engine_pred"] = prediction_data["prediction"]
            return prediction_data
            
        recent_results = [r[1] for r in results]
        streak = 1
        last_val = recent_results[0]
        for i in range(1, len(recent_results)):
            if recent_results[i] == last_val:
                streak += 1
            else:
                break
        
        if streak >= 3:
            prediction_data["trend_engine_pred"] = last_val
            prediction_data["dragon_streak"] = streak
        else:
            prediction_data["trend_engine_pred"] = prediction_data["prediction"]
            prediction_data["dragon_streak"] = 0
            
        return prediction_data

    def calculate_volatility(self, results):
        """Calculates market volatility based on result changes."""
        if len(results) < 10: return 20, "STABLE"
        
        changes = 0
        recent_results = [r[1] for r in results[:10]]
        for i in range(len(recent_results) - 1):
            if recent_results[i] != recent_results[i+1]:
                changes += 1
        
        volatility_score = (changes / (len(recent_results) - 1)) * 100
        
        if volatility_score > 70:
            status = "EXTREME"
        elif volatility_score > 50:
            status = "VOLATILE"
        elif volatility_score > 30:
            status = "NORMAL"
        else:
            status = "STABLE"
            
        return round(volatility_score, 1), status

    def master_selector(self, signal):
        """Master Selector: Automatically checks which logic is winning and filters signals."""
        results = self.get_recent_results(20)
        
        vol_score, vol_status = self.calculate_volatility(results)
        signal["volatility_score"] = vol_score
        signal["volatility_status"] = vol_status
        
        completed_trades = [r for r in results if r[0] != "INITIAL"]
        if not completed_trades:
            win_rate = 100.0
        else:
            wins = sum(1 for pred, actual, source in completed_trades if pred == actual)
            win_rate = (wins / len(completed_trades)) * 100
            
        signal["current_win_rate"] = round(win_rate, 1)
        
        if win_rate < 50.0:
            signal["prediction"] = "SKIP/RISKY"
            signal["source"] = "Master Selector (Low Win Rate)"
            signal["confidence"] = win_rate
            signal["risk_alert"] = "সতর্কতা: উইন রেট ৫০% এর কম। ট্রেড এড়িয়ে চলুন (SKIP)।"
            return signal

        preds = [signal["main_engine_pred"], signal["cid_engine_pred"], signal["trend_engine_pred"]]
        big_count = preds.count("BIG")
        small_count = preds.count("SMALL")
        
        if big_count >= 2:
            signal["prediction"] = "BIG"
            signal["source"] = "Master Selector (Consensus: BIG)"
        elif small_count >= 2:
            signal["prediction"] = "SMALL"
            signal["source"] = "Master Selector (Consensus: SMALL)"
        
        if signal.get("dragon_streak", 0) >= 5:
            signal["prediction"] = signal["trend_engine_pred"]
            signal["source"] = f"Master Selector (Dragon Priority {signal['dragon_streak']}x)"
            signal["confidence"] = min(99.0, 85.0 + signal["dragon_streak"])
            
        return signal

    def process_signal(self, raw_signal):
        """Coordinates the 3-Engine Logic and Master Selector."""
        signal = self.main_engine(raw_signal)
        signal = self.cid_scanner_engine(signal)
        signal = self.trend_follower_engine(signal)
        signal = self.master_selector(signal)
        
        if signal["prediction"] == "SKIP/RISKY":
            signal["warning_color"] = "Orange"
        else:
            signal["warning_color"] = "Green" if signal["confidence"] >= 75.0 else "Orange"
            
        return signal
