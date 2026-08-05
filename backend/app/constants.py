"""
Application-level constants.

Notification type identifiers
──────────────────────────────
These string values are stored in NotificationLog.notification_type and are
the canonical names used by the scheduler, duplicate-prevention logic, and
any future analytics queries.

Adding a new notification type:
  1. Add a NOTIF_* constant here.
  2. Use it in scheduler.py — never hardcode the string inline.
  3. Add the corresponding unit test in tests/test_push.py.
"""

# ── Notification Types ────────────────────────────────────────────────────────

# Period reminders
NOTIF_PERIOD_1_DAY = "period_1_day"
NOTIF_PERIOD_3_DAYS = "period_3_days"

# Fertile window reminder
NOTIF_FERTILE_1_DAY = "fertile_1_day"

# Luteal phase heads-up (8 days before predicted period start)
NOTIF_LUTEAL_PHASE_HEADS_UP = "luteal_phase_heads_up"
