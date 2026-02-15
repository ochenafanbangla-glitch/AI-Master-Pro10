# AI_MASTER_PRO Changelog

## [v5.8] - 2026-02-14
### Added
- **Dragon Breakout Logic**: New advanced pattern detection system.
  - Identifies "Dragon" patterns (5+ consecutive BIG or SMALL results).
  - Analyzes breakout probability using CID Scanner and archive data.
  - Automatically triggers "Reverse Signal" when a Dragon reaches its probable limit (8+ streak or high probability).
  - Reduces AI confidence during Dragon peaks to protect users from losses.
- **Dragon Alert Dashboard**: Special UI components for Dragon warnings.
  - Purple-themed alert box for Dragon monitoring.
  - Real-time streak tracking on the dashboard.

## [v5.7] - 2026-02-14
### Logic Verification (Logic Integrity)
- **CID Scanner & PEM (Pattern Error Matrix)**: Refined `cid_scanner_manager` for more instant detection and triggering of the "Reverse Signal" logic.
- **20 Data Points Logic**: Strict enforcement of the 20 data points rule within the `predict` method.

### Bug and Exception Handling (Exception Handling)
- **Duplicate Data Input & Empty Input Field**: Input validation and duplicate submission prevention in `app.py`.
- **Server Connection Lost & Duplicate Entries**: Improved `add_trade` with duplicate checks and robust error handling.

### Performance Optimization (Optimization)
- **Database Queries**: Added indexes to the `trades` table for faster queries.
- **Memory Leaks**: Implemented pattern storage limits (top 5000) to prevent memory bloat.

### Cleaning and Commenting (Code Cleaning)
- **Code Refinement**: Removed redundant code and added comprehensive comments across the codebase.
