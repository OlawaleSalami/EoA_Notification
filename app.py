from flask import Flask, request, jsonify
from flask_cors import CORS  # ✅ Import CORS
import smtplib
from email.mime.text import MIMEText
import os  # ✅ Required for reading environment variables

app = Flask(__name__)
CORS(app) 
@app.route('/arcgis-webhook', methods=['POST'])
def arcgis_webhook():
    data = request.get_json()
    print("Received Survey123 data:", data)

    attributes = data.get("feature", {}).get("attributes", {})
    email = attributes.get("E-mail", "")  # ✅ Use exact field name from form
    name = attributes.get("Name", "Valued client")  # ✅ Corrected field name
    service = attributes.get("Services Performed", "Not Provided")  # ✅ The type of service
    
    if email:
        send_email(email, name)

    return jsonify({"message": "Webhook received"}), 200

def send_email(to_address, name,service):
    sender_email = "walesalami012@gmail.com"
    sender_password = os.environ.get("EMAIL_PASSWORD")  # ✅ Secure from environment

    body = (
        f"Dear {name},\n\n"
        f"Thank you for requesting our service.\n"
        f"The **{service}** has been completed.\n\n"
        f"If you have any questions, feel free to reply to this email.\n\n"
        f"Best regards,\n"
        f"EoA Support Team"
    )

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
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

