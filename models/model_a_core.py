import random
import numpy as np
import sqlite3
import os
import json
try:
    import fcntl
except ImportError:
    fcntl = None
import time

class ModelACore:
    """
    Model A (Father): Main live signal provider.
    Advanced Lite AI: Uses mathematical pattern analysis with adaptive performance weighting.
    Enhanced with CID Scanner Pattern Error Matrix (PEM) and Rolling Window Learning.
    """
    def __init__(self):
        self.name = "Model A (Advanced Lite AI)"
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')
        self.pattern_file = os.path.join(os.path.dirname(__file__), 'patterns.json')
        self.performance_file = os.path.join(os.path.dirname(__file__), 'strategy_performance.json')
        
        self.strategies = ["pattern", "trend", "fib", "rsi", "markov", "chaos", "streak_reversal"]
        self.patterns = self._load_patterns()
        self.strategy_weights = self._load_performance()

    def _load_patterns(self):
        """Loads AI pattern data from JSON file with file locking for safety."""
        default_data = {"patterns": {}, "markov_probabilities": {}, "error_matrix": {}}
        if os.path.exists(self.pattern_file):
            try:
                with open(self.pattern_file, 'r') as f:
                    if fcntl: fcntl.flock(f, fcntl.LOCK_SH)
                    data = json.load(f)
                    if fcntl: fcntl.flock(f, fcntl.LOCK_UN)
                    
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
        """Saves AI pattern data to JSON file with file locking."""
        try:
            with open(self.pattern_file, 'w') as f:
                if fcntl: fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(self.patterns, f)
                if fcntl: fcntl.flock(f, fcntl.LOCK_UN)
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
            with open(self.performance_file, 'w') as f:
                json.dump(self.strategy_weights, f)
        except Exception as e:
            print(f"Error saving performance: {e}")

    def update_correction_table(self, pattern, pred, actual):
        """Updates the persistent correction table in the database."""
        if not pattern or pred == actual: return
        
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Auto-Purge: Remove entries older than 7 days to keep memory fresh
            cursor.execute("DELETE FROM correction_table WHERE last_seen < datetime('now', '-7 days')")
            
            # Check if pattern exists
            cursor.execute("SELECT occurrence_count, reliability_score FROM correction_table WHERE pattern = ?", (pattern,))
            row = cursor.fetchone()
            
            if row:
                count, score = row
                new_count = count + 1
                # Increase reliability score but cap at 0.95
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
            conn = sqlite3.connect(self.db_path, timeout=10)
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
        Optimized for speed by limiting the training scope.
        """
        if not os.path.exists(self.db_path):
            return False

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Strategy performance: focus on recent 20 active trades
            cursor.execute("SELECT ai_prediction, actual_result, signal_source, timestamp FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp ASC")
            rows = cursor.fetchall()
            
            # Pattern learning: limit to last 200 results for performance
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

            # --- Rolling Window Pattern Learning ---
            results = ["B" if r[0] == "BIG" else "S" for r in results_rows]
            new_patterns = self.patterns.get("patterns", {}).copy()
            error_matrix = self.patterns.get("error_matrix", {}).copy()
            
            total_results = len(results)
            max_pattern_length = min(8, total_results - 1) # Reduced from 12 to 8 for speed
            
            for length in range(1, max_pattern_length + 1):
                # Only train on the most recent data points to keep it fast
                start_idx = max(0, total_results - length - 10)
                for i in range(start_idx, total_results - length):
                    pattern = "".join(results[i:i+length])
                    next_val = results[i+length]
                    
                    dist_from_end = total_results - (i + length)
                    weight = 5.0 if dist_from_end <= 10 else 1.0
                    
                    if pattern not in new_patterns:
                        new_patterns[pattern] = {"B": 0, "S": 0}
                    new_patterns[pattern][next_val] += weight
                    
                    # Update Error Matrix (PEM)
                    actual = results_rows[i+length][0]
                    pred = results_rows[i+length][1]
                    
                    if pattern not in error_matrix:
                        error_matrix[pattern] = {"wins": 0, "losses": 0}
                    
                    inc = 2 if dist_from_end <= 10 else 1
                    if actual == pred:
                        error_matrix[pattern]["wins"] += inc
                    else:
                        error_matrix[pattern]["losses"] += inc
                        self.update_correction_table(pattern, pred, actual)
            
            # Memory Optimization: Keep only top 2000 patterns
            if len(new_patterns) > 2000:
                sorted_patterns = sorted(new_patterns.items(), key=lambda x: (x[1]["B"] + x[1]["S"]), reverse=True)
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

    def predict(self):
        """
        Predicts BIG or SMALL using multiple mathematical strategies with adaptive weighting.
        """
        last_results = self._get_last_n_results(60) 
        volatility = self._calculate_volatility(last_results)
        current_pattern = "".join(last_results[-6:]) if len(last_results) >= 6 else "".join(last_results)

        if len(last_results) < 20:
            return {
                "prediction": "WAIT", 
                "confidence": 0.0, 
                "source": "Data Collection Phase",
                "detected_pattern": current_pattern,
                "status": "waiting"
            }

        # Strategies
        pattern_pred, pattern_conf = self._strategy_pattern(last_results)
        trend_pred, trend_conf = self._strategy_trend(last_results)
        fib_pred, fib_conf = self._strategy_fib(last_results)
        rsi_pred, rsi_conf = self._strategy_rsi(last_results)
        markov_pred, markov_conf = self._strategy_markov(last_results)
        chaos_pred, chaos_conf = self._strategy_chaos(last_results)
        streak_pred, streak_conf = self._strategy_streak_reversal(last_results)

        votes = {"BIG": 0, "SMALL": 0}
        strat_outputs = [
            ("pattern", pattern_pred, pattern_conf),
            ("trend", trend_pred, trend_conf),
            ("fib", fib_pred, fib_conf),
            ("rsi", rsi_pred, rsi_conf),
            ("markov", markov_pred, markov_conf),
            ("chaos", chaos_pred, chaos_conf),
            ("streak_reversal", streak_pred, streak_conf)
        ]

        current_weights = self.strategy_weights.copy()
        if volatility > 0.7:
            current_weights["chaos"] *= 1.5
            current_weights["streak_reversal"] *= 1.2
            current_weights["trend"] *= 0.5
        elif volatility < 0.3:
            current_weights["pattern"] *= 1.5
            current_weights["trend"] *= 1.5
            current_weights["chaos"] *= 0.5

        for name, pred, conf in strat_outputs:
            if pred:
                votes[pred] += (conf / 100) * current_weights.get(name, 1.0)

        prediction = "BIG" if votes["BIG"] > votes["SMALL"] else "SMALL"
        total_votes = votes["BIG"] + votes["SMALL"]
        confidence = round((max(votes["BIG"], votes["SMALL"]) / total_votes) * 100, 2)
        confidence = max(min(confidence, 99.0), 60.0)
        
        contributions = {name: (conf / 100) * current_weights.get(name, 1.0) for name, pred, conf in strat_outputs if pred == prediction}
        best_source_key = max(contributions, key=contributions.get) if contributions else "pattern"
        
        source_display = {
            "pattern": "Pattern Analysis",
            "trend": "Trend Detection",
            "fib": "Fibonacci Sequence",
            "rsi": "RSI Analysis",
            "markov": "Markov Chain Analysis",
            "chaos": "Chaos Theory",
            "streak_reversal": "Streak Reversal"
        }

        return {
            "prediction": prediction,
            "confidence": confidence,
            "source": source_display.get(best_source_key, "Mathematical Sequence"),
            "detected_pattern": current_pattern
        }

    def _strategy_pattern(self, last_results):
        for length in range(min(12, len(last_results)), 0, -1):
            p_check = "".join(last_results[-length:])
            if p_check in self.patterns.get("patterns", {}):
                counts = self.patterns["patterns"][p_check]
                total = counts["B"] + counts["S"]
                if total > 5:
                    pred = "BIG" if counts["B"] > counts["S"] else "SMALL"
                    conf = (max(counts["B"], counts["S"]) / total) * 100
                    return pred, min(conf + (length * 2), 100)
        return None, 0

    def _strategy_trend(self, last_results):
        numeric = [1 if r == "B" else 0 for r in last_results]
        short_avg = np.mean(numeric[-7:]) if len(numeric) >= 7 else 0.5
        if abs(short_avg - 0.5) > 0.2:
            return ("BIG" if short_avg > 0.5 else "SMALL"), 80
        return ("BIG" if short_avg < 0.5 else "SMALL"), 65

    def _strategy_fib(self, last_results):
        streak = 1
        for i in range(len(last_results)-2, -1, -1):
            if last_results[i] == last_results[-1]: streak += 1
            else: break
        if streak in [2, 3, 5, 8, 13]:
            return ("SMALL" if last_results[-1] == "B" else "BIG"), 75
        return None, 0

    def _strategy_rsi(self, last_results):
        numeric = [1 if r == "B" else 0 for r in last_results]
        rsi = self._calculate_rsi(numeric)
        if rsi:
            if rsi > 75: return "SMALL", 85
            if rsi < 25: return "BIG", 85
        return None, 0

    def _strategy_markov(self, last_results):
        if len(last_results) >= 2:
            state = last_results[-1]
            probs = self.patterns.get("markov_probabilities", {}).get(state)
            if probs:
                pred = "BIG" if probs["B"] > probs["S"] else "SMALL"
                return pred, max(probs["B"], probs["S"]) * 100
        return None, 0

    def _strategy_chaos(self, last_results):
        if self._calculate_chaos_indicator(last_results):
            return ("SMALL" if last_results[-1] == "B" else "BIG"), 85
        return None, 0

    def _strategy_streak_reversal(self, last_results):
        streak = 1
        for i in range(len(last_results)-2, -1, -1):
            if last_results[i] == last_results[-1]: streak += 1
            else: break
        if streak >= 4:
            return ("SMALL" if last_results[-1] == "B" else "BIG"), 70 + (streak * 5)
        return None, 0

    def _get_last_n_results(self, n=None):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cursor = conn.cursor()
            cursor.execute("SELECT actual_result FROM trades WHERE actual_result IS NOT NULL ORDER BY timestamp DESC LIMIT ?", (n or 100,))
            rows = cursor.fetchall()
            return ["B" if r[0] == "BIG" else "S" for r in reversed(rows)]
        except Exception as e:
            print(f"Error getting last results: {e}")
            return []
        finally:
            if conn: conn.close()

    def _calculate_rsi(self, prices, period=14):
        if len(prices) < period + 1: return None
        changes = np.diff(prices)
        gains = np.where(changes > 0, changes, 0)
        losses = np.where(changes < 0, -changes, 0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_markov_probabilities(self, results):
        transitions = {}
        for i in range(len(results) - 1):
            curr, nxt = results[i], results[i+1]
            if curr not in transitions: transitions[curr] = {"B": 0, "S": 0}
            transitions[curr][nxt] += 1
        return {s: {"B": v["B"]/(v["B"]+v["S"]), "S": v["S"]/(v["B"]+v["S"])} for s, v in transitions.items() if (v["B"]+v["S"]) > 0}

    def _calculate_chaos_indicator(self, results, window=6):
        if len(results) < window: return False
        numeric = [1 if r == "B" else 0 for r in results[-window:]]
        changes = sum(1 for i in range(window-1) if numeric[i] != numeric[i+1])
        return changes >= window - 2

    def _calculate_volatility(self, results, window=20):
        if len(results) < window: return 0.5
        recent = results[-window:]
        changes = sum(1 for i in range(len(recent)-1) if recent[i] != recent[i+1])
        return changes / (window - 1)
