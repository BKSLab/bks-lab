"""Rate-limited public subscription and feedback forms."""

from fastapi import APIRouter, Request

from src.core.limiter import limiter
from src.dependencies.services import FeedbackServiceDep, SubscriberServiceDep
from src.schemas.forms import FeedbackRequest, FeedbackResponse, SubscribeRequest, SubscribeResponse

router = APIRouter(tags=["forms"])


@router.post(
    "/feedback", response_model=FeedbackResponse, summary="Send feedback",
    description="Store a valid message for the admin inbox; silently ignore the website honeypot.",
    operation_id="sendFeedback", response_description="Message stored or honeypot ignored.",
    responses={422: {"description": "Invalid form fields."}, 429: {"description": "Five requests per hour per IP."},
               503: {"description": "Message storage temporarily unavailable."}},
)
@limiter.limit("5/hour")
async def feedback(request: Request, data: FeedbackRequest, service: FeedbackServiceDep) -> FeedbackResponse:
    """Report success after committing the message, except for the anti-spam honeypot."""
    await service.submit(data)
    return FeedbackResponse()


@router.post(
    "/subscribe", response_model=SubscribeResponse, summary="Subscribe to updates",
    description="Store a normalized address once without revealing existing subscriptions.",
    operation_id="subscribe", response_description="Email registered or honeypot ignored.",
    responses={422: {"description": "Invalid email."}, 429: {"description": "Five requests per hour per IP."},
               500: {"description": "Subscriber storage unavailable."}},
)
@limiter.limit("5/hour")
async def subscribe(request: Request, data: SubscribeRequest, service: SubscriberServiceDep) -> SubscribeResponse:
    """Idempotently subscribe a visitor after honeypot validation."""
    await service.subscribe(data)
    return SubscribeResponse()
