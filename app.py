from flask import Flask, jsonify
import os
import numpy
# import pandas
# import scikit-learn

app = Flask(__name__)

@app.route("/")
def index():
    return "AI Master Pro 10 - Testing Imports"

@app.route("/health")
def health():
    return jsonify({"status": "ok", "numpy": "imported"})

if __name__ == "__main__":
    app.run(port=5000)
