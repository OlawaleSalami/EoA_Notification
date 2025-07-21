from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from email.message import EmailMessage
import smtplib

app = Flask(__name__)
CORS(app)

# Your Gmail credentials (use environment variable or hardcode for testing)
GMAIL_ADDRESS = "walesalami012@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("llugkgilegohquon")  # or paste your app password here

@app.route('/', methods=['GET'])
def home():
    return "EOA Notification Webhook Running", 200

@app.route('/arcgis-webhook', methods=['POST'])
def arcgis_webhook():
    try:
        data = request.get_json()
        print("✅ Received webhook payload:", data)

        attributes = data.get("feature", {}).get("attributes", {})
        email = attributes.get("e-mail", "").strip()
        name = attributes.get("name", "Valued Customer")
        service = attributes.get("services_performed", "Not Provided")

        signature_url = data.get("feature", {}).get("attachments", [{}])[0].get("url")

        attachment_path = None
        if signature_url:
            attachment_path = download_signature(signature_url)

        if email:
            send_email(email, name, service, attachment_path)

        return jsonify({"message": "Email processed"}), 200

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

def download_signature(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            path = "/tmp/signature.jpg"
            with open(path, "wb") as f:
                f.write(response.content)
            print("📸 Signature downloaded.")
            return path
        else:
            raise Exception("Failed to download image")
    except Exception as e:
        print(f"❌ Error downloading signature: {e}")
        return None

def send_email(to_address, name, service, attachment_path=None):
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Thank You – {service} Completed"
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_address

        msg.set_content(
            f"Dear {name},\n\n"
            f"Thank you for requesting our service.\n"
            f"The '{service}' has been completed.\n\n"
            f"Regards,\nEoA Team"
        )

        # Attach image if available
        if attachment_path:
            with open(attachment_path, "rb") as f:
                file_data = f.read()
                msg.add_attachment(file_data, maintype="image", subtype="jpeg", filename="signature.jpg")
            print("📎 Signature attached to email.")

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
            print(f"✅ Email sent to {to_address}")

    except Exception as e:
        print(f"❌ Email sending failed: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)