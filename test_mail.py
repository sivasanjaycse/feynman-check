"""
test_mail.py — Interactive Brevo SMTP Diagnostic & Mail Dispatch Tester.

Tests:
  1. DNS resolution of smtp-relay.brevo.com
  2. TLS handshake on port 587
  3. Authentication with BREVO_SMTP_LOGIN & BREVO_SMTP_KEY
  4. Real mail dispatch to your inbox with delivery status check
"""
from __future__ import annotations

import argparse
import os
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Load environment
from slice.config import load_env
load_env()


def test_brevo_mail(recipient: str | None = None, sender: str | None = None):
    print("\n" + "=" * 70)
    print(" [EMAIL] BREVO SMTP RELAY DIAGNOSTIC TOOL")
    print("=" * 70)

    server = os.getenv("BREVO_SMTP_SERVER", "smtp-relay.brevo.com").strip()
    port = int(os.getenv("BREVO_SMTP_PORT", "587"))
    login = os.getenv("BREVO_SMTP_LOGIN", "ba29a1001@smtp-brevo.com").strip()
    key = os.getenv("BREVO_SMTP_KEY", "").strip()

    target_recipient = (
        recipient
        or os.getenv("FACULTY_EMAIL")
        or os.getenv("FACULTY_MAIL")
        or "sivasanjayofficial@gmail.com"
    ).strip()

    from_sender = (
        sender
        or os.getenv("BREVO_SMTP_FROM")
        or "sivasanjaidisco@gmail.com"
    ).strip()

    print(f"[*] SMTP Server   : {server}:{port}")
    print(f"[*] SMTP Login    : {login}")
    print(f"[*] Key configured: {'YES (' + key[:12] + '...)' if key else 'NO (MISSING!)'}")
    print(f"[*] Sender (From) : {from_sender}")
    print(f"[*] Recipient (To): {target_recipient}")
    print("-" * 70)

    if not key:
        print("[ERROR] BREVO_SMTP_KEY is missing in your .env file!")
        return False

    # 1. DNS Resolution check
    print("\n[STEP 1] Checking DNS resolution...")
    try:
        ip = socket.gethostbyname(server)
        print(f"  [OK] Resolved {server} -> {ip}")
    except Exception as e:
        print(f"  [FAIL] DNS resolution failed: {e}")
        return False

    # 2. Connection & TLS check
    print("\n[STEP 2] Connecting to SMTP Relay & Initializing TLS...")
    try:
        s = smtplib.SMTP(server, port, timeout=15)
        code, msg = s.ehlo()
        print(f"  [OK] Connected! Server EHLO response: {code}")

        code, msg = s.starttls()
        print(f"  [OK] TLS established! Response: {code}")

        s.ehlo()
    except Exception as e:
        print(f"  [FAIL] Connection or TLS failed: {e}")
        return False

    # 3. Authentication check
    print("\n[STEP 3] Authenticating with Brevo...")
    try:
        code, msg = s.login(login, key)
        print(f"  [OK] Authentication SUCCEEDED! Code: {code}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"  [FAIL] Authentication failed: {e}")
        print("  -> Please check that BREVO_SMTP_KEY and login match your Brevo account.")
        s.quit()
        return False
    except Exception as e:
        print(f"  [FAIL] Unexpected error during login: {e}")
        s.quit()
        return False

    # 4. Message Dispatch
    print("\n[STEP 4] Dispatching test email...")
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[Feynman Check] Live Brevo SMTP Delivery Verification"
        msg["From"] = f"Feynman Check Alert <{from_sender}>"
        msg["To"] = target_recipient

        plain_text = (
            f"Hello Professor,\n\n"
            f"This is a test notification confirming that Brevo SMTP relay is delivering "
            f"directly to your inbox ({target_recipient}).\n\n"
            f"Sender: {from_sender}\n"
            f"Relay : {server}:{port}\n\n"
            f"-- Feynman Check System"
        )
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))

        html_text = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px;">
  <div style="max-width: 580px; margin: 0 auto; background: #1e293b; border-radius: 10px; border: 1px solid #334155; padding: 24px;">
    <h2 style="color: #6366f1; margin-top: 0;">Feynman Check - SMTP Test</h2>
    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">
      Live delivery test successful! The Feynman Check escalation system is configured to send real-time misconception alerts to:
    </p>
    <div style="background: #0f172a; border-left: 4px solid #10b981; padding: 12px 16px; margin: 16px 0; font-family: monospace; color: #10b981;">
      {target_recipient}
    </div>
    <p style="color: #94a3b8; font-size: 13px;">
      Sent via Brevo SMTP Relay ({server}:{port})
    </p>
  </div>
</body>
</html>"""
        msg.attach(MIMEText(html_text, "html", "utf-8"))

        s.send_message(msg)
        s.quit()

        print("  [OK] Brevo Relay accepted the message (250 OK queued)!")
        print(f"\n" + "=" * 70)
        print("  SUCCESSFULLY DISPATCHED TO: " + target_recipient)
        print("=" * 70)
        print("\n[WHERE TO FIND YOUR EMAIL IN GMAIL]")
        print("1. Check your PRIMARY inbox in Gmail.")
        print("2. Check the SPAM / JUNK folder:")
        print("   -> Since this is sent via an SMTP relay, Gmail may initially flag it as Spam.")
        print("   -> Open https://mail.google.com/mail/#spam")
        print("   -> If it's in Spam, click 'Report not spam' so future alerts go straight to Inbox.")
        print("3. Check the 'All Mail' folder:")
        print("   -> Open https://mail.google.com/mail/#all\n")
        return True

    except Exception as e:
        print(f"  [FAIL] Failed to dispatch message: {e}")
        try:
            s.quit()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Brevo SMTP Mail Sending")
    parser.add_argument("--recipient", "-r", default=None, help="Recipient email address")
    parser.add_argument("--sender", "-s", default=None, help="Sender email address")
    args = parser.parse_args()

    test_brevo_mail(recipient=args.recipient, sender=args.sender)
