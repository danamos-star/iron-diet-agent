import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_notification(to_email: str, subject: str, body: str) -> dict:
    """Sends an email containing the meal plan and grocery list to the recipient.
    
    Args:
        to_email: Target recipient email address.
        subject: Email subject line.
        body: Plain text body content of the email.
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    # If using default/placeholder env vars, simulate delivery successfully
    if not sender_email or sender_email in ("your-email@gmail.com", ""):
        print(f"--> [SIMULATED EMAIL DISPATCH] To: {to_email} | Subject: {subject}")
        return {
            "status": "success",
            "message": f"Successfully sent simulated email to {to_email}."
        }

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        return {
            "status": "success",
            "message": f"Successfully sent meal plan and grocery list to {to_email}."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to send email: {str(e)}"
        }