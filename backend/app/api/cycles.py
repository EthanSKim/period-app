from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Cycle, User
from app.schemas import CycleCreate, CycleResponse, CycleUpdate

router = APIRouter(prefix="/cycles", tags=["cycles"])


def recalculate_cycle_lengths(user_id: int, db: Session):
    # Query all cycles for the user from the database, ordered by start_date ascending.
    cycles = (
        db.query(Cycle)
        .filter(Cycle.user_id == user_id)
        .order_by(Cycle.start_date.asc())
        .all()
    )

    # For each cycle at index i (previous):
    for i in range(len(cycles) - 1):
        prev_cycle = cycles[i]
        subseq_cycle = cycles[i + 1]
        # If there is a subsequent cycle at i + 1 (current)
        # and it has an end_date (i.e., subseq_cycle.end_date is not None),
        # set prev_cycle.cycle_length to start_date difference.
        if subseq_cycle.end_date is not None:
            prev_cycle.cycle_length = (
                subseq_cycle.start_date - prev_cycle.start_date
            ).days
        else:
            # Otherwise, set prev_cycle.cycle_length = None.
            prev_cycle.cycle_length = None

    # For the last cycle (index len(cycles)-1), cycle_length is always None.
    if cycles:
        cycles[-1].cycle_length = None

    # Save/commit all recalculated lengths to the DB.
    db.commit()


@router.post("", response_model=CycleResponse, status_code=status.HTTP_201_CREATED)
def create_cycle(
    cycle_in: CycleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Create a cycle record owned by the authenticated user.
    new_cycle = Cycle(
        user_id=current_user.id,
        start_date=cycle_in.start_date,
        end_date=cycle_in.end_date,
    )
    db.add(new_cycle)
    db.commit()
    db.refresh(new_cycle)

    # Recalculate cycle lengths for all cycles owned by the authenticated user.
    recalculate_cycle_lengths(current_user.id, db)

    # Refresh to return updated cycle_length
    db.refresh(new_cycle)
    return new_cycle


@router.get("", response_model=list[CycleResponse])
def get_cycles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Return all cycles for the current user ordered by start_date descending.
    return (
        db.query(Cycle)
        .filter(Cycle.user_id == current_user.id)
        .order_by(Cycle.start_date.desc())
        .all()
    )


@router.patch("/{id}", response_model=CycleResponse)
def update_cycle(
    id: int,
    cycle_update: CycleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validates that the cycle exists
    cycle = db.query(Cycle).filter(Cycle.id == id).first()
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found",
        )

    # Validates ownership
    if cycle.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this cycle",
        )

    update_data = cycle_update.model_dump(exclude_unset=True)

    # Validates that the updated end_date is after the updated start_date
    new_start_date = update_data.get("start_date", cycle.start_date)
    new_end_date = update_data.get("end_date", cycle.end_date)

    if new_end_date is not None and new_end_date <= new_start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date",
        )

    # Apply updates
    for key, value in update_data.items():
        setattr(cycle, key, value)

    db.commit()
    db.refresh(cycle)

    # Recalculates cycle lengths for the user after updating.
    recalculate_cycle_lengths(current_user.id, db)

    db.refresh(cycle)
    return cycle
