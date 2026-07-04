"""
Prediction service — pure functions, no database or FastAPI imports.
All functions operate on plain Python datetime.date objects.

v2: Adds weighted rolling average (6+ cycles), standard deviation,
    confidence intervals, and upgraded confidence levels.
v3: Adds ovulation date and fertile window predictions.
"""

import math
from datetime import date, timedelta

# ── Constants ────────────────────────────────────────────────────────────────

POPULATION_DEFAULT_CYCLE_LENGTH: float = 28.0

# Weights for the weighted rolling average of the most recent 3 gaps.
# Index 0 = most-recent gap weight, index 1 = second-most-recent, etc.
WEIGHTS: list[float] = [0.5, 0.3, 0.2]


# ── Average / weighted average ────────────────────────────────────────────────


def compute_weighted_average(gaps: list[float]) -> float:
    """
    Compute a weighted rolling average of the most recent 3 gaps.

    Uses WEIGHTS = [0.5, 0.3, 0.2]:
        result = gaps[-1] * 0.5 + gaps[-2] * 0.3 + gaps[-3] * 0.2

    Requires len(gaps) >= 3; caller is responsible for ensuring this.
    """
    return gaps[-1] * WEIGHTS[0] + gaps[-2] * WEIGHTS[1] + gaps[-3] * WEIGHTS[2]


def compute_average_cycle_length(
    cycle_start_dates: list[date],
) -> tuple[float, str, str]:
    """
    Given a list of cycle start dates (sorted ascending), compute the average
    cycle length in days based on inter-period gaps (start_date[i+1] - start_date[i]).

    Returns (average_cycle_length, confidence, basis) tuple.

    Cycle count logic:
    - 0 cycles  -> population default 28.0, low, default
    - 1 cycle   -> population default 28.0, low, limited_data
    - 2 cycles  -> blend (gap + 28) / 2, low, limited_data
    - 3-5 cycles -> simple mean of all gaps, medium, personal_average
    - 6+ cycles  -> weighted rolling average of last 3 gaps,
                    medium/high*, personal_average

    *high only when std_dev <= 2.0 (determined in get_prediction()).
    """
    n = len(cycle_start_dates)

    if n == 0:
        return (POPULATION_DEFAULT_CYCLE_LENGTH, "low", "default")

    if n == 1:
        return (POPULATION_DEFAULT_CYCLE_LENGTH, "low", "limited_data")

    # Compute all consecutive gaps (ascending order guaranteed by callers)
    gaps: list[float] = [
        float((cycle_start_dates[i + 1] - cycle_start_dates[i]).days)
        for i in range(n - 1)
    ]

    if n == 2:
        # One gap: blend with population default
        blended = (gaps[0] + POPULATION_DEFAULT_CYCLE_LENGTH) / 2.0
        return (blended, "low", "limited_data")

    # 3-5 cycles (2-4 gaps): simple mean
    if n <= 5:
        mean_gap = sum(gaps) / len(gaps)
        return (mean_gap, "medium", "personal_average")

    # 6+ cycles (5+ gaps): weighted rolling average of the 3 most recent gaps
    weighted_avg = compute_weighted_average(gaps)
    # Confidence will be refined by the orchestrator using std_dev
    return (weighted_avg, "medium", "personal_average")


# ── Standard deviation & confidence interval ─────────────────────────────────


def compute_standard_deviation(gaps: list[float]) -> float:
    """
    Compute the population standard deviation of a list of gap lengths.

    Formula: sqrt( sum((x - mean)^2) / N )

    Requires len(gaps) >= 1; returns 0.0 for a single-element list.
    """
    n = len(gaps)
    if n == 0:
        return 0.0
    mean = sum(gaps) / n
    variance = sum((g - mean) ** 2 for g in gaps) / n
    return math.sqrt(variance)


def compute_range_offset(std_dev: float) -> int:
    """
    Map a standard deviation to a ±offset (in days) for the predicted range.

    - std_dev <= 2.0  → offset = 2
    - std_dev >= 4.0  → offset = 5
    - 2.0 < std_dev < 4.0 → proportional: round(2.0 + (std_dev - 2.0) * 1.5)
    """
    if std_dev <= 2.0:
        return 2
    if std_dev >= 4.0:
        return 5
    return round(2.0 + (std_dev - 2.0) * 1.5)


def compute_predicted_range(
    predicted_start: date | None,
    gaps: list[float],
) -> tuple[date | None, date | None]:
    """
    Compute the earliest/latest bounds of the predicted next period.

    Returns (earliest, latest) dates, or (None, None) if:
    - predicted_start is None, or
    - fewer than 2 gaps are available (std_dev cannot be computed meaningfully)
    """
    if predicted_start is None or len(gaps) < 2:
        return (None, None)

    std_dev = compute_standard_deviation(gaps)
    offset = compute_range_offset(std_dev)
    earliest = predicted_start - timedelta(days=offset)
    latest = predicted_start + timedelta(days=offset)
    return (earliest, latest)


# ── Remaining helpers (unchanged from v1) ────────────────────────────────────


def compute_current_cycle_day(
    most_recent_start: date | None,
    today: date,
) -> int | None:
    """
    Returns (today - most_recent_start).days + 1.
    Returns None if most_recent_start is None.
    """
    if most_recent_start is None:
        return None
    return (today - most_recent_start).days + 1


def compute_predicted_next_start(
    most_recent_start: date | None,
    average_cycle_length: float,
) -> date | None:
    """
    Returns most_recent_start + timedelta(days=round(average_cycle_length)).
    Returns None if most_recent_start is None.
    """
    if most_recent_start is None:
        return None
    return most_recent_start + timedelta(days=round(average_cycle_length))


def compute_ovulation_and_fertile_window(
    predicted_next_period_start: date | None,
) -> tuple[date | None, date | None, date | None]:
    """
    Derive ovulation and fertile window from the predicted next period start.

    Using the standard luteal-phase model:
      predicted_ovulation_date = predicted_next_period_start - 14 days
      fertile_window_start     = predicted_ovulation_date - 5 days
      fertile_window_end       = predicted_ovulation_date + 1 day

    Returns (predicted_ovulation_date, fertile_window_start, fertile_window_end).
    All three are None when predicted_next_period_start is None.

    Note: Past-dated results are returned as-is without suppression.
    Dates may fall in the past if the user is beyond cycle day 14.

    # TODO: refine with BBT data
    """
    if predicted_next_period_start is None:
        return (None, None, None)

    predicted_ovulation_date = predicted_next_period_start - timedelta(days=14)
    fertile_window_start = predicted_ovulation_date - timedelta(days=5)
    fertile_window_end = predicted_ovulation_date + timedelta(days=1)
    return (predicted_ovulation_date, fertile_window_start, fertile_window_end)


# ── Orchestrator ─────────────────────────────────────────────────────────────


def get_prediction(cycle_start_dates: list[date], today: date) -> dict:
    """
    Orchestrates all computations and returns a dict with keys:
        predicted_next_period_start, average_cycle_length, current_cycle_day,
        confidence, basis, predicted_range,
        predicted_ovulation_date, fertile_window_start, fertile_window_end

    predicted_range is a dict with 'earliest' and 'latest' date keys,
    or None when insufficient data exists.
    Ovulation/fertile-window fields are None when predicted_next_period_start
    is None.
    """
    n = len(cycle_start_dates)
    average_cycle_length, confidence, basis = compute_average_cycle_length(
        cycle_start_dates
    )

    most_recent_start: date | None = (
        cycle_start_dates[-1] if cycle_start_dates else None
    )

    current_cycle_day = compute_current_cycle_day(most_recent_start, today)
    predicted_next_period_start = compute_predicted_next_start(
        most_recent_start, average_cycle_length
    )

    # Build gaps list for std_dev / range computation
    gaps: list[float] = []
    if n >= 2:
        gaps = [
            float((cycle_start_dates[i + 1] - cycle_start_dates[i]).days)
            for i in range(n - 1)
        ]

    # Upgrade confidence to 'high' for 6+ cycles with tight std_dev
    if n >= 6 and len(gaps) >= 2:
        std_dev = compute_standard_deviation(gaps)
        if std_dev <= 2.0:
            confidence = "high"

    # Compute predicted range (None when < 3 cycles / < 2 gaps)
    earliest, latest = compute_predicted_range(predicted_next_period_start, gaps)
    predicted_range: dict | None = (
        {"earliest": earliest, "latest": latest}
        if earliest is not None and latest is not None
        else None
    )

    # Ovulation & fertile window (v3)
    predicted_ovulation_date, fertile_window_start, fertile_window_end = (
        compute_ovulation_and_fertile_window(predicted_next_period_start)
    )

    return {
        "predicted_next_period_start": predicted_next_period_start,
        "average_cycle_length": average_cycle_length,
        "current_cycle_day": current_cycle_day,
        "confidence": confidence,
        "basis": basis,
        "predicted_range": predicted_range,
        "predicted_ovulation_date": predicted_ovulation_date,
        "fertile_window_start": fertile_window_start,
        "fertile_window_end": fertile_window_end,
    }
