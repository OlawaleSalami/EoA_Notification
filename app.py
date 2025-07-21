from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
import os
import logging
from email.utils import parseaddr

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Environment variables for security
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "walesalami012@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Validate required environment variables
if not GMAIL_APP_PASSWORD:
    logger.error("GMAIL_APP_PASSWORD environment variable not set")
    raise ValueError("Gmail app password must be set as environment variable")

def is_valid_email(email):
    """Basic email validation"""
    parsed = parseaddr(email)
    return "@" in parsed[1] and "." in parsed[1].split("@")[1]

@app.route("/", methods=["GET"])
def home():
    return "EOA Notification Webhook Running", 200

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "EOA Webhook"}), 200

@app.route("/arcgis-webhook", methods=["POST"])
def webhook():
    try:
        payload = request.get_json()
        
        if not payload:
            return jsonify({"error": "No JSON payload received"}), 400
            
        logger.info("Received webhook payload")
        
        # Extract details with better error handling
        feature = payload.get("feature", {})
        attributes = feature.get("attributes", {})
        
        name = attributes.get("name", "Valued Customer")
        email_to = attributes.get("e_mail", GMAIL_ADDRESS)
        address = attributes.get("client_address", "N/A")
        service_type = attributes.get("service_type", "N/A")
        amount = attributes.get("amount", "N/A")
        
        # Validate email address
        if not is_valid_email(email_to):
            logger.warning(f"Invalid email address: {email_to}, using default")
            email_to = GMAIL_ADDRESS
        
        # Extract signature image URL
        attachments = feature.get("attachments", [])
        signature_url = attachments[0].get("url") if attachments else None
        
        # Send email
        success = send_email(email_to, name, address, service_type, amount, signature_url)
        
        if success:
            return jsonify({"message": "Email processed successfully"}), 200
        else:
            return jsonify({"error": "Failed to send email"}), 500
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

def send_email(to_address, name, address, service, amount, signature_url=None):
    """Send email with improved error handling and logging"""
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "EOA Service Confirmation"
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_address
        
        # Create HTML body for better formatting
        html_body = f"""
        <html>
        <body>
            <h2>EOA Service Confirmation</h2>
            <p>Dear {name},</p>
            <p>Thank you for engaging our services.</p>
            <ul>
                <li><strong>Service Type:</strong> {service}</li>
                <li><strong>Address:</strong> {address}</li>
                <li><strong>Amount:</strong> {amount}</li>
            </ul>
            <p>Best regards,<br>
            EOA Support Team</p>
        </body>
        </html>
        """
        
        # Plain text fallback
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
        msg.attach(MIMEText(html_body, "html"))
        
        # Attach signature image if available
        if signature_url:
            try:
                logger.info("Downloading signature image...")
                response = requests.get(signature_url, timeout=10)
                if response.status_code == 200:
                    image = MIMEImage(response.content)
                    image.add_header("Content-Disposition", "attachment", filename="signature.jpg")
                    msg.attach(image)
                    logger.info("Signature attached to email")
                else:
                    logger.warning(f"Failed to download signature. Status: {response.status_code}")
            except requests.RequestException as e:
                logger.error(f"Failed to download signature: {e}")
        
        # Send email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_address}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed. Check credentials.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)