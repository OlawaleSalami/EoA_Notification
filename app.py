import os
import smtplib
import requests
from flask import Flask, request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

app = Flask(__name__)

GMAIL_ADDRESS = "walesalami012@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("llugkgilegohquon")  # set this in your Render environment

@app.route("/", methods=["GET"])
def home():
    return "EOA Notification Webhook Running", 200

@app.route("/arcgis-webhook", methods=["POST"])
def webhook():
    try:
        payload = request.get_json()
        print("✅ Received webhook payload:", payload)

        # Extract feature and attachment info
        feature = payload.get("feature", {}).get("attributes", {})
        name = feature.get("name", "Unknown")
        email_to = feature.get("e_mail", GMAIL_ADDRESS)
        address = feature.get("client_address", "N/A")
        service_type = feature.get("service_type", "N/A")
        amount = feature.get("amount", "N/A")

        # Build email message
        message = MIMEMultipart()
        message["From"] = GMAIL_ADDRESS
        message["To"] = email_to
        message["Subject"] = f"Pest Control Service Notification for {name}"
        body = f"""
        Hello {name},

        This is to confirm that pest control service was provided at:
        Address: {address}
        Service Type: {service_type}
        Amount: ₦{amount}

        Thank you.

        Regards,
        Pest Control Services
        """
        message.attach(MIMEText(body, "plain"))

        # Download signature image if available
        attachments = payload.get("feature", {}).get("attachments", {}).get("customer_signature", [])
        if attachments:
            img_url = attachments[0]["url"]
            img_name = attachments[0]["name"]
            response = requests.get(img_url)
            if response.status_code == 200:
                part = MIMEApplication(response.content, Name=img_name)
                part["Content-Disposition"] = f'attachment; filename="{img_name}"'
                message.attach(part)
            else:
                print(f"⚠️ Failed to download image: {img_url}")

        # Send email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(message)

        return "✅ Webhook processed successfully", 200

    except Exception as e:
        print("❌ Webhook error:", e)
        return "Error processing webhook", 500
