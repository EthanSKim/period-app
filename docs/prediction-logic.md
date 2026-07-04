# Prediction Logic Documentation

This document explains the math, weights, and decision rules behind the **Period App prediction engine** (`app/services/prediction_service.py`).

---

## Overview

Given a user's list of cycle start dates (sorted oldest → newest), the engine computes:

| Output field | Description |
|---|---|
| `predicted_next_period_start` | Best estimate of when the next period begins |
| `average_cycle_length` | Effective cycle length used for prediction |
| `current_cycle_day` | Day number within the current (ongoing) cycle |
| `confidence` | `low` / `medium` / `high` |
| `basis` | Explains what data source drove the prediction |
| `predicted_range` | `{ earliest, latest }` — a ± window around the predicted date |

---

## Step 1 — Compute Gaps

All calculations are based on **inter-period gaps**: the number of days between consecutive cycle start dates.

```
gap[i] = start_date[i+1] − start_date[i]   (in days)
```

For N cycles, there are **N − 1** gaps.

---

## Step 2 — Average Cycle Length

The method used depends on how many cycles have been recorded:

### 0 cycles
No personal data available. Use the **population default**:

```
average_cycle_length = 28.0
confidence = "low"
basis = "default"
```

### 1 cycle
Only one start date — no gap can be computed. Fall back to the population default:

```
average_cycle_length = 28.0
confidence = "low"
basis = "limited_data"
```

### 2 cycles (1 gap)
One gap exists but is too sparse for a reliable personal average. **Blend** the single gap with the population default:

```
average_cycle_length = (gap[0] + 28.0) / 2
confidence = "low"
basis = "limited_data"
```

### 3–5 cycles (2–4 gaps)
Enough data for a personal average, but not enough for the weighted rolling algorithm. Use a **simple arithmetic mean** of all gaps:

```
average_cycle_length = mean(gaps)
confidence = "medium"
basis = "personal_average"
```

### 6+ cycles (5+ gaps) — Weighted Rolling Average
With 6 or more cycles, the engine switches to a **weighted rolling average** of the **3 most recent gaps**. Recent cycles are weighted more heavily because they better reflect the user's current pattern.

#### Weights

```python
WEIGHTS = [0.5, 0.3, 0.2]
```

| Weight | Gap |
|--------|-----|
| 0.5 | Most recent gap (`gaps[-1]`) |
| 0.3 | Second most recent (`gaps[-2]`) |
| 0.2 | Third most recent (`gaps[-3]`) |

#### Formula

```
average_cycle_length = gaps[-1] × 0.5
                     + gaps[-2] × 0.3
                     + gaps[-3] × 0.2
```

The weights sum to 1.0, so the result is always a weighted average in the same units (days).

```
confidence = "medium" (upgraded to "high" if std_dev ≤ 2.0 — see below)
basis = "personal_average"
```

---

## Step 3 — Predicted Next Period Start

```
predicted_next_period_start = most_recent_start + round(average_cycle_length) days
```

> Python's built-in `round()` uses **banker's rounding** (round-half-to-even), so 28.5 → 28 and 29.5 → 30.

---

## Step 4 — Standard Deviation & Confidence Interval

### Standard Deviation

For users with **3+ cycles** (2+ gaps), the engine computes the **population standard deviation** of all gaps:

```
σ = sqrt( Σ(gap[i] − μ)² / N )
```

where μ = mean of all gaps and N = number of gaps.

A low σ means cycles are highly regular; a high σ means they are variable.

### Range Offset

The σ is mapped to a ± offset (in days) using a piecewise linear function:

| σ (std dev) | Offset |
|---|---|
| σ ≤ 2.0 | 2 days |
| σ ≥ 4.0 | 5 days |
| 2.0 < σ < 4.0 | `round(2.0 + (σ − 2.0) × 1.5)` days |

The intermediate formula linearly interpolates between 2 and 5 over the range [2.0, 4.0].

### Predicted Range

```
earliest = predicted_next_period_start − offset
latest   = predicted_next_period_start + offset
```

The range is `None` when:
- fewer than 3 cycles have been recorded (< 2 gaps), or
- `predicted_next_period_start` is `None`.

---

## Step 5 — Confidence Level

| Condition | `confidence` |
|---|---|
| 0 or 1 cycle | `"low"` |
| 2 cycles (blended) | `"low"` |
| 3–5 cycles | `"medium"` |
| 6+ cycles **and** σ > 2.0 | `"medium"` |
| 6+ cycles **and** σ ≤ 2.0 | `"high"` |

The upgrade from `"medium"` → `"high"` reflects both sufficient personal history (6+ cycles) and demonstrated regularity (tight standard deviation).

---

## Current Cycle Day

```
current_cycle_day = (today − most_recent_start).days + 1
```

Day 1 is the start date itself. Returns `None` if no cycles have been recorded.

---

## Example Walkthrough

**Scenario**: User has recorded 6 cycles with start dates producing gaps of `[28, 30, 26, 32, 24]` days.

1. **Gap computation**: `[28, 30, 26, 32, 24]`
2. **Average (weighted)**: `24×0.5 + 32×0.3 + 26×0.2 = 12.0 + 9.6 + 5.2 = 26.8 days`
3. **Predicted start**: `most_recent_start + round(26.8) = most_recent_start + 27 days`
4. **σ** of all 5 gaps ≈ `2.97` → offset = `round(2.0 + (2.97 − 2.0) × 1.5)` = `round(3.455)` = `3`
5. **Range**: `[predicted − 3, predicted + 3]`
6. **Confidence**: σ = 2.97 > 2.0 → `"medium"` (not `"high"`)

---

## Constants

| Constant | Value | Meaning |
|---|---|---|
| `POPULATION_DEFAULT_CYCLE_LENGTH` | `28.0` | Average human menstrual cycle |
| `WEIGHTS` | `[0.5, 0.3, 0.2]` | Recency weights for 6+ cycle rolling average |
