"""Feedback use-case: silently discard the honeypot and report delivery truthfully."""

from src.clients.mail import MailClient
from src.exceptions.feedback import FeedbackUnavailableError, MailDeliveryError
from src.schemas.forms import FeedbackRequest


class FeedbackService:
    def __init__(self, mail_client: MailClient) -> None:
        self.mail_client = mail_client

    async def send(self, data: FeedbackRequest) -> None:
        """Send a genuine request once, or report that delivery is unavailable."""
        if data.website:
            return
        try:
            await self.mail_client.send_feedback(
                name=data.name, email=data.email, message=data.message
            )
        except MailDeliveryError as error:
            raise FeedbackUnavailableError from error
