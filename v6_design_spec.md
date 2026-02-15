# AI Master Pro v6.0 Design Specification

## 1. Persistent Correction Table (PCT)
The PCT will be stored in the SQLite database to ensure it survives session resets.

### Table Schema: `correction_table`
| Column | Type | Description |
| :--- | :--- | :--- |
| `pattern` | TEXT (PK) | The sequence of results (e.g., "BBSB") |
| `incorrect_prediction` | TEXT | The prediction that failed (BIG/SMALL) |
| `correct_result` | TEXT | The actual result that occurred (BIG/SMALL) |
| `occurrence_count` | INTEGER | How many times this specific error happened |
| `last_seen` | DATETIME | Last time this error occurred |
| `reliability_score` | REAL | A score (0-1) indicating how reliable this correction is |

## 2. Memory vs. Trend Balance Logic
To prevent "memory dominance" over live trends, we implement a **Decay & Validation** mechanism:

1.  **Dynamic Weighting**:
    *   If a pattern is in the PCT, we check its `reliability_score`.
    *   If the live trend (last 10 results) shows a strong "Dragon" (streak >= 5), the Trend Weight increases by 2x, potentially overriding the PCT correction.
2.  **Correction Validation**:
    *   Before applying a correction from the PCT, the system checks if the *current* session's recent accuracy for that pattern is high.
    *   If the PCT suggests "BIG" but the last 3 times this pattern appeared in the *current* session it resulted in "SMALL", the live trend wins.
3.  **Flexible Memory**:
    *   PCT entries will have a `last_seen` timestamp. Older entries lose `reliability_score` over time (Temporal Decay).

## 3. Implementation Plan
1.  **Database**: Add `correction_table` to `db_manager.py`.
2.  **Model A Core**:
    *   Add `update_correction_table(pattern, pred, actual)` method.
    *   Add `get_correction(pattern)` method.
3.  **MultiManager**:
    *   In `cid_scanner_manager`, query PCT before finalizing signal.
    *   Apply "Trend Override" if a Dragon is detected.
