import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from ..config import settings

logger = logging.getLogger(__name__)


def send_email(
    to_email: str, subject: str, html_content: str, text_content: str = None
) -> bool:
    """
    Send an email using SMTP settings from config.

    Args:
        to_email: The recipient's email address
        subject: The email subject
        html_content: HTML content of the email
        text_content: Plain text content (optional, will use a stripped version of html_content if not provided)

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Skip if email is not enabled in settings
    if not settings.EMAIL_ENABLED:
        logger.info(
            f"Email sending is disabled. Would have sent email to {to_email} with subject '{subject}'"
        )
        return False

    # Skip if SMTP settings are not configured
    if (
        not settings.SMTP_SERVER
        or not settings.SMTP_USERNAME
        or not settings.SMTP_PASSWORD
    ):
        logger.warning("SMTP settings not configured. Email not sent.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email

    # Create plain text version if not provided
    if text_content is None:
        # Very simple conversion - in production you might want a proper HTML to text converter
        text_content = (
            html_content.replace("<br>", "\n").replace("</p>", "\n").replace("<p>", "")
        )
        import re

        text_content = re.sub(r"<[^>]*>", "", text_content)

    # Attach parts to message
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")
    message.attach(part1)
    message.attach(part2)

    try:
        # Connect to SMTP server
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()  # Secure the connection
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

        # Send email
        server.sendmail(settings.EMAIL_FROM, to_email, message.as_string())
        server.quit()

        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False


def send_password_reset_email(to_email: str, reset_token: str, base_url: str) -> bool:
    """
    Send a password reset email with a reset link.

    Args:
        to_email: The recipient's email address
        reset_token: The password reset token
        base_url: The base URL of the application

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    reset_url = f"{base_url}/reset-password?token={reset_token}"

    subject = "Password Reset Request"

    html_content = f"""
    <html>
    <body>
        <p>Hello,</p>
        <p>You requested a password reset for your account. Please use the link below to reset your password:</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>If you did not request this password reset, please ignore this email.</p>
        <p>The link will expire in 30 minutes.</p>
        <p>Thank you,<br>TAAFT Team</p>
    </body>
    </html>
    """

    text_content = f"""
    Hello,
    
    You requested a password reset for your account. Please use the link below to reset your password:
    
    {reset_url}
    
    If you did not request this password reset, please ignore this email.
    
    The link will expire in 30 minutes.
    
    Thank you,
    TAAFT Team
    """

    return send_email(to_email, subject, html_content, text_content)


def send_verification_email(
    to_email: str, verification_token: str, base_url: str
) -> bool:
    """
    Send an email verification email with a verification link.

    Args:
        to_email: The recipient's email address
        verification_token: The email verification token
        base_url: The base URL of the application

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    verification_url = f"{base_url}/verify-email?token={verification_token}"

    subject = "Verify Your Email Address"

    html_content = f"""
    <html>
    <body>
        <p>Hello,</p>
        <p>Thank you for registering. Please verify your email address by clicking the link below:</p>
        <p><a href="{verification_url}">Verify Email</a></p>
        <p>If you did not create an account, please ignore this email.</p>
        <p>Thank you,<br>TAAFT Team</p>
    </body>
    </html>
    """

    text_content = f"""
    Hello,
    
    Thank you for registering. Please verify your email address by clicking the link below:
    
    {verification_url}
    
    If you did not create an account, please ignore this email.
    
    Thank you,
    TAAFT Team
    """

    return send_email(to_email, subject, html_content, text_content)
