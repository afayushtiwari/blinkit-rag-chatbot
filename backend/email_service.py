"""Optional SMTP email sender for QuickCart invoices.

This module does nothing until EMAIL_ENABLED=true and all SMTP variables are
set in backend/.env. It deliberately returns a status instead of breaking an
otherwise valid checkout when email is unavailable.
"""

import os
import smtplib
from email.message import EmailMessage

from invoice import invoice_filename


def _enabled() -> bool:
    return os.getenv("EMAIL_ENABLED", "false").strip().lower() == "true"


def send_invoice_email(order: dict, invoice_pdf: bytes) -> dict:
    """Send a confirmation email only when SMTP is explicitly configured."""
    if not _enabled():
        return {"status": "disabled", "message": "Email is not configured."}

    required = {
        "SMTP_HOST": os.getenv("SMTP_HOST"),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "SMTP_FROM": os.getenv("SMTP_FROM"),
    }
    missing = [name for name, value in required.items() if not value]
    recipient = order.get("email")
    if not recipient:
        return {"status": "not_requested", "message": "No customer email was provided."}
    if missing:
        return {
            "status": "not_configured",
            "message": f"Missing SMTP configuration: {', '.join(missing)}.",
        }

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"

        message = EmailMessage()
        message["Subject"] = f"QuickCart order confirmed: {order['order_id']}"
        message["From"] = required["SMTP_FROM"]
        message["To"] = recipient
        message.set_content(
            f"Hi {order['customer_name']},\n\n"
            f"Your QuickCart order {order['order_id']} is confirmed. "
            f"Total: Rs. {order['total']:.2f}.\n\n"
            "Your invoice is attached.\n\n"
            "This is a demo checkout email."
        )
        message.add_attachment(
            invoice_pdf,
            maintype="application",
            subtype="pdf",
            filename=invoice_filename(order["order_id"]),
        )

        with smtplib.SMTP(required["SMTP_HOST"], port, timeout=15) as client:
            if use_tls:
                client.starttls()
            client.login(required["SMTP_USERNAME"], required["SMTP_PASSWORD"])
            client.send_message(message)
        return {"status": "sent", "message": f"Invoice sent to {recipient}."}
    except Exception as error:
        return {"status": "failed", "message": f"Invoice email could not be sent: {error}"}
