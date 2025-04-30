"""
Email Test Script

This script tests sending emails through the application's email service.
Run it from the project root directory.
"""

import sys
import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the current directory to the Python path
sys.path.insert(0, os.getcwd())

# Load environment variables
load_dotenv()

print("Current directory:", os.getcwd())
print("Email settings from environment:")
print(f"EMAIL_ENABLED: {os.getenv('EMAIL_ENABLED')}")
print(f"SMTP_SERVER: {os.getenv('SMTP_SERVER')}")
print(f"SMTP_PORT: {os.getenv('SMTP_PORT')}")
print(f"SMTP_USERNAME: {os.getenv('SMTP_USERNAME')}")
print(f"SMTP_PASSWORD: {os.getenv('SMTP_PASSWORD')}")
print(f"EMAIL_FROM: {os.getenv('EMAIL_FROM')}")

print("\nNOTE: For Gmail, you need to use an App Password:")
print("1. Go to your Google Account settings (https://myaccount.google.com/security)")
print("2. Enable 2-Step Verification if not already enabled")
print("3. Select 'App passwords' under 'Signing in to Google'")
print("4. Generate a new app password for 'Mail'")
print("5. Update your .env file with this password")

try:
    # Import our application's modules
    from app.config import settings
    from app.services.email_service import send_email

    print("\nSettings from config:")
    print(f"EMAIL_ENABLED: {settings.EMAIL_ENABLED}")
    print(f"SMTP_SERVER: {settings.SMTP_SERVER}")
    print(f"SMTP_PORT: {settings.SMTP_PORT}")
    print(f"SMTP_USERNAME: {settings.SMTP_USERNAME}")
    print(f"EMAIL_FROM: {settings.EMAIL_FROM}")
    print(f"SMTP_PASSWORD: {'[Set]' if settings.SMTP_PASSWORD else '[Not Set]'}")

    def test_send_email(recipient_email):
        print(f"\nAttempting to send test email to {recipient_email}...")

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
            print("❌ Failed to send test email. Check the logs for details.")

    # Check if recipient email was provided
    if len(sys.argv) > 1:
        test_send_email(sys.argv[1])
    else:
        print("\nNo recipient email provided.")
        print("Usage: python test_email.py your-email@example.com")

except Exception as e:
    print(f"\nError: {e}")
    print("Make sure you're running this script from the project root directory.")
