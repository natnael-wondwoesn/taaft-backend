import os
import sys
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

print("Current directory:", os.getcwd())
print("Email settings from environment:")
print(f"EMAIL_ENABLED: {os.getenv('EMAIL_ENABLED')}")
print(f"SMTP_SERVER: {os.getenv('SMTP_SERVER')}")
print(f"SMTP_PORT: {os.getenv('SMTP_PORT')}")
print(f"SMTP_USERNAME: {os.getenv('SMTP_USERNAME')}")
print(f"SMTP_PASSWORD: {'[Set]' if os.getenv('SMTP_PASSWORD') else '[Not Set]'}")
print(f"EMAIL_FROM: {os.getenv('EMAIL_FROM')}")

# DO NOT modify these values - use the values from your .env file
# The values below are just placeholders for documentation
"""
# Reminder: Your .env file should contain these settings with proper values:
EMAIL_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=natnael.wondwoesn@gmail.com
SMTP_PASSWORD=your-16-digit-app-password
EMAIL_FROM=natnael.wondwoesn@gmail.com
"""

# NOTE: Make sure you have set up an App Password in your Google Account:
# 1. Go to https://myaccount.google.com/security
# 2. Under "Signing in to Google", select "App passwords" (requires 2-Step Verification)
# 3. Generate a new app password for your application
# 4. Use that password in your .env file

try:
    # Now import the module that uses these settings
    from config import settings

    print("\nSettings after import:")
    print(f"EMAIL_ENABLED: {settings.EMAIL_ENABLED}")
    print(f"SMTP_SERVER: {settings.SMTP_SERVER}")
    print(f"SMTP_PORT: {settings.SMTP_PORT}")
    print(f"SMTP_USERNAME: {settings.SMTP_USERNAME}")
    print(f"EMAIL_FROM: {settings.EMAIL_FROM}")

    # Check if password is set (don't log the actual password)
    if settings.SMTP_PASSWORD:
        print("SMTP_PASSWORD: [Set]")
    else:
        print("SMTP_PASSWORD: [Not Set]")

    try:
        from services.email_service import send_email

        def test_send_email(recipient_email):
            """Test sending an email"""
            print(f"Attempting to send test email to {recipient_email}...")

            subject = "Test Email from TAAFT System"
            html_content = """
            <html>
            <body>
                <h2>Test Email</h2>
                <p>This is a test email from the TAAFT system to verify that email sending is working correctly.</p>
            </body>
            </html>
            """

            result = send_email(recipient_email, subject, html_content)
            if result:
                print("✅ Test email sent successfully!")
            else:
                print("❌ Failed to send test email. Check logs for details.")

        # If an email address is provided as argument, try to send a test email
        if len(sys.argv) > 1:
            recipient_email = sys.argv[1]
            test_send_email(recipient_email)
        else:
            print(
                "No recipient email provided. To test email sending, run: python email_test.py your-email@example.com"
            )

    except ImportError as e:
        print(f"Failed to import email_service: {e}")
        print(
            "Check that the file path is correct and the services directory is in your Python path."
        )

except ImportError as e:
    print(f"Failed to import config: {e}")
    print(
        "Make sure you're running this script from the correct directory (app folder)."
    )
