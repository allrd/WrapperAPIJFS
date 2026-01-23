from flask import Flask, request, jsonify
from vali import process_invoice, load_or_create_excel
import os

app = Flask(__name__)

# -------------------------
# STATIC CREDENTIALS
# -------------------------
VALID_USERNAME = "RohitKumar"
VALID_PASSWORD = "Admin"


@app.route("/process-invoice", methods=["POST"])
def process_invoice_api():

    # -------------------------
    # 1️⃣ AUTH HEADERS
    # -------------------------
    username = request.headers.get("X-Username")
    password = request.headers.get("X-Password")

    if not username or not password:
        return jsonify({"error": "Authentication headers missing"}), 401

    if username != VALID_USERNAME or password != VALID_PASSWORD:
        return jsonify({"error": "Invalid username or password"}), 401

    # -------------------------
    # 2️⃣ REQUEST BODY
    # -------------------------
    data = request.json
    file_path = data.get("file_path") if data else None

    if not file_path:
        return jsonify({"error": "file_path is required"}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # -------------------------
    # 3️⃣ LOAD EXCEL + PROCESS
    # -------------------------
    df = load_or_create_excel()
    before_count = len(df)

    df = process_invoice(file_path, df)

    after_count = len(df)
    status = "NEW_CLAIM" if after_count > before_count else "DUPLICATE_CLAIM"

    last_row = df.iloc[-1]

    # -------------------------
    # 4️⃣ RESPONSE
    # -------------------------
    return jsonify({
        "status": status,
        "invoice_number": last_row["Invoice Number"],
        "invoice_date": str(last_row["Invoice Date"]),
        "vendor": last_row["Vendor"],
        "total_amount": last_row["Total Amount"],
        "processed_by": username
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
