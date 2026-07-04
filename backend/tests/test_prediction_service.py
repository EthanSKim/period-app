"""
Unit tests for prediction_service.py — no HTTP, no database.
All tests exercise the pure functions directly.

Covers both v1 (basic average, current_cycle_day, predicted_next_start)
and v2 (weighted average, std_dev, range offset, confidence intervals,
predicted_range, 'high' confidence) logic.
"""

from datetime import date, timedelta

import pytest

from app.services.prediction_service import (
    POPULATION_DEFAULT_CYCLE_LENGTH,
    WEIGHTS,
    compute_average_cycle_length,
    compute_current_cycle_day,
    compute_predicted_next_start,
    compute_predicted_range,
    compute_range_offset,
    compute_standard_deviation,
    compute_weighted_average,
    get_prediction,
)

# ---------------------------------------------------------------------------
# compute_average_cycle_length
# ---------------------------------------------------------------------------


class TestComputeAverageCycleLength:
    def test_zero_cycles_returns_default(self) -> None:
        avg, confidence, basis = compute_average_cycle_length([])
        assert avg == 28.0
        assert confidence == "low"
        assert basis == "default"

    def test_one_cycle_returns_population_default_limited_data(self) -> None:
        avg, confidence, basis = compute_average_cycle_length([date(2026, 1, 1)])
        assert avg == 28.0
        assert confidence == "low"
        assert basis == "limited_data"

    def test_two_cycles_30_day_gap_blends_with_population_default(self) -> None:
        # gap = 30 days, blended = (30 + 28) / 2 = 29.0
        dates = [date(2026, 1, 1), date(2026, 1, 31)]
        avg, confidence, basis = compute_average_cycle_length(dates)
        assert avg == 29.0
        assert confidence == "low"
        assert basis == "limited_data"

    def test_two_cycles_28_day_gap_blends_to_28(self) -> None:
        dates = [date(2026, 1, 1), date(2026, 1, 29)]
        avg, confidence, basis = compute_average_cycle_length(dates)
        assert avg == 28.0
        assert confidence == "low"
        assert basis == "limited_data"

    def test_three_cycles_gaps_30_28_gives_personal_average(self) -> None:
        # dates: Jan 1, Jan 31 (+30), Feb 28 (+28)
        dates = [date(2026, 1, 1), date(2026, 1, 31), date(2026, 2, 28)]
        avg, confidence, basis = compute_average_cycle_length(dates)
        assert avg == pytest.approx(29.0)
        assert confidence == "medium"
        assert basis == "personal_average"

    def test_four_cycles_gaps_28_30_26_gives_28(self) -> None:
        # gaps: 28, 30, 26 → mean = 84/3 = 28.0
        d0 = date(2026, 1, 1)
        dates = [
            d0,
            d0 + timedelta(days=28),
            d0 + timedelta(days=58),  # +30
            d0 + timedelta(days=84),  # +26
        ]
        avg, confidence, basis = compute_average_cycle_length(dates)
        assert avg == pytest.approx(28.0)
        assert confidence == "medium"
        assert basis == "personal_average"

    def test_five_cycles_uses_simple_mean(self) -> None:
        # 5 cycles → 4 gaps → simple mean (NOT weighted)
        d0 = date(2026, 1, 1)
        # gaps: 28, 30, 26, 32 → mean = 116/4 = 29.0
        dates = [
            d0,
            d0 + timedelta(days=28),
            d0 + timedelta(days=58),  # +30
            d0 + timedelta(days=84),  # +26
            d0 + timedelta(days=116),  # +32
        ]
        avg, confidence, basis = compute_average_cycle_length(dates)
        assert avg == pytest.approx(29.0)
        assert confidence == "medium"
        assert basis == "personal_average"

    def test_six_cycles_uses_weighted_rolling_average(self) -> None:
        # 6 cycles → 5 gaps; weighted over last 3 gaps
        # gaps: 28, 30, 26, 32, 24
        # weighted: 24*0.5 + 32*0.3 + 26*0.2 = 12 + 9.6 + 5.2 = 26.8
        d0 = date(2026, 1, 1)
        dates = [
            d0,
            d0 + timedelta(days=28),
            d0 + timedelta(days=58),  # +30
            d0 + timedelta(days=84),  # +26
            d0 + timedelta(days=116),  # +32
            d0 + timedelta(days=140),  # +24
        ]
        avg, confidence, basis = compute_average_cycle_length(dates)
        expected = 24 * 0.5 + 32 * 0.3 + 26 * 0.2
        assert avg == pytest.approx(expected)
        assert confidence == "medium"  # orchestrator upgrades to 'high' if std_dev <= 2
        assert basis == "personal_average"

    def test_population_default_constant_is_28(self) -> None:
        assert POPULATION_DEFAULT_CYCLE_LENGTH == 28.0

    def test_weights_constant(self) -> None:
        assert WEIGHTS == [0.5, 0.3, 0.2]
        assert sum(WEIGHTS) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_weighted_average
# ---------------------------------------------------------------------------


class TestComputeWeightedAverage:
    def test_uniform_gaps_returns_same_value(self) -> None:
        # All gaps = 28 → weighted avg = 28.0
        gaps = [28.0, 28.0, 28.0, 28.0, 28.0]
        assert compute_weighted_average(gaps) == pytest.approx(28.0)

    def test_known_values(self) -> None:
        # gaps: [28, 30, 26, 32, 24]
        # last 3: [26, 32, 24]
        # 24*0.5 + 32*0.3 + 26*0.2 = 12 + 9.6 + 5.2 = 26.8
        gaps = [28.0, 30.0, 26.0, 32.0, 24.0]
        assert compute_weighted_average(gaps) == pytest.approx(26.8)

    def test_three_exact_gaps(self) -> None:
        # gaps[-1]=30, gaps[-2]=28, gaps[-3]=26
        # 30*0.5 + 28*0.3 + 26*0.2 = 15 + 8.4 + 5.2 = 28.6
        gaps = [26.0, 28.0, 30.0]
        assert compute_weighted_average(gaps) == pytest.approx(28.6)

    def test_weights_applied_to_most_recent_first(self) -> None:
        # Verify weight ordering: most recent (last) gets 0.5
        gaps = [10.0, 20.0, 30.0]  # last=30 should dominate
        result = compute_weighted_average(gaps)
        # 30*0.5 + 20*0.3 + 10*0.2 = 15 + 6 + 2 = 23.0
        assert result == pytest.approx(23.0)


# ---------------------------------------------------------------------------
# compute_standard_deviation
# ---------------------------------------------------------------------------


class TestComputeStandardDeviation:
    def test_empty_list_returns_zero(self) -> None:
        assert compute_standard_deviation([]) == 0.0

    def test_single_element_returns_zero(self) -> None:
        assert compute_standard_deviation([28.0]) == 0.0

    def test_uniform_gaps_zero_std(self) -> None:
        assert compute_standard_deviation([28.0, 28.0, 28.0]) == pytest.approx(0.0)

    def test_known_std_dev(self) -> None:
        # gaps = [26, 28, 30] -> mean = 28, deviations = [-2, 0, 2]
        # variance = (4 + 0 + 4) / 3 = 8/3, std_dev ~= 1.6330
        gaps = [26.0, 28.0, 30.0]
        expected = (8 / 3) ** 0.5
        assert compute_standard_deviation(gaps) == pytest.approx(expected)

    def test_high_variability(self) -> None:
        # gaps = [20, 28, 36] -> mean = 28, deviations = [-8, 0, 8]
        # variance = (64 + 0 + 64) / 3 = 128/3, std_dev ~= 6.532
        gaps = [20.0, 28.0, 36.0]
        expected = (128 / 3) ** 0.5
        assert compute_standard_deviation(gaps) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# compute_range_offset
# ---------------------------------------------------------------------------


class TestComputeRangeOffset:
    def test_zero_std_dev_returns_2(self) -> None:
        assert compute_range_offset(0.0) == 2

    def test_exactly_2_returns_2(self) -> None:
        assert compute_range_offset(2.0) == 2

    def test_exactly_4_returns_5(self) -> None:
        assert compute_range_offset(4.0) == 5

    def test_above_4_returns_5(self) -> None:
        assert compute_range_offset(10.0) == 5

    def test_midpoint_3_returns_round_of_3_5(self) -> None:
        # std_dev = 3.0 → 2.0 + (3.0 - 2.0) * 1.5 = 2.0 + 1.5 = 3.5 → round = 4
        assert compute_range_offset(3.0) == round(3.5)

    def test_std_dev_2_5(self) -> None:
        # 2.0 + (2.5 - 2.0) * 1.5 = 2.0 + 0.75 = 2.75 → round = 3
        assert compute_range_offset(2.5) == round(2.75)

    def test_std_dev_3_5(self) -> None:
        # 2.0 + (3.5 - 2.0) * 1.5 = 2.0 + 2.25 = 4.25 → round = 4
        assert compute_range_offset(3.5) == round(4.25)


# ---------------------------------------------------------------------------
# compute_predicted_range
# ---------------------------------------------------------------------------


class TestComputePredictedRange:
    def test_none_predicted_start_returns_none_range(self) -> None:
        earliest, latest = compute_predicted_range(None, [28.0, 28.0])
        assert earliest is None
        assert latest is None

    def test_fewer_than_2_gaps_returns_none_range(self) -> None:
        start = date(2026, 3, 1)
        # 0 gaps
        earliest, latest = compute_predicted_range(start, [])
        assert earliest is None
        assert latest is None
        # 1 gap
        earliest, latest = compute_predicted_range(start, [28.0])
        assert earliest is None
        assert latest is None

    def test_uniform_gaps_gives_offset_2(self) -> None:
        # std_dev = 0 → offset = 2
        start = date(2026, 3, 29)
        gaps = [28.0, 28.0, 28.0]
        earliest, latest = compute_predicted_range(start, gaps)
        assert earliest == start - timedelta(days=2)
        assert latest == start + timedelta(days=2)

    def test_high_variability_gives_offset_5(self) -> None:
        # gaps [20, 28, 36] → std_dev ≈ 6.53 >= 4.0 → offset = 5
        start = date(2026, 3, 29)
        gaps = [20.0, 28.0, 36.0]
        earliest, latest = compute_predicted_range(start, gaps)
        assert earliest == start - timedelta(days=5)
        assert latest == start + timedelta(days=5)


# ---------------------------------------------------------------------------
# compute_current_cycle_day
# ---------------------------------------------------------------------------


class TestComputeCurrentCycleDay:
    def test_none_start_returns_none(self) -> None:
        assert compute_current_cycle_day(None, date(2026, 6, 20)) is None

    def test_same_day_is_day_1(self) -> None:
        d = date(2026, 6, 1)
        assert compute_current_cycle_day(d, d) == 1

    def test_one_day_later_is_day_2(self) -> None:
        start = date(2026, 6, 1)
        today = date(2026, 6, 2)
        assert compute_current_cycle_day(start, today) == 2

    def test_14_days_later_is_day_15(self) -> None:
        start = date(2026, 6, 1)
        today = date(2026, 6, 15)
        assert compute_current_cycle_day(start, today) == 15

    def test_27_days_later_is_day_28(self) -> None:
        start = date(2026, 5, 1)
        today = start + timedelta(days=27)
        assert compute_current_cycle_day(start, today) == 28


# ---------------------------------------------------------------------------
# compute_predicted_next_start
# ---------------------------------------------------------------------------


class TestComputePredictedNextStart:
    def test_none_start_returns_none(self) -> None:
        assert compute_predicted_next_start(None, 28.0) is None

    def test_28_day_cycle(self) -> None:
        start = date(2026, 1, 1)
        result = compute_predicted_next_start(start, 28.0)
        assert result == date(2026, 1, 29)

    def test_29_day_cycle(self) -> None:
        start = date(2026, 1, 1)
        result = compute_predicted_next_start(start, 29.0)
        assert result == date(2026, 1, 30)

    def test_fractional_rounds_correctly(self) -> None:
        start = date(2026, 1, 1)
        result = compute_predicted_next_start(start, 28.5)
        assert result == start + timedelta(days=round(28.5))

    def test_population_default_28(self) -> None:
        start = date(2026, 6, 1)
        result = compute_predicted_next_start(start, POPULATION_DEFAULT_CYCLE_LENGTH)
        assert result == date(2026, 6, 29)


# ---------------------------------------------------------------------------
# get_prediction (orchestrator) — v1 scenarios
# ---------------------------------------------------------------------------


class TestGetPredictionV1:
    def test_zero_cycles(self) -> None:
        today = date(2026, 6, 20)
        result = get_prediction([], today)
        assert result["average_cycle_length"] == 28.0
        assert result["confidence"] == "low"
        assert result["basis"] == "default"
        assert result["current_cycle_day"] is None
        assert result["predicted_next_period_start"] is None
        assert result["predicted_range"] is None

    def test_one_cycle(self) -> None:
        start = date(2026, 5, 23)
        today = date(2026, 6, 20)
        result = get_prediction([start], today)
        assert result["average_cycle_length"] == 28.0
        assert result["confidence"] == "low"
        assert result["basis"] == "limited_data"
        assert result["current_cycle_day"] == (today - start).days + 1
        assert result["predicted_next_period_start"] == start + timedelta(days=28)
        assert result["predicted_range"] is None

    def test_two_cycles_30_day_gap(self) -> None:
        d0 = date(2026, 1, 1)
        d1 = date(2026, 1, 31)  # 30 day gap
        today = date(2026, 2, 10)
        result = get_prediction([d0, d1], today)
        assert result["average_cycle_length"] == 29.0
        assert result["confidence"] == "low"
        assert result["basis"] == "limited_data"
        assert result["current_cycle_day"] == (today - d1).days + 1
        assert result["predicted_next_period_start"] == d1 + timedelta(days=29)
        # 1 gap → no range
        assert result["predicted_range"] is None

    def test_three_cycles_personal_average(self) -> None:
        # gaps: 30, 28 → mean = 29.0
        d0 = date(2026, 1, 1)
        d1 = d0 + timedelta(days=30)
        d2 = d1 + timedelta(days=28)
        today = date(2026, 3, 15)
        result = get_prediction([d0, d1, d2], today)
        assert result["average_cycle_length"] == pytest.approx(29.0)
        assert result["confidence"] == "medium"
        assert result["basis"] == "personal_average"
        assert result["current_cycle_day"] == (today - d2).days + 1
        assert result["predicted_next_period_start"] == d2 + timedelta(days=round(29.0))
        # 2 gaps → range present
        assert result["predicted_range"] is not None

    def test_four_cycles_28_30_26_gap(self) -> None:
        d0 = date(2026, 1, 1)
        dates = [
            d0,
            d0 + timedelta(days=28),
            d0 + timedelta(days=58),
            d0 + timedelta(days=84),
        ]
        today = date(2026, 4, 1)
        result = get_prediction(dates, today)
        assert result["average_cycle_length"] == pytest.approx(28.0)
        assert result["confidence"] == "medium"
        assert result["basis"] == "personal_average"


# ---------------------------------------------------------------------------
# get_prediction (orchestrator) — v2 scenarios
# ---------------------------------------------------------------------------


class TestGetPredictionV2:
    def _make_uniform_dates(self, n: int, gap: int = 28) -> list[date]:
        """Generate n cycle start dates spaced `gap` days apart."""
        d0 = date(2026, 1, 1)
        return [d0 + timedelta(days=gap * i) for i in range(n)]

    # ── Weighted average ──────────────────────────────────────────────────

    def test_six_cycles_uses_weighted_average(self) -> None:
        # gaps: 28, 30, 26, 32, 24
        d0 = date(2026, 1, 1)
        dates = [
            d0,
            d0 + timedelta(days=28),
            d0 + timedelta(days=58),
            d0 + timedelta(days=84),
            d0 + timedelta(days=116),
            d0 + timedelta(days=140),
        ]
        today = date(2026, 6, 1)
        result = get_prediction(dates, today)
        expected_avg = 24 * 0.5 + 32 * 0.3 + 26 * 0.2
        assert result["average_cycle_length"] == pytest.approx(expected_avg)
        assert result["basis"] == "personal_average"

    def test_seven_cycles_weighted_average_ignores_old_gaps(self) -> None:
        # gaps: [28, 30, 26, 32, 24, 29]
        # last 3: [32, 24, 29]
        # 29*0.5 + 24*0.3 + 32*0.2 = 14.5 + 7.2 + 6.4 = 28.1
        d0 = date(2026, 1, 1)
        dates = [
            d0,
            d0 + timedelta(days=28),
            d0 + timedelta(days=58),
            d0 + timedelta(days=84),
            d0 + timedelta(days=116),
            d0 + timedelta(days=140),
            d0 + timedelta(days=169),
        ]
        today = date(2026, 8, 1)
        result = get_prediction(dates, today)
        expected_avg = 29 * 0.5 + 24 * 0.3 + 32 * 0.2
        assert result["average_cycle_length"] == pytest.approx(expected_avg)

    # ── Confidence levels ─────────────────────────────────────────────────

    def test_confidence_low_for_zero_cycles(self) -> None:
        result = get_prediction([], date(2026, 1, 1))
        assert result["confidence"] == "low"

    def test_confidence_low_for_one_cycle(self) -> None:
        result = get_prediction([date(2026, 1, 1)], date(2026, 1, 15))
        assert result["confidence"] == "low"

    def test_confidence_low_for_two_cycles(self) -> None:
        dates = [date(2026, 1, 1), date(2026, 1, 29)]
        result = get_prediction(dates, date(2026, 2, 10))
        assert result["confidence"] == "low"

    def test_confidence_medium_for_three_cycles(self) -> None:
        dates = self._make_uniform_dates(3)
        result = get_prediction(dates, date(2026, 3, 1))
        assert result["confidence"] == "medium"

    def test_confidence_medium_for_five_cycles(self) -> None:
        dates = self._make_uniform_dates(5)
        result = get_prediction(dates, date(2026, 5, 1))
        assert result["confidence"] == "medium"

    def test_confidence_high_for_six_cycles_low_std_dev(self) -> None:
        # Uniform 28-day gaps → std_dev = 0 ≤ 2.0 → 'high'
        dates = self._make_uniform_dates(6)
        result = get_prediction(dates, date(2026, 7, 1))
        assert result["confidence"] == "high"

    def test_confidence_medium_for_six_cycles_high_std_dev(self) -> None:
        # Alternating 20/36 day gaps → std_dev > 2.0 → stays 'medium'
        d0 = date(2026, 1, 1)
        dates = [
            d0,
            d0 + timedelta(days=20),
            d0 + timedelta(days=56),
            d0 + timedelta(days=76),
            d0 + timedelta(days=112),
            d0 + timedelta(days=132),
        ]
        result = get_prediction(dates, date(2026, 6, 1))
        assert result["confidence"] == "medium"

    # ── Predicted range ───────────────────────────────────────────────────

    def test_predicted_range_none_for_zero_cycles(self) -> None:
        result = get_prediction([], date(2026, 1, 1))
        assert result["predicted_range"] is None

    def test_predicted_range_none_for_one_cycle(self) -> None:
        result = get_prediction([date(2026, 1, 1)], date(2026, 1, 15))
        assert result["predicted_range"] is None

    def test_predicted_range_none_for_two_cycles(self) -> None:
        dates = [date(2026, 1, 1), date(2026, 1, 29)]
        result = get_prediction(dates, date(2026, 2, 10))
        assert result["predicted_range"] is None

    def test_predicted_range_present_for_three_cycles(self) -> None:
        dates = self._make_uniform_dates(3)
        result = get_prediction(dates, date(2026, 3, 1))
        assert result["predicted_range"] is not None
        pr = result["predicted_range"]
        assert pr["earliest"] is not None
        assert pr["latest"] is not None
        assert pr["earliest"] <= result["predicted_next_period_start"]
        assert pr["latest"] >= result["predicted_next_period_start"]

    def test_predicted_range_offset_2_for_uniform_gaps(self) -> None:
        # Uniform gaps → std_dev = 0 → offset = 2
        dates = self._make_uniform_dates(4, gap=28)
        result = get_prediction(dates, date(2026, 4, 1))
        predicted = result["predicted_next_period_start"]
        pr = result["predicted_range"]
        assert pr["earliest"] == predicted - timedelta(days=2)
        assert pr["latest"] == predicted + timedelta(days=2)

    def test_predicted_range_offset_5_for_high_variability(self) -> None:
        # High-variability gaps → std_dev > 4 → offset = 5
        d0 = date(2026, 1, 1)
        dates = [
            d0,
            d0 + timedelta(days=20),
            d0 + timedelta(days=56),  # gap=36
            d0 + timedelta(days=76),  # gap=20
        ]
        result = get_prediction(dates, date(2026, 3, 1))
        predicted = result["predicted_next_period_start"]
        pr = result["predicted_range"]
        assert pr["earliest"] == predicted - timedelta(days=5)
        assert pr["latest"] == predicted + timedelta(days=5)


# ---------------------------------------------------------------------------
# compute_ovulation_and_fertile_window
# ---------------------------------------------------------------------------


class TestComputeOvulationAndFertileWindow:
    def test_none_predicted_start_returns_all_none(self) -> None:
        from app.services.prediction_service import (
            compute_ovulation_and_fertile_window,
        )

        ov, fw_start, fw_end = compute_ovulation_and_fertile_window(None)
        assert ov is None
        assert fw_start is None
        assert fw_end is None

    def test_known_date_returns_correct_ovulation(self) -> None:
        from app.services.prediction_service import (
            compute_ovulation_and_fertile_window,
        )

        # predicted_next_period_start = 2026-03-29
        # ovulation = 2026-03-29 - 14 = 2026-03-15
        predicted = date(2026, 3, 29)
        ov, _fw_start, _fw_end = compute_ovulation_and_fertile_window(predicted)
        assert ov == date(2026, 3, 15)

    def test_fertile_window_start_is_5_days_before_ovulation(self) -> None:
        from app.services.prediction_service import (
            compute_ovulation_and_fertile_window,
        )

        predicted = date(2026, 3, 29)
        _ov, fw_start, _fw_end = compute_ovulation_and_fertile_window(predicted)
        # fertile_window_start = ovulation - 5 = 2026-03-15 - 5 = 2026-03-10
        assert fw_start == date(2026, 3, 10)

    def test_fertile_window_end_is_1_day_after_ovulation(self) -> None:
        from app.services.prediction_service import (
            compute_ovulation_and_fertile_window,
        )

        predicted = date(2026, 3, 29)
        _ov, _fw_start, fw_end = compute_ovulation_and_fertile_window(predicted)
        # fertile_window_end = ovulation + 1 = 2026-03-15 + 1 = 2026-03-16
        assert fw_end == date(2026, 3, 16)

    def test_all_three_fields_consistent(self) -> None:
        from app.services.prediction_service import (
            compute_ovulation_and_fertile_window,
        )

        predicted = date(2026, 6, 1)
        ov, fw_start, fw_end = compute_ovulation_and_fertile_window(predicted)
        assert ov == predicted - timedelta(days=14)
        assert fw_start == ov - timedelta(days=5)
        assert fw_end == ov + timedelta(days=1)

    def test_past_dates_returned_without_suppression(self) -> None:
        """Dates in the past must NOT be filtered out or set to None."""
        from app.services.prediction_service import (
            compute_ovulation_and_fertile_window,
        )

        # Use a predicted start well in the past
        predicted = date(2020, 1, 15)
        ov, fw_start, fw_end = compute_ovulation_and_fertile_window(predicted)
        assert ov == date(2020, 1, 1)
        assert fw_start == date(2019, 12, 27)
        assert fw_end == date(2020, 1, 2)

    def test_year_boundary_calculation(self) -> None:
        from app.services.prediction_service import (
            compute_ovulation_and_fertile_window,
        )

        predicted = date(2026, 1, 10)
        ov, fw_start, fw_end = compute_ovulation_and_fertile_window(predicted)
        # ovulation = 2025-12-27
        assert ov == date(2025, 12, 27)
        # fertile_window_start = 2025-12-22
        assert fw_start == date(2025, 12, 22)
        # fertile_window_end = 2025-12-28
        assert fw_end == date(2025, 12, 28)


# ---------------------------------------------------------------------------
# get_prediction (orchestrator) — v3 ovulation scenarios
# ---------------------------------------------------------------------------


class TestGetPredictionV3:
    def test_zero_cycles_all_ovulation_fields_none(self) -> None:
        result = get_prediction([], date(2026, 6, 20))
        assert result["predicted_ovulation_date"] is None
        assert result["fertile_window_start"] is None
        assert result["fertile_window_end"] is None

    def test_one_cycle_ovulation_computed(self) -> None:
        start = date(2026, 5, 23)
        today = date(2026, 6, 20)
        result = get_prediction([start], today)
        # predicted_next_period_start = 2026-05-23 + 28 = 2026-06-20
        predicted = result["predicted_next_period_start"]
        assert predicted is not None
        assert result["predicted_ovulation_date"] == predicted - timedelta(days=14)
        assert result["fertile_window_start"] == (
            result["predicted_ovulation_date"] - timedelta(days=5)
        )
        assert result["fertile_window_end"] == (
            result["predicted_ovulation_date"] + timedelta(days=1)
        )

    def test_three_cycles_ovulation_computed_correctly(self) -> None:
        d0 = date(2026, 1, 1)
        d1 = d0 + timedelta(days=30)
        d2 = d1 + timedelta(days=28)
        # avg = 29.0, predicted = d2 + 29 days = 2026-03-29
        today = date(2026, 3, 15)
        result = get_prediction([d0, d1, d2], today)
        predicted = result["predicted_next_period_start"]
        assert predicted == date(2026, 3, 29)
        assert result["predicted_ovulation_date"] == date(2026, 3, 15)
        assert result["fertile_window_start"] == date(2026, 3, 10)
        assert result["fertile_window_end"] == date(2026, 3, 16)

    def test_ovulation_field_relationships_hold_for_any_cycle_count(self) -> None:
        """
        For any scenario that produces a predicted_next_period_start,
        the derived fields must satisfy:
          ovulation = predicted - 14
          fw_start  = ovulation - 5
          fw_end    = ovulation + 1
        """
        d0 = date(2026, 1, 1)
        dates = [d0 + timedelta(days=28 * i) for i in range(4)]
        today = date(2026, 5, 1)
        result = get_prediction(dates, today)
        predicted = result["predicted_next_period_start"]
        ov = result["predicted_ovulation_date"]
        fw_start = result["fertile_window_start"]
        fw_end = result["fertile_window_end"]
        assert ov == predicted - timedelta(days=14)
        assert fw_start == ov - timedelta(days=5)
        assert fw_end == ov + timedelta(days=1)

    def test_past_ovulation_not_suppressed(self) -> None:
        """
        If the cycle has progressed past the predicted ovulation date,
        the engine must still return the computed (past) date — not None.
        """
        # Single cycle started 2026-01-01; predicted next = 2026-01-29
        # ovulation = 2026-01-15 (already in the past relative to today)
        start = date(2026, 1, 1)
        today = date(2026, 2, 10)  # well past ovulation
        result = get_prediction([start], today)
        predicted = result["predicted_next_period_start"]
        assert result["predicted_ovulation_date"] == predicted - timedelta(days=14)
        assert result["predicted_ovulation_date"] is not None
