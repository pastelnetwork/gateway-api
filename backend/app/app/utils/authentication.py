import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
import string
import secrets

import emails
from emails.template import JinjaTemplate
from jose import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(
    email_to: str,
    subject_template: str = "",
    html_template: str = "",
    environment: Dict[str, Any] = {},
) -> None:
    assert settings.EMAILS_ENABLED, "no provided configuration for email variables"
    message = emails.Message(
        subject=JinjaTemplate(subject_template),
        html=JinjaTemplate(html_template),
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, render=environment, smtp=smtp_options)
    logger.info(f"send email result: {response}")


def send_alert_email(alert_message: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - ALERT!!!"
    send_email(
        email_to=settings.ALERTS_EMAIL_RCPT,
        subject_template=subject,
        html_template=f"<p>ALERT: {alert_message}</p>",
        environment={"project_name": settings.PROJECT_NAME, "email": settings.ALERTS_EMAIL_RCPT},
    )


def send_test_email(email_to: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    with open(Path(settings.EMAIL_TEMPLATES_DIR) / "test_email.html") as f:
        template_str = f.read()
    send_email(
        email_to=email_to,
        subject_template=subject,
        html_template=template_str,
        environment={"project_name": settings.PROJECT_NAME, "email": email_to},
    )


def send_reset_password_email(email_to: str, email: str, token: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    project_root_directory = Path(__file__).parent.parent.absolute()
    with open(project_root_directory / Path(settings.EMAIL_TEMPLATES_DIR) / "reset_password.html") as f:
        template_str = f.read()
    server_host = settings.FRONTEND_URL
    link = f"{server_host}/reset-password?token={token}"

    send_email(
        email_to=email_to,
        subject_template=subject,
        html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )


def send_new_account_email(email_to: str, username: str, password: str) -> None:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    with open(Path(settings.EMAIL_TEMPLATES_DIR) / "new_account.html") as f:
        template_str = f.read()
    link = settings.FRONTEND_URL
    send_email(
        email_to=email_to,
        subject_template=subject,
        html_template=template_str,
        environment={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": link,
        },
    )


def send_new_account_with_key_email(email_to: str, wallet_id: str, wallet_key_index: int, key_salt: str) -> None:
    subject = f"Action Required - Please Verify Your Email"
    frontend = settings.FRONTEND_URL
    link = f"{frontend}verify_user_with_key?i={wallet_key_index}&s={key_salt}"
    body = (f'Welcome to Pastel Portal! We’re excited to have you on board.<br/>'
            f'To get started, please verify your email address by clicking the link below:<br/>'
            f'<a href="{link}">Verify Email</a><br/><br/>'
            f'Or copy and paste the following link into your browser:<br/>'
            f'{link}<br/><br/>'
            f'Your Wallet ID is: {wallet_id}<br/><br/>')
    send_email(
        email_to=email_to,
        subject_template=subject,
        html_template=body,
        environment={"project_name": settings.PROJECT_NAME, "email": email_to,},
    )


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.utcnow()
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email}, settings.SECRET_KEY, algorithm="HS256",
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return decoded_token["email"]
    except jwt.JWTError:
        return None
