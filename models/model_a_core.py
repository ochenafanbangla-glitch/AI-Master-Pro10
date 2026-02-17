import random
import numpy as np
import sqlite3
import os
import json
import time
import shutil
from utils.db_manager import get_db_connection

class ModelACore:
    """
    Model A (Father): Main live signal provider.
    Optimized for Vercel: Removed fcntl dependency and simplified file handling.
    """
    def __init__(self):
        self.name = "Model A (Advanced Lite AI)"
        self.is_vercel = "VERCEL" in os.environ
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))
        
        if self.is_vercel:
            # Use /tmp for all write operations on Vercel
            self.db_path = '/tmp/database.db'
            self.pattern_file = '/tmp/patterns.json'
            self.performance_file = '/tmp/strategy_performance.json'
            
            # Copy original files to /tmp for write access if they don't exist
            orig_pattern = os.path.join(os.path.dirname(__file__), 'patterns.json')
            orig_perf = os.path.join(os.path.dirname(__file__), 'strategy_performance.json')
            
            try:
                if not os.path.exists(self.pattern_file) and os.path.exists(orig_pattern):
                    shutil.copy2(orig_pattern, self.pattern_file)
                if not os.path.exists(self.performance_file) and os.path.exists(orig_perf):
                    shutil.copy2(orig_perf, self.performance_file)
            except Exception as e:
                print(f"Vercel File Copy Error: {e}")
        else:
            self.db_path = os.path.join(BASE_DIR, 'database.db')
            self.pattern_file = os.path.join(os.path.dirname(__file__), 'patterns.json')
            self.performance_file = os.path.join(os.path.dirname(__file__), 'strategy_performance.json')
        
        self.strategies = ["pattern", "trend", "fib", "rsi", "markov", "chaos", "streak_reversal"]
        self.patterns = self._load_patterns()
        self.strategy_weights = self._load_performance()

    def _load_patterns(self):
        """Loads AI pattern data from JSON file. Removed fcntl for Vercel compatibility."""
        default_data = {"patterns": {}, "markov_probabilities": {}, "error_matrix": {}}
        if os.path.exists(self.pattern_file):
            try:
                with open(self.pattern_file, 'r') as f:
                    data = json.load(f)
                    if not isinstance(data, dict): return default_data
                    if "patterns" not in data: data["patterns"] = {}
                    if "markov_probabilities" not in data: data["markov_probabilities"] = {}
                    if "error_matrix" not in data: data["error_matrix"] = {}
                    return data
            except Exception as e:
                print(f"Error loading patterns: {e}")
                return default_data
        return default_data

    def _save_patterns(self):
        """Saves AI pattern data to JSON file. Uses a temp file for safer writing."""
        try:
            temp_file = self.pattern_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.patterns, f)
            os.replace(temp_file, self.pattern_file)
        except Exception as e:
            print(f"Error saving patterns: {e}")

    def _load_performance(self):
        """Loads strategy performance weights."""
        default_weights = {s: 1.0 for s in self.strategies}
        if os.path.exists(self.performance_file):
            try:
                with open(self.performance_file, 'r') as f:
                    data = json.load(f)
                    for s in self.strategies:
                        if s not in data: data[s] = 1.0
                    return data
            except Exception as e:
                print(f"Error loading performance: {e}")
                return default_weights
        return default_weights

    def _save_performance(self):
        try:
            temp_file = self.performance_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.strategy_weights, f)
            os.replace(temp_file, self.performance_file)
        except Exception as e:
            print(f"Error saving performance: {e}")

    def update_correction_table(self, pattern, pred, actual):
        """Updates the persistent correction table in the database."""
        if not pattern or pred == actual: return
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM correction_table WHERE last_seen < datetime('now', '-7 days')")
            cursor.execute("SELECT occurrence_count, reliability_score FROM correction_table WHERE pattern = ?", (pattern,))
            row = cursor.fetchone()
            if row:
                count, score = row
                new_count = count + 1
                new_score = min(0.95, score + 0.05)
                cursor.execute("""
                    UPDATE correction_table 
                    SET occurrence_count = ?, reliability_score = ?, last_seen = CURRENT_TIMESTAMP, 
                        incorrect_prediction = ?, correct_result = ?
                    WHERE pattern = ?
                """, (new_count, new_score, pred, actual, pattern))
            else:
                cursor.execute("""
                    INSERT INTO correction_table (pattern, incorrect_prediction, correct_result, occurrence_count, reliability_score)
                    VALUES (?, ?, ?, 1, 0.5)
                """, (pattern, pred, actual))
            conn.commit()
        except Exception as e:
            print(f"Correction Table Update Error: {e}")
        finally:
            if conn: conn.close()

    def get_correction(self, pattern):
        """Retrieves a correction for a given pattern if it exists and is reliable."""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT correct_result, reliability_score FROM correction_table WHERE pattern = ?", (pattern,))
            row = cursor.fetchone()
            if row:
                return {"correct_result": row[0], "reliability": row[1]}
        except Exception as e:
            print(f"Error getting correction: {e}")
        finally:
            if conn: conn.close()
        return None

    def train_from_db(self, include_archived=True):
        """
        Analyzes historical data and evaluates strategy performance.
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT ai_prediction, actual_result, signal_source, timestamp FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp ASC")
            rows = cursor.fetchall()
            limit = 200
            if include_archived:
                cursor.execute("SELECT actual_result, ai_prediction FROM trades WHERE actual_result IS NOT NULL ORDER BY timestamp DESC LIMIT ?", (limit,))
            else:
                cursor.execute("SELECT actual_result, ai_prediction FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT ?", (limit,))
            results_rows = list(reversed(cursor.fetchall()))
            if len(rows) < 5:
                return False
            recent_rows = rows[-20:]
            perf = {s: {"wins": 0, "total": 0} for s in self.strategies}
            source_map = {
                "Pattern Analysis": "pattern",
                "Trend Detection": "trend",
                "Fibonacci Sequence": "fib",
                "RSI Analysis": "rsi",
                "Markov Chain Analysis": "markov",
                "Chaos Theory": "chaos",
                "Streak Reversal": "streak_reversal"
            }
            for pred, actual, source, _ in recent_rows:
                strat = source_map.get(source)
                if strat:
                    perf[strat]["total"] += 1
                    if pred == actual:
                        perf[strat]["wins"] += 1
            for s in self.strategies:
                if perf[s]["total"] > 0:
                    accuracy = perf[s]["wins"] / perf[s]["total"]
                    self.strategy_weights[s] = max(0.5, min(3.0, accuracy * 3.0))
            self._save_performance()
            results = ["B" if r[0] == "BIG" else "S" for r in results_rows]
            new_patterns = self.patterns.get("patterns", {}).copy()
            error_matrix = self.patterns.get("error_matrix", {}).copy()
            total_results = len(results)
            max_pattern_length = min(8, total_results - 1)
            for length in range(1, max_pattern_length + 1):
                start_idx = max(0, total_results - length - 50)
                for i in range(start_idx, total_results - length):
                    pattern = "".join(results[i:i+length])
                    next_val = results[i+length]
                    dist_from_end = total_results - (i + length)
                    weight = 10.0 if dist_from_end <= 5 else 5.0 if dist_from_end <= 15 else 1.0
                    if pattern not in new_patterns:
                        new_patterns[pattern] = {"B": 0, "S": 0}
                    new_patterns[pattern][next_val] += weight
                    actual = results_rows[i+length][0]
                    pred = results_rows[i+length][1]
                    if pattern not in error_matrix:
                        error_matrix[pattern] = {"wins": 0, "losses": 0}
                    inc = 5 if dist_from_end <= 5 else 2 if dist_from_end <= 15 else 1
                    if actual == pred:
                        error_matrix[pattern]["wins"] += inc
                    else:
                        error_matrix[pattern]["losses"] += inc
                        self.update_correction_table(pattern, pred, actual)
            if len(new_patterns) > 2000:
                sorted_patterns = sorted(new_patterns.items(), key=lambda x: sum(x[1].values()), reverse=True)
                new_patterns = dict(sorted_patterns[:2000])
            self.patterns["patterns"] = new_patterns
            self.patterns["error_matrix"] = error_matrix
            self.patterns["markov_probabilities"] = self._calculate_markov_probabilities(results)
            self._save_patterns()
            return True
        except Exception as e:
            print(f"Training error: {e}")
            return False
        finally:
            if conn: conn.close()

    def _calculate_markov_probabilities(self, results):
        if len(results) < 2: return {}
        transitions = {}
        for i in range(len(results)-1):
            curr = results[i]
            nxt = results[i+1]
            if curr not in transitions: transitions[curr] = {"B": 0, "S": 0}
            transitions[curr][nxt] += 1
        probs = {}
        for state, counts in transitions.items():
            total = sum(counts.values())
            probs[state] = {k: v/total for k, v in counts.items()}
        return probs

    def _get_last_n_results(self, n=60):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT actual_result FROM trades WHERE actual_result IS NOT NULL ORDER BY timestamp DESC LIMIT ?", (n,))
            rows = cursor.fetchall()
            return ["B" if r[0] == "BIG" else "S" for r in reversed(rows)]
        except Exception as e:
            print(f"Error getting results: {e}")
            return []
        finally:
            if conn: conn.close()

    def _calculate_volatility(self, results):
        if len(results) < 10: return 0.5
        changes = sum(1 for i in range(len(results)-1) if results[i] != results[i+1])
        return changes / (len(results)-1)

    def predict(self):
        """
        Predicts BIG or SMALL using multiple mathematical strategies.
        """
        last_results = self._get_last_n_results(60) 
        if not last_results:
            return {"prediction": "BIG", "confidence": 50.0, "source": "Fallback", "detected_pattern": "NONE"}
            
        volatility = self._calculate_volatility(last_results)
        current_pattern = "".join(last_results[-6:]) if len(last_results) >= 6 else "".join(last_results)
        
        votes = {"BIG": 0.0, "SMALL": 0.0}
        sources = {}

        # 1. Pattern Matching (PEM Enhanced)
        for length in range(min(8, len(last_results)), 1, -1):
            pat = "".join(last_results[-length:])
            if pat in self.patterns.get("patterns", {}):
                stats = self.patterns["patterns"][pat]
                total = sum(stats.values())
                if total > 0:
                    w = self.strategy_weights["pattern"] * (length / 4)
                    votes["BIG"] += (stats["B"] / total) * w
                    votes["SMALL"] += (stats["S"] / total) * w
                    sources["Pattern Analysis"] = "BIG" if stats["B"] > stats["S"] else "SMALL"
                    break

        # 2. Trend Detection
        if len(last_results) >= 10:
            recent = last_results[-5:]
            older = last_results[-10:-5]
            recent_b = recent.count("B")
            older_b = older.count("B")
            w = self.strategy_weights["trend"]
            if recent_b > older_b: 
                votes["BIG"] += 0.6 * w
                sources["Trend Detection"] = "BIG"
            elif recent_b < older_b: 
                votes["SMALL"] += 0.6 * w
                sources["Trend Detection"] = "SMALL"

        # 3. Markov Chain
        if last_results[-1] in self.patterns.get("markov_probabilities", {}):
            p = self.patterns["markov_probabilities"][last_results[-1]]
            w = self.strategy_weights["markov"]
            votes["BIG"] += p.get("B", 0.5) * w
            votes["SMALL"] += p.get("S", 0.5) * w
            sources["Markov Chain Analysis"] = "BIG" if p.get("B", 0) > p.get("S", 0) else "SMALL"

        # 4. Streak Reversal (Anti-Dragon)
        streak = 1
        for i in range(len(last_results)-2, -1, -1):
            if last_results[i] == last_results[-1]: streak += 1
            else: break
        if streak >= 4:
            w = self.strategy_weights["streak_reversal"] * (streak / 3)
            rev = "SMALL" if last_results[-1] == "B" else "BIG"
            votes[rev] += 0.8 * w
            sources["Streak Reversal"] = rev

        prediction = "BIG" if votes["BIG"] >= votes["SMALL"] else "SMALL"
        total_votes = votes["BIG"] + votes["SMALL"]
        confidence = (votes[prediction] / total_votes * 100) if total_votes > 0 else 50.0
        
        # Calibration
        if volatility > 0.7: confidence -= 10
        confidence = max(65.0, min(98.5, confidence))
        
        source = "Combined Matrix"
        for s, p in sources.items():
            if p == prediction:
                source = s
                break
                
        return {
            "prediction": prediction,
            "confidence": round(confidence, 1),
            "source": source,
            "detected_pattern": current_pattern if current_pattern else "NONE"
        }
