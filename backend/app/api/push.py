from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.database import get_db
from app.models import PushSubscription, User
from app.schemas import (
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    PushSubscriptionResponse,
)

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
def get_vapid_public_key():
    """
    Expose the VAPID public key for the frontend to create push subscriptions.
    """
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post(
    "/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def subscribe(
    payload: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save or update a push subscription for the authenticated user.
    """
    # Check if this endpoint already exists for the user
    sub = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == payload.endpoint,
        )
        .first()
    )

    if sub:
        # Update existing subscription keys
        sub.p256dh_key = payload.keys.p256dh
        sub.auth_key = payload.keys.auth
        db.commit()
        db.refresh(sub)
        return sub
    else:
        # Create a new subscription
        new_sub = PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh_key=payload.keys.p256dh,
            auth_key=payload.keys.auth,
        )
        db.add(new_sub)
        db.commit()
        db.refresh(new_sub)
        return new_sub


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    payload: PushSubscriptionDelete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a push subscription matching the endpoint for the authenticated user.
    """
    sub = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == payload.endpoint,
        )
        .first()
    )

    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for this user",
        )

    db.delete(sub)
    db.commit()
    return


@router.get("/subscriptions", response_model=list[PushSubscriptionResponse])
def get_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Admin/debug endpoint: List active subscriptions for the authenticated user.
    """
    return (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id)
        .all()
    )
