import os
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
    # Log debug information about email configuration
    logger.info(
        f"Email configuration: ENABLED={settings.EMAIL_ENABLED}, SERVER={settings.SMTP_SERVER}, PORT={settings.SMTP_PORT}"
    )

    # Skip if email is not enabled in settings
    if not settings.EMAIL_ENABLED:
        logger.warning(
            f"Email sending is disabled. Would have sent email to {to_email} with subject '{subject}'"
        )
        return False

    # Skip if SMTP settings are not configured
    if (
        not settings.SMTP_SERVER
        or not settings.SMTP_USERNAME
        or not settings.SMTP_PASSWORD
    ):
        logger.warning(
            f"SMTP settings not configured. SERVER={settings.SMTP_SERVER}, USERNAME={settings.SMTP_USERNAME}, PASSWORD={'*****' if settings.SMTP_PASSWORD else 'Not set'}"
        )
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
        logger.info(
            f"Attempting to connect to SMTP server: {settings.SMTP_SERVER}:{settings.SMTP_PORT}"
        )
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()  # Secure the connection
        logger.info(f"Attempting SMTP login with username: {settings.SMTP_USERNAME}")
        server.login(settings.SMTP_USERNAME, "hxndgvqecwvpvigo")

        # Send email
        logger.info(f"Sending email from {settings.EMAIL_FROM} to {to_email}")
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
    # Remove trailing slash from base_url if present to prevent double slashes
    base_url = os.getenv("FRONTEND_URL", "https://taaft-development.vercel.app")
    if base_url.endswith("/"):
        base_url = base_url.rstrip("/")

    # Get the backend URL for token validation
    backend_url = os.getenv("BASE_URL", "https://taaft-backend.onrender.com")
    if backend_url.endswith("/"):
        backend_url = backend_url.rstrip("/")

    # Create a reset URL that goes through the backend validation first
    reset_url = f"{backend_url}/reset-password?token={reset_token}"

    subject = "Password Reset Request"

    html_content = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-container {{
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            }}
            .header {{
                background-color: #4A6FFF;
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .content {{
                background-color: #FFFFFF;
                padding: 20px 30px;
            }}
            .button {{
                display: inline-block;
                background-color: #4A6FFF;
                color: white;
                text-decoration: none;
                padding: 12px 24px;
                border-radius: 4px;
                margin: 20px 0;
                font-weight: bold;
            }}
            .footer {{
                background-color: #F8F9FA;
                padding: 15px;
                text-align: center;
                font-size: 12px;
                color: #6C757D;
            }}
            .reset-url {{
                word-break: break-all;
                font-size: 14px;
                color: #6C757D;
                margin-top: 10px;
            }}
            .expires {{
                margin-top: 20px;
                padding: 10px;
                background-color: #FFF8E1;
                border-radius: 4px;
                font-size: 14px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h2>Password Reset</h2>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>We received a request to reset your password for your TAAFT account. Click the button below to set a new password:</p>
                
                <center><a href="{reset_url}" class="button">Reset Password</a></center>
                
                <p class="expires">This link will expire in 30 minutes.</p>
                
                <p>If you didn't request a password reset, you can safely ignore this email.</p>
                
                <p>If the button above doesn't work, copy and paste the following URL into your browser:</p>
                <p class="reset-url">{reset_url}</p>
                
                <p>Thank you,<br>The TAAFT Team</p>
            </div>
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>&copy; {2025} TAAFT. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    TAAFT - Password Reset Request
    
    Hello,
    
    We received a request to reset your password for your TAAFT account. Please use the link below to set a new password:
    
    {reset_url}
    
    This link will expire in 30 minutes.
    
    If you didn't request a password reset, you can safely ignore this email.
    
    Thank you,
    The TAAFT Team
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
    # Remove trailing slash from base_url if present to prevent double slashes
    if base_url.endswith("/"):
        base_url = base_url.rstrip("/")

    verification_url = f"{base_url}/verify-email?token={verification_token}"

    subject = "Verify Your Email Address"

    html_content = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-container {{
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            }}
            .header {{
                background-color: #4A6FFF;
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .content {{
                background-color: #FFFFFF;
                padding: 20px 30px;
            }}
            .button {{
                display: inline-block;
                background-color: #4A6FFF;
                color: white;
                text-decoration: none;
                padding: 12px 24px;
                border-radius: 4px;
                margin: 20px 0;
                font-weight: bold;
            }}
            .footer {{
                background-color: #F8F9FA;
                padding: 15px;
                text-align: center;
                font-size: 12px;
                color: #6C757D;
            }}
            .verification-url {{
                word-break: break-all;
                font-size: 14px;
                color: #6C757D;
                margin-top: 10px;
            }}
            .benefits {{
                margin: 20px 0;
                background-color: #F1F8FF;
                border-radius: 6px;
                padding: 15px;
            }}
            .benefits ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            .welcome {{
                font-size: 18px;
                font-weight: 500;
                color: #4A6FFF;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h2>Email Verification</h2>
            </div>
            <div class="content">
                <p class="welcome">Welcome to TAAFT!</p>
                <p>Thank you for creating an account. To complete your registration and access all features, please verify your email address by clicking the button below:</p>
                
                <center><a href="{verification_url}" class="button">Verify Email Address</a></center>
                
                <div class="benefits">
                    <p><strong>Benefits of verifying your email:</strong></p>
                    <ul>
                        <li>Access to all TAAFT features</li>
                        <li>Receive important notifications</li>
                        <li>Reset your password if needed</li>
                        <li>Secure your account</li>
                    </ul>
                </div>
                
                <p>If the button above doesn't work, copy and paste the following URL into your browser:</p>
                <p class="verification-url">{verification_url}</p>
                
                <p>If you did not create an account with TAAFT, you can safely ignore this email.</p>
                
                <p>Thank you,<br>The TAAFT Team</p>
            </div>
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>&copy; {2025} TAAFT. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    TAAFT - Email Verification
    
    Welcome to TAAFT!
    
    Thank you for creating an account. To complete your registration and access all features, please verify your email address by clicking the link below:
    
    {verification_url}
    
    Benefits of verifying your email:
    - Access to all TAAFT features
    - Receive important notifications
    - Reset your password if needed
    - Secure your account
    
    If you did not create an account with TAAFT, you can safely ignore this email.
    
    Thank you,
    The TAAFT Team
    """

    return send_email(to_email, subject, html_content, text_content)


def send_login_code_email(to_email: str, login_code: str) -> bool:
    """
    Send a one-time login code for secure authentication.

    Args:
        to_email: The recipient's email address
        login_code: The one-time login code

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    subject = "Your One-Time Login Code"

    html_content = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-container {{
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            }}
            .header {{
                background-color: #4A6FFF;
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .content {{
                background-color: #FFFFFF;
                padding: 20px 30px;
            }}
            .code-container {{
                margin: 25px 0;
                text-align: center;
            }}
            .code {{
                font-family: 'Courier New', monospace;
                font-size: 36px;
                font-weight: bold;
                letter-spacing: 5px;
                color: #4A6FFF;
                padding: 15px 20px;
                background-color: #F1F8FF;
                border-radius: 6px;
                border: 1px dashed #4A6FFF;
                display: inline-block;
            }}
            .footer {{
                background-color: #F8F9FA;
                padding: 15px;
                text-align: center;
                font-size: 12px;
                color: #6C757D;
            }}
            .expires {{
                margin-top: 15px;
                padding: 10px;
                background-color: #FFF8E1;
                border-radius: 4px;
                font-size: 14px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h2>One-Time Login Code</h2>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>We received a request to log in to your TAAFT account. Please use the following code to complete your login:</p>
                
                <div class="code-container">
                    <div class="code">{login_code}</div>
                </div>
                
                <p class="expires">This code will expire in 10 minutes.</p>
                
                <p>If you didn't request this code, please ignore this email. Someone may have entered your email address by mistake.</p>
                
                <p>Thank you,<br>The TAAFT Team</p>
            </div>
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>&copy; {2025} TAAFT. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    TAAFT - Your One-Time Login Code
    
    Hello,
    
    We received a request to log in to your TAAFT account. Please use the following code to complete your login:
    
    {login_code}
    
    This code will expire in 10 minutes.
    
    If you didn't request this code, please ignore this email. Someone may have entered your email address by mistake.
    
    Thank you,
    The TAAFT Team
    """

    return send_email(to_email, subject, html_content, text_content)
