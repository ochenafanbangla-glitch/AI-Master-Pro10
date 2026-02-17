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
    Enhanced with Incremental Learning and Weight Decay.
    """
    def __init__(self):
        self.name = "Model A (Advanced Lite AI)"
        self.is_vercel = "VERCEL" in os.environ
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))
        
        if self.is_vercel:
            self.db_path = '/tmp/database.db'
            self.pattern_file = '/tmp/patterns.json'
            self.performance_file = '/tmp/strategy_performance.json'
            
            orig_pattern = os.path.join(os.path.dirname(__file__), 'patterns.json')
            orig_perf = os.path.join(os.path.dirname(__file__), 'strategy_performance.json')
            
            try:
                if not os.path.exists(self.pattern_file) and os.path.exists(orig_pattern):
                    shutil.copy2(orig_pattern, self.pattern_file)
                elif not os.path.exists(self.pattern_file):
                    with open(self.pattern_file, 'w') as f:
                        json.dump({"patterns": {}, "markov_probabilities": {}, "error_matrix": {}}, f)
                        
                if not os.path.exists(self.performance_file) and os.path.exists(orig_perf):
                    shutil.copy2(orig_perf, self.performance_file)
                elif not os.path.exists(self.performance_file):
                    with open(self.performance_file, 'w') as f:
                        json.dump({s: 1.0 for s in self.strategies}, f)
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
        try:
            temp_file = self.pattern_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.patterns, f)
            os.replace(temp_file, self.pattern_file)
        except Exception as e:
            print(f"Error saving patterns: {e}")

    def _load_performance(self):
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
                # Incremental reliability boost
                new_score = min(0.98, score + 0.02)
                cursor.execute("""
                    UPDATE correction_table 
                    SET occurrence_count = ?, reliability_score = ?, last_seen = CURRENT_TIMESTAMP, 
                        incorrect_prediction = ?, correct_result = ?
                    WHERE pattern = ?
                """, (new_count, new_score, pred, actual, pattern))
            else:
                cursor.execute("""
                    INSERT INTO correction_table (pattern, incorrect_prediction, correct_result, occurrence_count, reliability_score)
                    VALUES (?, ?, ?, 1, 0.6)
                """, (pattern, pred, actual))
            conn.commit()
        except Exception as e:
            print(f"Correction Table Update Error: {e}")
        finally:
            if conn: conn.close()

    def get_correction(self, pattern):
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
        Enhanced Training with Incremental Learning and Weight Decay.
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 1. Strategy Performance Update (Reinforcement Learning)
            cursor.execute("SELECT ai_prediction, actual_result, signal_source FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT 50")
            recent_trades = cursor.fetchall()
            
            if recent_trades:
                source_map = {
                    "Pattern Analysis": "pattern",
                    "Trend Detection": "trend",
                    "Fibonacci Sequence": "fib",
                    "RSI Analysis": "rsi",
                    "Markov Chain Analysis": "markov",
                    "Chaos Theory": "chaos",
                    "Streak Reversal": "streak_reversal"
                }
                
                perf = {s: {"wins": 0, "total": 0} for s in self.strategies}
                for pred, actual, source in recent_trades:
                    strat = source_map.get(source)
                    if strat:
                        perf[strat]["total"] += 1
                        if pred == actual:
                            perf[strat]["wins"] += 1
                
                for s in self.strategies:
                    if perf[s]["total"] > 0:
                        accuracy = perf[s]["wins"] / perf[s]["total"]
                        # Reinforcement: Adjust weights based on recent success
                        self.strategy_weights[s] = max(0.3, min(3.0, accuracy * 3.0))
                self._save_performance()

            # 2. Pattern Analysis with Weight Decay (Incremental Learning)
            limit = 300
            if include_archived:
                cursor.execute("SELECT actual_result, ai_prediction FROM trades WHERE actual_result IS NOT NULL ORDER BY timestamp DESC LIMIT ?", (limit,))
            else:
                cursor.execute("SELECT actual_result, ai_prediction FROM trades WHERE actual_result IS NOT NULL AND is_archived = 0 ORDER BY timestamp DESC LIMIT ?", (limit,))
            
            results_rows = list(reversed(cursor.fetchall()))
            if len(results_rows) < 5:
                return False
                
            results = ["B" if r[0] == "BIG" else "S" for r in results_rows]
            
            # Apply Weight Decay to existing patterns
            new_patterns = {}
            for p, counts in self.patterns.get("patterns", {}).items():
                new_patterns[p] = {k: v * 0.95 for k, v in counts.items()} # 5% decay
                
            error_matrix = self.patterns.get("error_matrix", {}).copy()
            
            total_results = len(results)
            max_pattern_length = min(8, total_results - 1)
            
            for length in range(1, max_pattern_length + 1):
                start_idx = max(0, total_results - length - 100)
                for i in range(start_idx, total_results - length):
                    pattern = "".join(results[i:i+length])
                    next_val = results[i+length]
                    
                    # Distance-based weighting (Recency Bias)
                    dist_from_end = total_results - (i + length)
                    weight = 15.0 if dist_from_end <= 5 else 8.0 if dist_from_end <= 15 else 2.0
                    
                    if pattern not in new_patterns:
                        new_patterns[pattern] = {"B": 0, "S": 0}
                    new_patterns[pattern][next_val] += weight
                    
                    # Error Analysis
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
            
            # Pruning old/weak patterns
            if len(new_patterns) > 2500:
                sorted_patterns = sorted(new_patterns.items(), key=lambda x: sum(x[1].values()), reverse=True)
                new_patterns = dict(sorted_patterns[:2500])
                
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

    def predict(self):
        """
        Enhanced Prediction with Multi-Strategy Weighted Consensus.
        """
        results = self._get_last_n_results(60)
        if not results:
            return {"prediction": random.choice(["BIG", "SMALL"]), "confidence": 50.0, "source": "Random (No Data)"}
            
        res_str = ["B" if r == "BIG" else "S" for r in results]
        
        votes = {"BIG": 0, "SMALL": 0}
        details = {}
        
        # 1. Pattern Strategy
        p_pred, p_conf = self._strategy_pattern(res_str)
        if p_pred:
            weight = self.strategy_weights.get("pattern", 1.0)
            votes[p_pred] += p_conf * weight
            details["pattern"] = {"pred": p_pred, "conf": p_conf}
            
        # 2. Trend Strategy
        t_pred, t_conf = self._strategy_trend(res_str)
        if t_pred:
            weight = self.strategy_weights.get("trend", 1.0)
            votes[t_pred] += t_conf * weight
            details["trend"] = {"pred": t_pred, "conf": t_conf}
            
        # 3. Markov Strategy
        m_pred, m_conf = self._strategy_markov(res_str)
        if m_pred:
            weight = self.strategy_weights.get("markov", 1.0)
            votes[m_pred] += m_conf * weight
            details["markov"] = {"pred": m_pred, "conf": m_conf}
            
        # 4. Fibonacci Strategy
        f_pred, f_conf = self._strategy_fibonacci(res_str)
        if f_pred:
            weight = self.strategy_weights.get("fib", 1.0)
            votes[f_pred] += f_conf * weight
            details["fib"] = {"pred": f_pred, "conf": f_conf}

        # Consensus
        prediction = "BIG" if votes["BIG"] > votes["SMALL"] else "SMALL"
        total_votes = votes["BIG"] + votes["SMALL"]
        confidence = (max(votes["BIG"], votes["SMALL"]) / total_votes * 100) if total_votes > 0 else 50.0
        
        # Source identification
        best_strat = max(details.items(), key=lambda x: x[1]["conf"] * self.strategy_weights.get(x[0], 1.0))[0]
        source_map = {
            "pattern": "Pattern Analysis",
            "trend": "Trend Detection",
            "markov": "Markov Chain Analysis",
            "fib": "Fibonacci Sequence"
        }
        
        return {
            "prediction": prediction,
            "confidence": round(min(98.0, confidence), 1),
            "source": source_map.get(best_strat, "Hybrid AI"),
            "details": details
        }

    def _strategy_pattern(self, results):
        for length in range(6, 1, -1):
            pattern = "".join(results[-length:])
            if pattern in self.patterns.get("patterns", {}):
                counts = self.patterns["patterns"][pattern]
                total = sum(counts.values())
                if total > 5:
                    pred = "BIG" if counts["B"] > counts["S"] else "SMALL"
                    conf = (max(counts["B"], counts["S"]) / total) * 100
                    return pred, conf
        return None, 0

    def _strategy_trend(self, results):
        if len(results) < 5: return None, 0
        recent = results[-5:]
        b_count = recent.count("B")
        s_count = recent.count("S")
        pred = "BIG" if b_count > s_count else "SMALL"
        conf = (max(b_count, s_count) / 5) * 100
        return pred, conf

    def _strategy_markov(self, results):
        last = "B" if results[-1] == "BIG" or results[-1] == "B" else "S"
        probs = self.patterns.get("markov_probabilities", {}).get(last)
        if probs:
            pred = "BIG" if probs["B"] > probs["S"] else "SMALL"
            conf = max(probs["B"], probs["S"]) * 100
            return pred, conf
        return None, 0

    def _strategy_fibonacci(self, results):
        # Simple Fibonacci-based pattern detection
        if len(results) < 8: return None, 0
        # Check for alternating patterns or streaks matching Fib numbers
        streak = 1
        for i in range(len(results)-2, -1, -1):
            if results[i] == results[-1]: streak += 1
            else: break
        
        fib = [1, 2, 3, 5, 8, 13]
        if streak in fib:
            # If streak is a fib number, predict continuation or reversal based on context
            pred = "BIG" if results[-1] == "B" or results[-1] == "BIG" else "SMALL"
            return pred, 65.0
        return None, 0

    def _get_last_n_results(self, n=60):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT actual_result FROM trades WHERE actual_result IS NOT NULL ORDER BY timestamp DESC LIMIT ?", (n,))
            rows = cursor.fetchall()
            return [row[0] for row in reversed(rows)]
        except Exception as e:
            print(f"Error getting last results: {e}")
            return []
        finally:
            if conn: conn.close()
