import sqlite3
import os
import json
from datetime import datetime
from utils.db_manager import get_db_connection

class MultiManagerSystem:
    def __init__(self, model_a, db_path):
        self.model_a = model_a
        self.db_path = db_path
        self.loss_threshold = 3 # Increased for better stability
        self.max_loss_streak = 5
        self.win_zone_window = 20
        self.rolling_window = 10

    def get_recent_results(self, limit=50):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ai_prediction, actual_result, signal_source FROM trades WHERE is_archived = 0 ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [tuple(row) for row in rows]
        finally:
            conn.close()

    def analyze_loss_streak(self):
        """
        Analyzes the current loss streak to trigger auto-adaptation.
        """
        results = self.get_recent_results(10)
        if not results: return 0
        
        streak = 0
        # Results are ordered by timestamp DESC, so first item is most recent
        for pred, actual, source in results:
            if pred == "INITIAL" or actual is None:
                continue
            if pred != actual:
                streak += 1
            else:
                break
        return streak

    def main_engine(self, prediction_data):
        """Engine 1: Normal Logic (Base AI Prediction)"""
        prediction_data["main_engine_pred"] = prediction_data["prediction"]
        return prediction_data

    def cid_scanner_engine(self, prediction_data):
        """
        Engine 2: Enhanced CID Scanner (Reverse Logic / Pattern Trap Detector)
        """
        results = self.get_recent_results(30)
        if not results: 
            prediction_data["cid_engine_pred"] = prediction_data["prediction"]
            prediction_data["cid_trap_detected"] = False
            prediction_data["cid_confidence"] = 0
            return prediction_data
        
        recent_data = ["B" if r[1] == "BIG" else "S" for r in reversed(results)]
        error_matrix = self.model_a.patterns.get("error_matrix", {})
        
        # Adaptive threshold based on performance
        threshold = self.adaptive_threshold()
        
        for pattern_length in [5, 4, 3]:
            if len(recent_data) >= pattern_length:
                pattern = "".join(recent_data[-pattern_length:])
                pattern_stats = error_matrix.get(pattern, {"wins": 0, "losses": 0})
                
                total_occurrences = pattern_stats["wins"] + pattern_stats["losses"]
                
                if total_occurrences >= 5:
                    loss_rate = pattern_stats["losses"] / total_occurrences
                    
                    if loss_rate > threshold:
                        original = prediction_data["prediction"]
                        reversed_pred = "SMALL" if original == "BIG" else "BIG"
                        
                        confidence = loss_rate * 100
                        
                        prediction_data["cid_engine_pred"] = reversed_pred
                        prediction_data["cid_trap_detected"] = True
                        prediction_data["cid_confidence"] = round(confidence, 1)
                        prediction_data["cid_pattern_length"] = pattern_length
                        prediction_data["cid_occurrences"] = total_occurrences
                        prediction_data["cid_loss_rate"] = round(loss_rate * 100, 1)
                        
                        validation = self.multi_layer_validation(pattern, original)
                        prediction_data["cid_validation"] = validation
                        
                        return prediction_data
        
        prediction_data["cid_engine_pred"] = prediction_data["prediction"]
        prediction_data["cid_trap_detected"] = False
        prediction_data["cid_confidence"] = 0
        
        return prediction_data

    def multi_layer_validation(self, pattern, prediction):
        validations = []
        error_matrix = self.model_a.patterns.get("error_matrix", {})
        pattern_stats = error_matrix.get(pattern, {"wins": 0, "losses": 0})
        
        if pattern_stats["losses"] > pattern_stats["wins"]:
            validations.append({"layer": "error_matrix", "passed": True})
        
        correction = self.model_a.get_correction(pattern)
        if correction and correction["reliability"] > 0.6:
            validations.append({"layer": "correction_table", "passed": True})
        
        results = self.get_recent_results(10)
        if len(results) >= 5:
            changes = 0
            for i in range(len(results) - 1):
                if results[i][1] != results[i+1][1]:
                    changes += 1
            
            volatility = changes / (len(results) - 1)
            if volatility > 0.5:
                validations.append({"layer": "volatility", "passed": True})
        
        confidence = (len(validations) / 3) * 100
        
        return {
            "validated": len(validations) >= 2,
            "confidence": round(confidence, 1),
            "layers_passed": len(validations),
            "details": validations
        }

    def track_cid_performance(self):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN ai_prediction = actual_result THEN 1 ELSE 0 END) as correct
                FROM trades 
                WHERE signal_source LIKE '%CID%' 
                AND actual_result IS NOT NULL
                AND timestamp > datetime('now', '-7 days')
            """)
            
            row = cursor.fetchone()
            if row and row[0] > 0:
                accuracy = (row[1] / row[0]) * 100
                return {
                    "cid_accuracy": round(accuracy, 1),
                    "cid_total_signals": row[0],
                    "cid_correct_signals": row[1]
                }
        except Exception as e:
            print(f"Error tracking CID performance: {e}")
        finally:
            conn.close()
        
        return {"cid_accuracy": 0, "cid_total_signals": 0, "cid_correct_signals": 0}

    def adaptive_threshold(self):
        perf = self.track_cid_performance()
        if perf["cid_accuracy"] > 70:
            return 0.55
        elif perf["cid_accuracy"] > 60:
            return 0.60
        else:
            return 0.70

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
        """
        Enhanced Master Selector with Error Analysis and Auto-Adaptation.
        """
        results = self.get_recent_results(20)
        vol_score, vol_status = self.calculate_volatility(results)
        signal["volatility_score"] = vol_score
        signal["volatility_status"] = vol_status
        
        # Error Analysis: Check for loss streaks
        loss_streak = self.analyze_loss_streak()
        signal["loss_streak"] = loss_streak
        
        completed_trades = [r for r in results if r[0] != "INITIAL" and r[1] is not None]
        if not completed_trades:
            win_rate = 100.0
        else:
            wins = sum(1 for pred, actual, source in completed_trades if pred == actual)
            win_rate = (wins / len(completed_trades)) * 100
            
        signal["current_win_rate"] = round(win_rate, 1)
        
        # Auto-Adaptation: If losing streak > 3, force SKIP or switch mode
        if loss_streak >= 3 or win_rate < 45.0:
            signal["prediction"] = "SKIP/RISKY"
            signal["source"] = f"Master Selector (Loss Streak: {loss_streak})"
            signal["confidence"] = win_rate
            signal["risk_alert"] = f"সতর্কতা: টানা {loss_streak} বার ভুল প্রেডিকশন। ট্রেড এড়িয়ে চলুন।"
            return signal

        preds = [signal["main_engine_pred"], signal["cid_engine_pred"], signal["trend_engine_pred"]]
        big_count = preds.count("BIG")
        small_count = preds.count("SMALL")
        
        # Consensus Logic
        if big_count >= 2:
            signal["prediction"] = "BIG"
            signal["source"] = "Master Selector (Consensus: BIG)"
        elif small_count >= 2:
            signal["prediction"] = "SMALL"
            signal["source"] = "Master Selector (Consensus: SMALL)"
        
        # CID Scanner override with high confidence
        if signal.get("cid_trap_detected") and signal.get("cid_confidence", 0) > 75:
            validation = signal.get("cid_validation", {})
            if validation.get("validated", False):
                signal["prediction"] = signal["cid_engine_pred"]
                signal["source"] = f"CID Scanner (Trap Detected {signal['cid_confidence']}%)"
                signal["confidence"] = signal["cid_confidence"]
                signal["risk_alert"] = f"CID সতর্কতা: প্যাটার্ন ট্র্যাপ সনাক্ত ({signal['cid_loss_rate']}% ক্ষতি হার)"
        
        # Dragon Priority
        if signal.get("dragon_streak", 0) >= 5:
            signal["prediction"] = signal["trend_engine_pred"]
            signal["source"] = f"Master Selector (Dragon Priority {signal['dragon_streak']}x)"
            signal["confidence"] = min(99.0, 85.0 + signal["dragon_streak"])
            
        return signal

    def process_signal(self, raw_signal):
        signal = self.main_engine(raw_signal)
        signal = self.cid_scanner_engine(signal)
        signal = self.trend_follower_engine(signal)
        signal = self.master_selector(signal)
        
        if signal["prediction"] == "SKIP/RISKY":
            signal["warning_color"] = "Orange"
        else:
            signal["warning_color"] = "Green" if signal["confidence"] >= 75.0 else "Orange"
            
        return signal
