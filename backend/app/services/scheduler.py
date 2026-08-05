import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.constants import (
    NOTIF_FERTILE_1_DAY,
    NOTIF_LUTEAL_PHASE_HEADS_UP,
    NOTIF_PERIOD_1_DAY,
    NOTIF_PERIOD_3_DAYS,
)
from app.database import SessionLocal
from app.models import Cycle, NotificationLog, PushSubscription, User
from app.services.prediction_service import get_prediction
from app.services.push_service import send_web_push

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# ── Notification payload definitions ─────────────────────────────────────────
# Each tuple: (type_constant, days_ahead, title, body, deep_link_url)
# "days_ahead" is compared against (reference_date - today).days.
# The reference_date fed into duplicate-prevention is the prediction date that
# triggered the notification (pred_start for period alerts; fertile_start for
# fertile-window; pred_start again for luteal phase).

_PERIOD_NOTIFICATIONS = [
    (
        NOTIF_PERIOD_1_DAY,
        1,
        "Period starting tomorrow",
        "Your period is expected to start tomorrow.",
        "/calendar",
    ),
    (
        NOTIF_PERIOD_3_DAYS,
        3,
        "Period starting in 3 days",
        "Your period is expected to start in 3 days.",
        "/calendar",
    ),
    (
        NOTIF_LUTEAL_PHASE_HEADS_UP,
        8,
        "Your body may need extra care this week",
        (
            "Your period is likely about a week away. The luteal phase can bring "
            "mood shifts, fatigue, bloating, and cramps. It\u2019s a good time to slow "
            "down, rest well, and be kind to yourself."
        ),
        "/calendar",
    ),
]

_FERTILE_NOTIFICATIONS = [
    (
        NOTIF_FERTILE_1_DAY,
        1,
        "Fertile window starts tomorrow",
        "Your fertile window is expected to start tomorrow.",
        "/calendar",
    ),
]


def run_daily_notifications_job():
    """
    Scheduled job that runs once daily (at 9 AM UTC).
    Evaluates prediction metrics for all subscribed users and sends pushes.

    Notification triggers evaluated each run:
      - period_1_day          : predicted period starts tomorrow
      - period_3_days         : predicted period starts in 3 days
      - luteal_phase_heads_up : predicted period starts in 8 days
      - fertile_1_day         : fertile window starts tomorrow
    """
    logger.info("Starting daily notifications job...")
    db = SessionLocal()
    try:
        # Find all users with active push subscriptions and at least 1 cycle
        users = db.query(User).join(PushSubscription).join(Cycle).distinct().all()

        users_evaluated = len(users)
        period_sent = 0
        fertile_sent = 0
        luteal_sent = 0
        subscriptions_cleaned_up = 0

        today = date.today()

        for user in users:
            cycles = (
                db.query(Cycle)
                .filter(Cycle.user_id == user.id)
                .order_by(Cycle.start_date.asc())
                .all()
            )
            start_dates = [c.start_date for c in cycles]
            pred = get_prediction(start_dates, today)

            pred_start = pred.get("predicted_next_period_start")
            fertile_start = pred.get("fertile_window_start")

            notifications_to_send = []

            # ── Period-anchored notifications (1 day, 3 days, 8 days) ────────
            if pred_start:
                days_until_period = (pred_start - today).days
                for notif_type, days_ahead, title, body, url in _PERIOD_NOTIFICATIONS:
                    if days_until_period == days_ahead:
                        notifications_to_send.append(
                            (notif_type, pred_start, title, body, url)
                        )

            # ── Fertile-window notifications (1 day) ─────────────────────────
            if fertile_start:
                days_until_fertile = (fertile_start - today).days
                for notif_type, days_ahead, title, body, url in _FERTILE_NOTIFICATIONS:
                    if days_until_fertile == days_ahead:
                        notifications_to_send.append(
                            (notif_type, fertile_start, title, body, url)
                        )

            # ── Send + log ───────────────────────────────────────────────────
            for notif_type, ref_date, title, body, url in notifications_to_send:
                # Duplicate-send prevention
                existing_log = (
                    db.query(NotificationLog)
                    .filter(
                        NotificationLog.user_id == user.id,
                        NotificationLog.notification_type == notif_type,
                        NotificationLog.cycle_reference_date == ref_date,
                    )
                    .first()
                )
                if existing_log:
                    continue

                subscriptions = (
                    db.query(PushSubscription)
                    .filter(PushSubscription.user_id == user.id)
                    .all()
                )
                if not subscriptions:
                    continue

                send_success_any = False
                for sub in subscriptions:
                    success = send_web_push(
                        db,
                        sub,
                        {
                            "title": title,
                            "body": body,
                            "icon": "/icon-192.png",
                            "url": url,
                        },
                    )
                    if success:
                        send_success_any = True
                    else:
                        db.commit()
                        exists = (
                            db.query(PushSubscription)
                            .filter(PushSubscription.id == sub.id)
                            .first()
                        )
                        if not exists:
                            subscriptions_cleaned_up += 1

                if send_success_any:
                    log_entry = NotificationLog(
                        user_id=user.id,
                        notification_type=notif_type,
                        cycle_reference_date=ref_date,
                    )
                    db.add(log_entry)
                    db.commit()

                    if notif_type == NOTIF_LUTEAL_PHASE_HEADS_UP:
                        luteal_sent += 1
                    elif notif_type == NOTIF_FERTILE_1_DAY:
                        fertile_sent += 1
                    else:
                        period_sent += 1

        logger.info(
            "Daily notifications job completed. "
            f"Evaluated: {users_evaluated}, "
            f"Period: {period_sent}, "
            f"Fertile: {fertile_sent}, "
            f"Luteal: {luteal_sent}, "
            f"Cleaned up: {subscriptions_cleaned_up}"
        )
    except Exception as ex:
        logger.error(f"Error running daily notifications job: {ex}")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """
    Start the background scheduler in the FastAPI process.
    Runs every day at 9:00 AM UTC.
    """
    if not scheduler.running:
        scheduler.add_job(
            run_daily_notifications_job,
            CronTrigger(hour=9, minute=0, timezone="UTC"),
            id="daily_notifications",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Background job scheduler started (9 AM UTC daily).")


def shutdown_scheduler():
    """
    Gracefully shut down the scheduler.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background job scheduler shut down.")
