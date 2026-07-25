import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.models import Cycle, NotificationLog, PushSubscription, User
from app.services.prediction_service import get_prediction
from app.services.push_service import send_web_push

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def run_daily_notifications_job():
    """
    Scheduled job that runs once daily (at 9 AM UTC).
    Evaluates prediction metrics for all subscribed users and sends pushes.
    """
    logger.info("Starting daily notifications job...")
    db = SessionLocal()
    try:
        # Find all users with active push subscriptions and at least 1 cycle
        users = db.query(User).join(PushSubscription).join(Cycle).distinct().all()

        users_evaluated = len(users)
        notifications_sent = 0
        subscriptions_cleaned_up = 0

        today = date.today()

        for user in users:
            # Get user's predictions
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

            # Check 1: Period starting tomorrow (1 day away) or in 3 days
            if pred_start:
                days_until_period = (pred_start - today).days
                if days_until_period == 1:
                    notifications_to_send.append(
                        (
                            "period_1_day",
                            pred_start,
                            "Period starting tomorrow",
                            "Your period is expected to start tomorrow.",
                            "/calendar",
                        )
                    )
                elif days_until_period == 3:
                    notifications_to_send.append(
                        (
                            "period_3_days",
                            pred_start,
                            "Period starting in 3 days",
                            "Your period is expected to start in 3 days.",
                            "/calendar",
                        )
                    )

            # Check 2: Fertile window starts tomorrow (1 day away)
            if fertile_start:
                days_until_fertile = (fertile_start - today).days
                if days_until_fertile == 1:
                    notifications_to_send.append(
                        (
                            "fertile_1_day",
                            fertile_start,
                            "Fertile window starts tomorrow",
                            "Your fertile window is expected to start tomorrow.",
                            "/calendar",
                        )
                    )

            for notif_type, ref_date, title, body, url in notifications_to_send:
                # Check for duplicate prevention
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

                # Fetch all push subscriptions for this user
                subscriptions = (
                    db.query(PushSubscription)
                    .filter(PushSubscription.user_id == user.id)
                    .all()
                )

                if not subscriptions:
                    continue

                # Send to all subscriptions of the user
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
                        # Verify if subscription got deleted (404/410 Gone)
                        db.commit()
                        exists = (
                            db.query(PushSubscription)
                            .filter(PushSubscription.id == sub.id)
                            .first()
                        )
                        if not exists:
                            subscriptions_cleaned_up += 1

                if send_success_any:
                    # Log that we sent the notification successfully
                    log_entry = NotificationLog(
                        user_id=user.id,
                        notification_type=notif_type,
                        cycle_reference_date=ref_date,
                    )
                    db.add(log_entry)
                    db.commit()
                    notifications_sent += 1

        logger.info(
            f"Daily notifications job completed. "
            f"Evaluated: {users_evaluated}, Sent: {notifications_sent}, "
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
