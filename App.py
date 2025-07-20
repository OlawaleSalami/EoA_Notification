from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
import os  # ✅ Required for reading environment variables

app = Flask(__name__)

@app.route('/arcgis-webhook', methods=['POST'])
def arcgis_webhook():
    data = request.get_json()
    print("Received Survey123 data:", data)

    attributes = data.get("feature", {}).get("attributes", {})
    email = attributes.get("E-mail", "")  # ✅ Use exact field name from form
    name = attributes.get("Name", "Valued client")  # ✅ Corrected field name

    if email:
        send_email(email, name)

    return jsonify({"message": "Webhook received"}), 200

def send_email(to_address, name):
    sender_email = "walesalami012@gmail.com"
    sender_password = os.environ.get("EMAIL_PASSWORD")  # ✅ Secure from environment

    subject = "Thank You for Your Submission"
    body = f"Dear {name},\n\nThank you for completing the survey. We have received your response."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_address

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_address, msg.as_string())
        print(f"✅ Email sent to {to_address}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
