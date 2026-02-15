from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file
import os
import uuid
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from models.model_a_core import ModelACore
from utils.db_manager import add_trade, get_recent_trades, init_db, delete_trade, clear_db, get_total_trades_count, DB_PATH, archive_all_trades, get_session_trades
from utils.auth_helper import login_required, admin_required
from utils.multi_manager import MultiManagerSystem
import threading

# Configure Logging
# On Vercel, writing to a local file might fail, so we use StreamHandler for console logs
IS_VERCEL = "VERCEL" in os.environ
log_handlers = [logging.StreamHandler()]
if not IS_VERCEL:
    try:
        log_handlers.append(logging.FileHandler("app_error.log"))
    except:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Initialize Flask App
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ai-master-pro-secure-key-2026")

# Initialize AI Models and Multi-Manager System
# We initialize inside a function or check for existence to avoid issues during build/cold start
model_a = None
manager_system = None

def get_systems():
    global model_a, manager_system
    if model_a is None:
        model_a = ModelACore()
        # Ensure DB is initialized
        if not os.path.exists(DB_PATH):
            init_db()
    if manager_system is None:
        manager_system = MultiManagerSystem(model_a, DB_PATH)
    return model_a, manager_system

@app.before_request
def ensure_session():
    get_systems() # Ensure systems are ready before any request
    """Ensures every user has a unique session ID and tracking info."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    if "start_time" not in session:
        session["start_time"] = datetime.now().timestamp()
    if "user_id" not in session:
        session["user_id"] = "guest_user"

@app.route("/")
def dashboard():
    """Main Trading Dashboard: Displays recent trades and AI accuracy."""
    try:
        recent_trades = get_recent_trades(10)
        total_collected = get_total_trades_count()
        
        # Calculate Accuracy for Trust Building
        all_trades = get_recent_trades(50)
        completed_trades = [t for t in all_trades if t["actual_result"] is not None]
        if completed_trades:
            wins = sum(1 for t in completed_trades if t["ai_prediction"] == t["actual_result"])
            accuracy = round((wins / len(completed_trades)) * 100, 1)
        else:
            accuracy = 0.0
            
    except Exception as e:
        logger.error(f"Dashboard Error: {e}", exc_info=True)
        recent_trades = []
        total_collected = 0
        accuracy = 0.0
        
    target_trades = 20 # Minimum data required for prediction
    
    # Calculate learning progress percentage
    learning_percent = 100 if total_collected >= target_trades else int((total_collected / target_trades) * 100)
    
    return render_template("user/dashboard.html", 
                           trades=recent_trades, 
                           total_collected=total_collected, 
                           target_trades=target_trades,
                           learning_percent=learning_percent,
                           accuracy=accuracy)

@app.route("/api/dashboard-data", methods=["GET"])
def get_dashboard_data():
    """Returns live data for the dashboard without full page reload."""
    try:
        recent_trades = get_recent_trades(10)
        total_collected = get_total_trades_count()
        
        all_trades = get_recent_trades(50)
        completed_trades = [t for t in all_trades if t["actual_result"] is not None]
        if completed_trades:
            wins = sum(1 for t in completed_trades if t["ai_prediction"] == t["actual_result"])
            accuracy = round((wins / len(completed_trades)) * 100, 1)
        else:
            accuracy = 0.0
            
        target_trades = 20
        learning_percent = 100 if total_collected >= target_trades else int((total_collected / target_trades) * 100)
        
        return jsonify({
            "status": "success",
            "trades": recent_trades,
            "total_collected": total_collected,
            "target_trades": target_trades,
            "learning_percent": learning_percent,
            "accuracy": accuracy
        })
    except Exception as e:
        logger.error(f"Dashboard Data Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/get-signal", methods=["GET"])
def get_signal():
    """Generates a trading signal after 20 data points are collected."""
    try:
        total_collected = get_total_trades_count()
        target_trades = 20
        
        # Enforce 20 data points logic
        if total_collected < target_trades:
            return jsonify({
                "status": "waiting",
                "message": f"Collecting data... {total_collected}/{target_trades} items collected.",
                "collected": total_collected,
                "target": target_trades
            })

        # Get raw signal from AI Core and process through Multi-Manager (CID/PEM)
        m_a, m_s = get_systems()
        raw_signal = m_a.predict()
        processed_signal = m_s.process_signal(raw_signal)
        
        # PAUSED logic removed as per user request

        trade_id = str(uuid.uuid4())[:8]
        
        # Store signal in session for verification during result submission
        session["last_signal"] = {
            "trade_id": trade_id,
            "prediction": processed_signal["prediction"],
            "confidence": processed_signal["confidence"],
            "source": processed_signal["source"]
        }
        
        return jsonify({
            "status": "success",
            "trade_id": trade_id,
            "prediction": processed_signal["prediction"],
            "confidence": processed_signal["confidence"],
            "source": processed_signal["source"],
            "risk_alert": processed_signal.get("risk_alert", ""),
            "dragon_alert": processed_signal.get("dragon_alert", ""),
            "memory_alert": processed_signal.get("memory_alert", ""),
            "correction_status": processed_signal.get("correction_status", "NONE"),
            "detected_pattern": processed_signal.get("detected_pattern", "")
        })
    except Exception as e:
        logger.error(f"Get Signal Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/submit-result", methods=["POST"])
def submit_result():
    """Submits actual result, validates input, and triggers AI training."""
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
        
    actual_result = data.get("result")
    user_choice = data.get("user_choice")
    bet_amount = data.get("bet_amount", 0)
    
    # Input Validation
    if not actual_result or actual_result not in ["BIG", "SMALL"]:
        return jsonify({"status": "error", "message": "Invalid result input.", "code": "INVALID_RESULT"}), 400

    # Prevent duplicate submissions
    last_sub_time = session.get("last_submission_time")
    last_sub_val = session.get("last_submission_val")
    curr_time = datetime.now().timestamp()
    
    # Removed 2-second delay as per user request for faster manual input
    if last_sub_time and (curr_time - last_sub_time < 0.1) and (last_sub_val == actual_result):
        return jsonify({"status": "error", "message": "Duplicate submission detected.", "code": "DUPLICATE_SUBMISSION"}), 400
    
    session["last_submission_time"] = curr_time
    session["last_submission_val"] = actual_result
    
    last_signal = session.get("last_signal")
    
    # Handle initial data collection vs active signal
    if not last_signal:
        trade_id = str(uuid.uuid4())[:8]
        prediction, confidence, source = "INITIAL", 0.0, "Initial Data Collection"
    else:
        trade_id, prediction, confidence, source = last_signal["trade_id"], last_signal["prediction"], last_signal["confidence"], last_signal["source"]

    # Set IST Timestamp
    ist_now = datetime.now(tz=timezone(timedelta(hours=5, minutes=30)))
    timestamp_str = ist_now.strftime("%Y-%m-%d %H:%M:%S")

    trade_data = {
        "user_id": session.get("user_id", "guest_user"),
        "session_id": session.get("session_id"),
        "trade_id": trade_id,
        "timestamp": timestamp_str,
        "ai_prediction": prediction,
        "ai_confidence": confidence,
        "signal_source": source,
        "user_choice": user_choice if user_choice != "---" else None,
        "actual_result": actual_result,
        "bet_amount": bet_amount
    }
    
    try:
        if add_trade(trade_data):
            # Always trigger AI learning after a trade is added
            m_a, _ = get_systems()
            if IS_VERCEL:
                # On Vercel, background threads might be killed immediately. 
                # We do it synchronously or skip for performance if needed.
                m_a.train_from_db()
            else:
                threading.Thread(target=m_a.train_from_db).start()
            
            if last_signal:
                is_correct = (last_signal["prediction"] == actual_result)
                if not is_correct:
                    # If prediction was wrong, trigger an additional training for faster adaptation
                    if IS_VERCEL:
                        m_a.train_from_db()
                    else:
                        threading.Thread(target=m_a.train_from_db).start()
                session.pop("last_signal", None)
                msg = "Correct Prediction! AI refined." if is_correct else "AI corrected its mistake."
            else:
                msg = "Initial data point collected."
                
            return jsonify({"status": "success", "message": msg}), 200
        return jsonify({"status": "error", "message": "Failed to save trade.", "code": "DB_SAVE_FAILED"}), 500
    except Exception as e:
        logger.error(f"API Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e), "code": "SERVER_ERROR"}), 500

@app.route("/api/undo-trade", methods=["POST"])
def undo_trade():
    """Deletes a trade and updates AI memory."""
    data = request.json
    trade_id = data.get("trade_id")
    if not trade_id: return jsonify({"status": "error", "message": "Trade ID required", "code": "MISSING_TRADE_ID"}), 400
    
    try:
        delete_trade(trade_id)
        threading.Thread(target=model_a.train_from_db).start() # Asynchronous training
        return jsonify({"status": "success", "message": "Trade deleted and AI updated"}), 200
    except Exception as e:
        logger.error(f"API Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e), "code": "SERVER_ERROR"}), 500

@app.route("/api/new-session", methods=["POST"])
def new_session():
    """Archives current data and resets short-term PEM for a fresh start."""
    try:
        archive_all_trades()
        # Perform long-term learning on all data including archived
        threading.Thread(target=model_a.train_from_db, kwargs={"include_archived": True}).start()
        # Reset PEM *after* training, to ensure it's cleared for new session
        model_a.patterns["error_matrix"] = {} 
        model_a._save_patterns()
        session.pop("last_signal", None)
        session["session_id"] = str(uuid.uuid4())
        return jsonify({"status": "success", "message": "New Session Started!"}), 200
    except Exception as e:
        logger.error(f"API Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e), "code": "SERVER_ERROR"}), 500

@app.route("/api/download-cvc")
def download_cvc():
    """Downloads CVC (Trade) data for the current session as a CSV file."""
    try:
        session_id = session.get("session_id")
        trades = get_session_trades(session_id)
        
        if not trades:
            return jsonify({"status": "error", "message": "No data found for this session."}), 404
            
        output = io.StringIO()
        if trades:
            writer = csv.DictWriter(output, fieldnames=trades[0].keys())
            writer.writeheader()
            writer.writerows(trades)
        
        output.seek(0)
        filename = f"CVC_DATA_{session_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Download CVC Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/admin-secure-portal")
@login_required
def admin_panel():
    """Admin panel for monitoring trades."""
    trades = get_recent_trades(50)
    return render_template("admin/panel.html", trades=trades)

if __name__ == "__main__":
    if not os.path.exists(DB_PATH): init_db()
    app.run(debug=True, port=5000)
