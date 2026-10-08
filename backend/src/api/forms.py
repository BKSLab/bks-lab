"""Rate-limited public subscription and feedback forms."""

from fastapi import APIRouter, Request

from src.core.limiter import limiter
from src.dependencies.services import FeedbackServiceDep, SubscriberServiceDep
from src.schemas.forms import FeedbackRequest, FeedbackResponse, SubscribeRequest, SubscribeResponse

router = APIRouter(tags=["forms"])


@router.post(
    "/feedback", response_model=FeedbackResponse, summary="Send feedback",
    description="Deliver a valid form via SMTP; silently ignore the website honeypot.",
    operation_id="sendFeedback", response_description="Message delivered or honeypot ignored.",
    responses={422: {"description": "Invalid form fields."}, 429: {"description": "Five requests per hour per IP."},
               503: {"description": "SMTP unconfigured or temporarily unavailable."}},
)
@limiter.limit("5/hour")
async def feedback(request: Request, data: FeedbackRequest, service: FeedbackServiceDep) -> FeedbackResponse:
    """Report success only after actual delivery, except for the anti-spam honeypot."""
    await service.send(data)
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
