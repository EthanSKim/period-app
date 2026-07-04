from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Cycle, User
from app.schemas import PredictionResponse
from app.services.prediction_service import get_prediction

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("", response_model=PredictionResponse)
def get_predictions(
    today: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionResponse:
    cycles = (
        db.query(Cycle)
        .filter(Cycle.user_id == current_user.id)
        .order_by(Cycle.start_date.asc())
        .all()
    )
    start_dates: list[date] = [c.start_date for c in cycles]
    if today is None:
        today = date.today()
    prediction = get_prediction(start_dates, today)
    return prediction
