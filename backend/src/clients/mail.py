"""Bounded SMTP delivery with explicit TLS and certificate verification."""

import asyncio
from email.message import EmailMessage

import aiosmtplib

from src.core.settings import SMTPSettings
from src.exceptions.feedback import MailDeliveryError


class MailClient:
    def __init__(self, settings: SMTPSettings) -> None:
        self.settings = settings

    async def send_feedback(self, *, name: str, email: str, message: str) -> None:
        """Deliver to the configured recipient; user input cannot select recipients.

        Raises:
            MailDeliveryError: Configuration or delivery failed (no automatic retry).
        """
        settings = self.settings
        if not (settings.host and settings.sender and settings.recipient):
            raise MailDeliveryError("SMTP is not configured")
        try:
            mail = EmailMessage()
            mail["Subject"] = "BKS Lab: новое сообщение"
            mail["From"] = settings.sender
            mail["To"] = settings.recipient
            mail["Reply-To"] = email
            mail.set_content(f"Имя: {name}\nEmail: {email}\n\n{message}")
            # A whole-operation deadline bounds connect/TLS/auth/send combined.
            async with asyncio.timeout(settings.timeout):
                refused, _ = await aiosmtplib.send(
                    mail, hostname=settings.host, port=settings.port,
                    username=settings.username or None,
                    password=settings.password.get_secret_value() or None,
                    sender=settings.sender, recipients=[settings.recipient],
                    use_tls=settings.use_tls, start_tls=settings.start_tls,
                    validate_certs=True, timeout=settings.timeout,
                )
            if refused:
                raise MailDeliveryError("SMTP recipient was refused")
        except (aiosmtplib.SMTPException, OSError, TimeoutError, ValueError) as error:
            raise MailDeliveryError("SMTP delivery failed") from error
