"""
Test script for email verification
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
    from app.services.email_service import send_verification_email
    from app.auth.utils import create_access_token
    import datetime

    print("\nSettings from config:")
    print(f"EMAIL_ENABLED: {settings.EMAIL_ENABLED}")
    print(f"SMTP_SERVER: {settings.SMTP_SERVER}")
    print(f"SMTP_PORT: {settings.SMTP_PORT}")
    print(f"SMTP_USERNAME: {settings.SMTP_USERNAME}")
    print(f"EMAIL_FROM: {settings.EMAIL_FROM}")
    print(f"SMTP_PASSWORD: {'[Set]' if settings.SMTP_PASSWORD else '[Not Set]'}")

    def test_verification_email(recipient_email):
        """Test sending a verification email"""
        print(f"\nAttempting to send verification email to {recipient_email}...")

        # Create a dummy user ID and verification token
        dummy_user_id = "test_user_12345"
        verification_token = create_access_token(
            data={"sub": dummy_user_id, "purpose": "email_verification"}
        )

        # Use localhost as the base URL for testing
        base_url = "http://localhost:8000"

        # Send verification email
        result = send_verification_email(recipient_email, verification_token, base_url)

        if result:
            print("✅ Verification email sent successfully!")
            print(f"Verification token for testing: {verification_token}")
        else:
            print("❌ Failed to send verification email. Check the logs for details.")

    # Check if recipient email was provided
    if len(sys.argv) > 1:
        test_verification_email(sys.argv[1])
    else:
        print("\nNo recipient email provided.")
        print("Usage: python test_verification_email.py your-email@example.com")

except Exception as e:
    print(f"\nError: {e}")
    print("Make sure you're running this script from the project root directory.")
