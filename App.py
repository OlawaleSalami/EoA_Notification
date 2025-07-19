from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/arcgis-webhook', methods=['POST'])
def arcgis_webhook():
    data = request.get_json()

    print("Webhook payload received:", data)

    # Example logic: trigger an alert if status is "urgent"
    status = data.get("feature", {}).get("attributes", {}).get("status", "").lower()
    if status == "urgent":
        print("🚨 Urgent issue detected!")

    return jsonify({"message": "Received"}), 200
