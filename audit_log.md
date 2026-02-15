# AI MASTER PRO V5.9 - Audit Log

## Phase 2: Core Logic Audit (Dragon vs Manager)

### Finding 1: Logic Overlapping & Conflict
- **Issue**: In `multi_manager.py`, the `cid_scanner_manager` handles both Dragon Trend Following and Dragon Breakout.
- **Conflict**: 
    - If `streak >= 5`, it might set `prediction = dragon_type` (Trend Following).
    - If `streak >= 8`, it sets `prediction = reverse_type` (Breakout).
    - However, if `counter_win_rate < 0.10` (Adaptive Mode), it forces Trend Following and **immediately pops the 'status'** but doesn't exit the function. It then proceeds to the "Win Zone Identification" which might **reverse the signal again** if the pattern is in a "Reverse Zone".
- **Result**: A signal could be set to BIG by Dragon Trend, then reversed to SMALL by Win Zone logic in the same call. This explains why users see SMALL when the server result is BIG.

### Finding 2: CID Sensor Accuracy & Reverse Signal
- **Issue**: The "Reverse Zone" logic in `cid_scanner_manager` (lines 128-133) is very aggressive. If a pattern has `win_rate <= 0.2` based on only 2 occurrences (`total >= 2`), it reverses the signal.
- **Problem**: 2 occurrences are not statistically significant. This causes "Reverse Signal" at the wrong time.

## Phase 3: Database Performance & Sync

### Finding 3: Database Path Mismatch
- **Issue**: `app.py` uses `DB_PATH` from `utils.db_manager`, but also checks `os.path.exists('database.db')` in `if __name__ == '__main__':`.
- **Sync**: The user mentioned `/home/ramf231/my_app/database.db`. The current code uses a relative path `database.db` in the project root. If the app is run from a different directory, it might create a new DB.

### Finding 4: Slowdown on Frequent Input
- **Issue**: `submit_result` calls `model_a.train_from_db()` **twice** if the prediction was wrong.
- **Performance**: `train_from_db` performs complex loops and JSON I/O with file locking. Doing this synchronously in the request-response cycle will definitely slow down the system as the DB grows.

## Phase 4: CID Sensor Adaptation

### Finding 5: Adaptation Lag
- **Issue**: `train_from_db` uses `np.exp(i / total_results)` for weighting. While this gives more weight to recent data, the `error_matrix` (PEM) only uses a simple `inc = 2` for recent data.
- **Problem**: This isn't aggressive enough to "forget" old patterns when the market shifts.

## Phase 5: Session & Archive Management

### Finding 6: PEM Reset Logic
- **Issue**: `new_session` in `app.py` resets `model_a.patterns["error_matrix"] = {}` but then calls `train_from_db(include_archived=True)`.
- **Problem**: `train_from_db` **re-populates** the `error_matrix` from the database (including archived trades if `include_archived=True`). This defeats the purpose of "New Session" which is meant to clear short-term memory.

## Phase 6: Broken Loops & Internal Server Errors

### Finding 7: Potential Crash in RSI/Numerical Logic
- **Issue**: `_strategy_rsi` and `_strategy_trend` use `numpy` on `last_results`. If `last_results` is empty or too short, it might cause issues, though there are some checks.
- **Issue**: `_calculate_markov_probabilities` can divide by zero if `v["B"]+v["S"]` is 0, though there is a check `if (v["B"]+v["S"]) > 0`.
- **Issue**: File locking with `fcntl` is not available on all systems (like Windows), though there's a try-except.
- **Issue**: `app.py` line 134: `(curr_time - last_sub_time < 2)` - if `last_sub_time` is None, this crashes. It is checked with `if last_sub_time`, so it's safe.
- **Issue**: `app.py` line 167: `if add_trade(trade_data):` - if this fails, it returns 500, but doesn't log the specific reason.
