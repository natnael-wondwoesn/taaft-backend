"""
Test script for passwordless login with one-time codes
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

try:
    # Import app modules
    from app.config import settings
    from app.services.email_service import send_login_code_email
    import random

    print("\nSettings from config:")
    print(f"EMAIL_ENABLED: {settings.EMAIL_ENABLED}")
    print(f"SMTP_SERVER: {settings.SMTP_SERVER}")
    print(f"SMTP_PORT: {settings.SMTP_PORT}")
    print(f"SMTP_USERNAME: {settings.SMTP_USERNAME}")
    print(f"EMAIL_FROM: {settings.EMAIL_FROM}")
    print(f"SMTP_PASSWORD: {'[Set]' if settings.SMTP_PASSWORD else '[Not Set]'}")

    def test_login_code_email(recipient_email):
        """Test sending a login code email"""
        print(f"\nAttempting to send login code test email to {recipient_email}...")

        # Generate a 6-digit login code
        login_code = "".join(random.choice("0123456789") for _ in range(6))

        # Send login code email
        result = send_login_code_email(recipient_email, login_code)

        if result:
            print("✅ Login code email sent successfully!")
            print(f"The login code for testing is: {login_code}")
        else:
            print("❌ Failed to send login code email. Check the logs for details.")

    # Check if recipient email was provided
    if len(sys.argv) > 1:
        test_login_code_email(sys.argv[1])
    else:
        print("\nNo recipient email provided.")
        print("Usage: python test_login_code.py your-email@example.com")

except Exception as e:
    print(f"\nError: {e}")
    print("Make sure you're running this script from the project root directory.")
