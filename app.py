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

# ---------------------------
# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------
# Flask setup
app = Flask(__name__)
CORS(app, origins=["*"], methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])

# ---------------------------
# Gmail configuration
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "walesalami012@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

logger.info(f"Gmail address configured: {GMAIL_ADDRESS}")
logger.info(f"Gmail password configured: {'Yes' if GMAIL_APP_PASSWORD else 'No'}")

# ---------------------------
# Google Sheets setup from base64-encoded credentials
creds_b64 = os.getenv("GOOGLE_CREDS_B64")
if not creds_b64:
    raise Exception("Missing GOOGLE_CREDS_B64 env variable")

try:
    creds_dict = json.loads(base64.b64decode(creds_b64).decode("utf-8"))
    with open("credentials.txt", "r") as f:
        encoded = f.read()

# Decode and parse the JSON
    decoded = base64.b64decode(encoded)
    creds_dict = json.loads(decoded)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("EOA Responses").sheet1
    logger.info("Connected to Google Sheet: EOA Responses")
except Exception as e:
    logger.error(f"Error setting up Google Sheets: {e}")
    raise

# ---------------------------
# Helper functions

def is_valid_email(email):
    try:
        parsed = parseaddr(email)
        return "@" in parsed[1] and "." in parsed[1].split("@")[1]
    except:
        return False

def send_email(to_address, name, address, service, amount, signature_url=None):
    try:
        logger.info(f"Preparing email to: {to_address}")

        msg = MIMEMultipart()
        msg["Subject"] = "EOA Service Confirmation"
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_address

        text_body = (
            f"Dear {name},\n\n"
            f"Thank you for engaging our services.\n"
            f"Service Type: {service}\n"
            f"Address: {address}\n"
            f"Amount: {amount}\n\n"
            f"Best regards,\n"
            f"EOA Support Team"
        )
        msg.attach(MIMEText(text_body, "plain"))

        if signature_url:
            try:
                logger.info(f"Downloading signature from: {signature_url}")
                response = requests.get(signature_url, timeout=10)
                if response.status_code == 200:
                    image = MIMEImage(response.content)
                    image.add_header("Content-Disposition", "attachment", filename="signature.jpg")
                    msg.attach(image)
                    logger.info("Signature attached")
            except Exception as e:
                logger.warning(f"Signature fetch failed: {e}")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)

        logger.info("Email sent successfully")
        return True

    except Exception as e:
        logger.error(f"Error sending email: {e}")
        logger.debug(traceback.format_exc())
        return False

# ---------------------------
# Routes

@app.route("/", methods=["GET"])
def home():
    return "EOA Notification Webhook Running", 200

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "EOA Webhook",
        "gmail_configured": bool(GMAIL_APP_PASSWORD)
    }), 200

@app.route("/arcgis-webhook", methods=["POST", "OPTIONS"])
def webhook():
    if request.method == "OPTIONS":
        response = jsonify({"message": "OK"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        return response, 200

    try:
        logger.info("=== Webhook triggered ===")
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "Invalid or missing JSON payload"}), 400

        feature = payload.get("feature", {})
        attributes = feature.get("attributes", {}) if isinstance(feature, dict) else {}

        name = attributes.get("name", "Valued Customer")
        email_to = attributes.get("e_mail", GMAIL_ADDRESS)
        address = attributes.get("client_address", "N/A")
        service_type = attributes.get("service_type", "N/A")
        amount = attributes.get("amount", "N/A")

        if not is_valid_email(email_to):
            logger.warning(f"Invalid email, using default: {email_to}")
            email_to = GMAIL_ADDRESS

        signature_url = None
        attachments = feature.get("attachments", {})
        try:
            if isinstance(attachments, list) and attachments and isinstance(attachments[0], dict):
                signature_url = attachments[0].get("url")
            elif isinstance(attachments, dict):
                if "url" in attachments:
                    signature_url = attachments.get("url")
                elif attachments:
                    first_attachment = attachments[list(attachments.keys())[0]]
                    if isinstance(first_attachment, dict):
                        signature_url = first_attachment.get("url")
        except Exception as e:
            logger.warning(f"Error processing attachments: {e}")

        if not GMAIL_APP_PASSWORD:
            return jsonify({"error": "Email service not configured"}), 500

        success = send_email(email_to, name, address, service_type, amount, signature_url)

        try:
            sheet.append_row([name, email_to, address, service_type, amount])
            logger.info("Data written to Google Sheet")
        except Exception as e:
            logger.error(f"Failed to write to sheet: {e}")

        if success:
            return jsonify({"message": "Email processed successfully"}), 200
        else:
            return jsonify({"error": "Failed to send email"}), 500

    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# ---------------------------
# Error handlers

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error handler triggered: {error}")
    return jsonify({"error": "Internal server error"}), 500

# ---------------------------
# App runner
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
