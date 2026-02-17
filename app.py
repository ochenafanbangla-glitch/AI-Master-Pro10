from flask import Flask, jsonify
import os
import sys
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route("/")
def index():
    return "AI Master Pro 10 - Debugging Imports"

@app.route("/health")
def health():
    import_results = {}
    
    try:
        from models.model_a_core import ModelACore
        import_results["ModelACore"] = "Success"
    except Exception as e:
        import_results["ModelACore"] = f"Error: {str(e)}"
        
    try:
        from utils.db_manager import init_db
        import_results["db_manager"] = "Success"
    except Exception as e:
        import_results["db_manager"] = f"Error: {str(e)}"

    return jsonify({
        "status": "ok", 
        "import_results": import_results,
        "python_path": sys.path
    })

if __name__ == "__main__":
    app.run(port=5000)
