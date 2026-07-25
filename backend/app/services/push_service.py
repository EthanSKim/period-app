import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import PushSubscription

logger = logging.getLogger(__name__)


def send_web_push(db: Session, subscription: PushSubscription, data: dict) -> bool:
    """
    Dispatch a web push notification to a specific user subscription.
    If the push service returns 404 or 410, automatically delete the
    subscription from the DB.
    """
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh_key,
                    "auth": subscription.auth_key,
                },
            },
            data=json.dumps(data),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": settings.VAPID_CLAIM_EMAIL,
            },
        )
        return True
    except WebPushException as ex:
        # Check for invalid/expired subscription (404 or 410)
        status_code = ex.response.status_code if ex.response is not None else None
        if status_code in (404, 410):
            logger.info(
                f"Removing invalid subscription {subscription.id} "
                f"(endpoint: {subscription.endpoint}). Status: {status_code}"
            )
            db.delete(subscription)
            db.commit()
        else:
            logger.error(
                f"Failed to send web push for subscription {subscription.id}: {ex}"
            )
        return False
    except Exception as ex:
        logger.error(
            "Unexpected error sending web push for subscription "
            f"{subscription.id}: {ex}"
        )
        return False
