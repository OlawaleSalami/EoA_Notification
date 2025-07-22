import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
import os
import logging
import traceback
from email.utils import parseaddr

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"], methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])

# Environment variables with detailed checking
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "walesalami012@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

logger.info(f"Gmail address configured: {GMAIL_ADDRESS}")
logger.info(f"Gmail password configured: {'Yes' if GMAIL_APP_PASSWORD else 'No'}")

def is_valid_email(email):
    """Basic email validation"""
    try:
        parsed = parseaddr(email)
        return "@" in parsed[1] and "." in parsed[1].split("@")[1]
    except:
        return False
# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("EOA Responses").sheet1  # replace with your actual sheet name
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
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        response = jsonify({"message": "OK"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        return response, 200
        
    try:
        # Log the raw request
        logger.info("=== WEBHOOK REQUEST START ===")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {request.content_length}")
        
        # Get raw data first
        raw_data = request.get_data(as_text=True)
        logger.info(f"Raw payload: {raw_data[:500]}...")  # First 500 chars
        
        # Try to parse JSON
        payload = request.get_json()
        if not payload:
            logger.error("No JSON payload received or invalid JSON")
            return jsonify({"error": "Invalid or missing JSON payload"}), 400
            
        logger.info(f"Parsed payload keys: {list(payload.keys())}")
        logger.info(f"Full payload: {payload}")
        
        # Check if we have the expected structure
        if "feature" not in payload:
            logger.warning("No 'feature' key in payload")
            feature = {}
        else:
            feature = payload.get("feature", {})
            logger.info(f"Feature keys: {list(feature.keys())}")
        
        # Extract attributes safely
        attributes = feature.get("attributes", {}) if isinstance(feature, dict) else {}
        logger.info(f"Attributes: {attributes}")
        
        # Extract each field with detailed logging
        name = attributes.get("name", "Valued Customer")
        email_to = attributes.get("e_mail", GMAIL_ADDRESS)
        address = attributes.get("client_address", "N/A")
        service_type = attributes.get("service_type", "N/A")
        amount = attributes.get("amount", "N/A")
        
        logger.info(f"Extracted data - Name: {name}, Email: {email_to}, Service: {service_type}")
	    sheet.append_row([name, email_to, address, service_type, amount])
        
        # Validate email
        if not is_valid_email(email_to):
            logger.warning(f"Invalid email address: {email_to}, using default")
            email_to = GMAIL_ADDRESS
        
        # Check for attachments - SAFE VERSION
        attachments = feature.get("attachments", {}) if isinstance(feature, dict) else {}
        signature_url = None
        
        logger.info(f"Attachments type: {type(attachments)}")
        logger.info(f"Attachments content: {attachments}")
        
        # Handle different attachment structures safely
        try:
            if isinstance(attachments, list):
                logger.info(f"Attachments is a list with {len(attachments)} items")
                if len(attachments) > 0 and isinstance(attachments[0], dict):
                    signature_url = attachments[0].get("url")
                    logger.info(f"Signature URL from list: {signature_url}")
            elif isinstance(attachments, dict):
                logger.info(f"Attachments is a dict with keys: {list(attachments.keys())}")
                if "url" in attachments:
                    signature_url = attachments.get("url")
                    logger.info(f"Signature URL from dict: {signature_url}")
                elif attachments:
                    # Try first key-value pair
                    first_key = list(attachments.keys())[0]
                    first_attachment = attachments[first_key]
                    logger.info(f"First attachment key: {first_key}, value type: {type(first_attachment)}")
                    if isinstance(first_attachment, dict) and "url" in first_attachment:
                        signature_url = first_attachment.get("url")
                        logger.info(f"Signature URL from nested dict: {signature_url}")
            
            if not signature_url:
                logger.info("No signature URL found in attachments")
                
        except Exception as e:
            logger.error(f"Error processing attachments: {e}")
            logger.info("Continuing without signature attachment")
        
        # Validate Gmail configuration
        if not GMAIL_APP_PASSWORD:
            logger.error("Gmail app password not configured")
            return jsonify({"error": "Email service not configured"}), 500
        
        # Send email
        logger.info("Attempting to send email...")
        success = send_email(email_to, name, address, service_type, amount, signature_url)
        
        if success:
            logger.info("Email sent successfully")
            return jsonify({"message": "Email processed successfully"}), 200
        else:
            logger.error("Failed to send email")
            return jsonify({"error": "Failed to send email"}), 500
            
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

def send_email(to_address, name, address, service, amount, signature_url=None):
    """Send email with improved error handling and logging"""
    try:
        logger.info(f"Preparing email to: {to_address}")
        
        msg = MIMEMultipart()
        msg["Subject"] = "EOA Service Confirmation"
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_address
        
        # Create email body
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
        logger.info("Email body attached")
        
        # Handle signature attachment
        if signature_url:
            try:
                logger.info(f"Downloading signature from: {signature_url}")
                response = requests.get(signature_url, timeout=10)
                if response.status_code == 200:
                    image = MIMEImage(response.content)
                    image.add_header("Content-Disposition", "attachment", filename="signature.jpg")
                    msg.attach(image)
                    logger.info("Signature attached successfully")
                else:
                    logger.warning(f"Failed to download signature. Status: {response.status_code}")
            except Exception as e:
                logger.error(f"Signature attachment error: {e}")
        
        # Send email
        logger.info("Connecting to Gmail SMTP...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            logger.info("Logging in to Gmail...")
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            logger.info("Sending message...")
            smtp.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_address}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Email sending error: {e}")
        logger.error(f"Email error traceback: {traceback.format_exc()}")
        return False

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error handler triggered: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render uses dynamic ports
    app.run(host="0.0.0.0", port=port)