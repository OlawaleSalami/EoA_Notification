from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
import os

app = Flask(__name__)
CORS(app)

GMAIL_ADDRESS = "walesalami012@gmail.com"
GMAIL_APP_PASSWORD = "llugkgilegohquon"  # Set this securely in production

@app.route("/", methods=["GET"])
def home():
    return "EOA Notification Webhook Running", 200

@app.route("/arcgis-webhook", methods=["POST"])
def webhook():
    try:
        payload = request.get_json()
        print("✅ Received webhook payload:", payload)

        # Extract details
        feature = payload.get("feature", {}).get("attributes", {})
        name = feature.get("name", "Valued Customer")
        email_to = feature.get("e_mail", GMAIL_ADDRESS)
        address = feature.get("client_address", "N/A")
        service_type = feature.get("service_type", "N/A")
        amount = feature.get("amount", "N/A")

        # Optional: Extract signature image URL
        attachments = payload.get("feature", {}).get("attachments", [])
        signature_url = attachments[0].get("url") if attachments else None

        # Send email with or without signature
        send_email(email_to, name, address, service_type, amount, signature_url)

        return jsonify({"message": "Email processed successfully"}), 200

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

def send_email(to_address, name, address, service, amount, signature_url=None):
    msg = MIMEMultipart()
    msg["Subject"] = "EOA Service Confirmation"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address

    body = (
        f"Dear {name},\n\n"
        f"Thank you for engaging our services.\n"
        f"Service Type: {service}\n"
        f"Address: {address}\n"
        f"Amount: {amount}\n\n"
        f"Best regards,\n"
        f"EOA Support Team"
    )

    msg.attach(MIMEText(body, "plain"))

    # Attach image if available
    if signature_url:
        try:
            response = requests.get(signature_url)
            if response.status_code == 200:
                image = MIMEImage(response.content)
                image.add_header("Content-Disposition", "attachment", filename="signature.jpg")
                msg.attach(image)
                print("📎 Signature attached to email.")
            else:
                print(f"⚠️ Failed to download signature. Status: {response.status_code}")
        except Exception as e:
            print(f"❌ Failed to attach signature: {e}")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Email sent to {to_address}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
