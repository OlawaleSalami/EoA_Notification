import os
import json
import base64
import logging
import traceback
import smtplib
import requests

from flask import Flask, request, jsonify
from flask_cors import CORS
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import parseaddr

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask setup
app = Flask(__name__)
CORS(app)

# Environment Variables
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "walesalami012@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GOOGLE_CREDS_B64 = os.getenv("GOOGLE_CREDS_B64")

# Validate credentials
if not GOOGLE_CREDS_B64:
    raise Exception("GOOGLE_CREDS_B64 is not set")

# Decode and set up Google Sheets client
try:
    creds_json = base64.b64decode(GOOGLE_CREDS_B64).decode("utf-8")
    creds_dict = json.loads(creds_json)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    sheet = gspread.authorize(creds).open("EOA Responses").sheet1
    logger.info("Connected to Google Sheet")
except Exception as e:
    logger.error(f"Google Sheets setup failed: {e}")
    raise

# Email Validation
def is_valid_email(email):
    try:
        return "@" in parseaddr(email)[1]
    except:
        return False

# Send Email Function
def send_email(to_address, name, address, service, amount, signature_url=None):
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "EOA Service Confirmation"
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_address

        body = f"""Dear {name},

Thank you for engaging our services.
Service Type: {service}
Address: {address}
Amount: {amount}

Best regards,
EOA Support Team
"""
        msg.attach(MIMEText(body, "plain"))

        if signature_url:
            try:
                response = requests.get(signature_url)
                if response.status_code == 200:
                    img = MIMEImage(response.content)
                    img.add_header("Content-Disposition", "attachment", filename="signature.jpg")
                    msg.attach(img)
            except Exception as e:
                logger.warning(f"Failed to fetch signature image: {e}")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)

        logger.info("Email sent")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        logger.debug(traceback.format_exc())
        return False

# Routes
@app.route("/", methods=["GET"])
def home():
    return "EOA Notification Webhook is running", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/arcgis-webhook", methods=["POST"])
def arcgis_webhook():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No JSON payload provided"}), 400

        feature = payload.get("feature", {})
        attributes = feature.get("attributes", {})

        name = attributes.get("name", "Valued Customer")
        email_to = attributes.get("e_mail", GMAIL_ADDRESS)
        address = attributes.get("client_address", "N/A")
        service_type = attributes.get("service_type", "N/A")
        amount = attributes.get("amount", "N/A")

        if not is_valid_email(email_to):
            email_to = GMAIL_ADDRESS

        # Extract signature URL if any
        signature_url = None
        attachments = feature.get("attachments", {})
        if isinstance(attachments, list) and attachments:
            signature_url = attachments[0].get("url")
        elif isinstance(attachments, dict):
            signature_url = attachments.get("url")

        email_sent = send_email(email_to, name, address, service_type, amount, signature_url)

        try:
            sheet.append_row([name, email_to, address, service_type, amount])
            logger.info("Data written to Google Sheet")
        except Exception as e:
            logger.error(f"Google Sheet write failed: {e}")

        return jsonify({"message": "Email processed" if email_sent else "Failed to send email"}), 200 if email_sent else 500

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Start the app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
