import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_notification(to_email: str, subject: str, body: str) -> str:
    """Sends an email containing the meal plan and shopping list to the specified recipient.
    
    Args:
        to_email: Target email address.
        subject: Email subject line.
        body: Content of the email.
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    if not sender_email or sender_email == "your-email@gmail.com":
        return f"[Simulated Delivery] Email successfully dispatched to {to_email} with subject: '{subject}'."

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

        return f"Successfully sent meal plan and grocery list to {to_email}!"
    except Exception as e:
        return f"Failed to send email: {str(e)}"