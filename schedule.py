from datetime import datetime, timedelta, date
from models import db, Reminder, SportsEvent, HolidayEvent


def send_email_reminder(reminder):
    """Send an email - Gmail App Password will be enabled after adding it."""
    try:
        from flask_mail import Mail, Message
        from flask import current_app
        mail = Mail(current_app)
        msg = Message(
            subject=f"🔔 remind: {reminder.title}",
            recipients=[reminder.user.email],
            html=f"""
            <div style="font-family:Arial;padding:20px;background:#0f0f1a;color:#f1f0f5;border-radius:10px;">
                <h2 style="color:#a855f7;">🔔 {reminder.title}</h2>
                <p>{reminder.description or ''}</p>
                <p style="color:#8b8ba7;">დრო: {reminder.remind_time.strftime('%d %b %Y, %H:%M')}</p>
            </div>
            """
        )
        mail.send(msg)
        print(f"Send an email: {reminder.user.email}")
    except Exception as e:
        print(f"Email error: {e}")


def handle_repeat(reminder):
    """Next date for recurring reminder"""
    if reminder.repeat == 'daily':
        reminder.remind_time += timedelta(days=1)
        reminder.sent = False
    elif reminder.repeat == 'weekly':
        reminder.remind_time += timedelta(weeks=1)
        reminder.sent = False
    elif reminder.repeat == 'monthly':
        reminder.remind_time += timedelta(days=30)
        reminder.sent = False
    else:
        reminder.sent = True


def check_reminders():
    now = datetime.now()
    reminders = Reminder.query.filter(
        Reminder.remind_time <= now,
        Reminder.sent == False
    ).all()

    for reminder in reminders:
        print(f"[RemindMe] 🔔 {reminder.title} - {reminder.description}")
        send_email_reminder(reminder)
        handle_repeat(reminder)

    db.session.commit()


def send_sports_reminder_email(event):
    """Send an email 20 minutes before the start of a sports competition"""
    try:
        from flask_mail import Mail, Message
        from flask import current_app
        mail = Mail(current_app)
        msg = Message(
            subject=f"🏟️ starting in 20 minutes: {event.title}",
            recipients=[event.user.email],
            html=f"""
            <div style="font-family:Arial;padding:20px;background:#0f0f1a;color:#f1f0f5;border-radius:10px;">
                <h2 style="color:#a855f7;">🏟️ {event.title}</h2>
                <p>starting time: {event.event_time.strftime('%d %b %Y, %H:%M')}</p>
                <p>{event.note or ''}</p>
            </div>
            """
        )
        mail.send(msg)
        print(f"Send an email: {event.user.email}")
    except Exception as e:
        print(f"Email error: {e}")


def send_holiday_reminder_email(holiday):
    """Send an email 20 minutes before the start of a sports competition"""
    try:
        from flask_mail import Mail, Message
        from flask import current_app
        mail = Mail(current_app)
        msg = Message(
            subject=f"🎉 starting in 20 minutes: {holiday.title}",
            recipients=[holiday.user.email],
            html=f"""
            <div style="font-family:Arial;padding:20px;background:#0f0f1a;color:#f1f0f5;border-radius:10px;">
                <h2 style="color:#a855f7;">🎉 {holiday.title}</h2>
                <p>{holiday.note or ''}</p>
            </div>
            """
        )
        mail.send(msg)
        print(f"Send an email: {holiday.user.email}")
    except Exception as e:
        print(f"Email error: {e}")


def check_sports_reminders():
    """Checks sports competitions and sends a message 20 minutes before"""
    now = datetime.now()
    window_end = now + timedelta(minutes=20)
    events = SportsEvent.query.filter(
        SportsEvent.remind_before == True,
        SportsEvent.reminded == False,
        SportsEvent.event_time > now,
        SportsEvent.event_time <= window_end
    ).all()

    for event in events:
        print(f"[RemindMe] 🥊 starting in 20 minutes: {event.title}")
        send_sports_reminder_email(event)
        event.reminded = True

    db.session.commit()


def check_holiday_reminders():
    """Checks holidays/dates and sends a notification 20 minutes in advance"""
    now = datetime.now()
    today = date.today()

    holidays = HolidayEvent.query.filter(
        HolidayEvent.remind_before == True,
        HolidayEvent.event_time.isnot(None)
    ).all()

    for h in holidays:
        next_date = h.event_date.replace(year=today.year) if h.repeat_yearly else h.event_date
        if next_date != today:
            continue
        if h.last_reminded_year == today.year:
            continue

        event_dt = datetime.combine(next_date, h.event_time)
        if now < event_dt <= now + timedelta(minutes=20):
            print(f"[RemindMe] 🎉 starting in 20 minutes: {h.title}")
            send_holiday_reminder_email(h)
            h.last_reminded_year = today.year

    db.session.commit()


def check_all_reminders():
    """Check all types of reminders - this feature is enabled by APScheduler"""
    check_reminders()
    check_sports_reminders()
    check_holiday_reminders()
 
