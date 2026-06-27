from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for
from datetime import datetime, date, timedelta
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash
from models import db, User, Reminder, Badge, CalendarEvent, HolidayEvent, SportsEvent
from schedule import check_all_reminders
from gamification import complete_reminder, xp_for_next_level
from sports import SPORT_LEAGUES
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR
from dotenv import load_dotenv
import os
import atexit

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///reminders.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "")

db.init_app(app)

from transactions.i18n import init_app as init_i18n, SUPPORTED_LANGS, get_lang, t as _t
init_i18n(app)


def _is_password_hashed(value):
    return value and value.startswith(("pbkdf2:", "scrypt:", "argon2:"))


def migrate_db():
    """Updating the old database schema (password → password_hash)"""
    insp = inspect(db.engine)
    if "user" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("user")}
    if "password_hash" not in cols and "password" in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE user RENAME COLUMN password TO password_hash"))

        for user in User.query.all():
            if user.password_hash and not _is_password_hashed(user.password_hash):
                user.password_hash = generate_password_hash(user.password_hash)
        db.session.commit()


with app.app_context():
    db.create_all()
    migrate_db()


def run_reminders():
    with app.app_context():
        try:
            check_all_reminders()
        except Exception as e:
            print(f"[Scheduler] error: {e}")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=run_reminders, trigger="interval", seconds=60)
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))




def get_upcoming_events(user_id, days=30):
    """Upcoming calendar / holiday / sports events in 30 days"""
    today = date.today()
    now = datetime.now()

    
    cal_events = CalendarEvent.query.filter_by(user_id=user_id).all()
    upcoming_cal = []
    for e in cal_events:
        if e.repeat_yearly:
            nd = e.event_date.replace(year=today.year)
            if nd < today:
                nd = e.event_date.replace(year=today.year + 1)
        else:
            nd = e.event_date
        dl = (nd - today).days
        if 0 <= dl <= days:
            upcoming_cal.append({"event": e, "next_date": nd, "days_left": dl})
    upcoming_cal.sort(key=lambda x: x["days_left"])

   
    holidays = HolidayEvent.query.filter_by(user_id=user_id).all()
    upcoming_hol = []
    for h in holidays:
        if h.repeat_yearly:
            nd = h.event_date.replace(year=today.year)
            if nd < today:
                nd = h.event_date.replace(year=today.year + 1)
        else:
            nd = h.event_date
        dl = (nd - today).days
        if 0 <= dl <= days:
            upcoming_hol.append({"holiday": h, "next_date": nd, "days_left": dl})
    upcoming_hol.sort(key=lambda x: x["days_left"])

  
    upcoming_sports = (
        SportsEvent.query
        .filter(SportsEvent.user_id == user_id, SportsEvent.event_time >= now)
        .order_by(SportsEvent.event_time)
        .all()
    )

    return upcoming_cal, upcoming_hol, upcoming_sports


def get_upcoming_summary(user_id, limit=5):
    """Shortlist for the main page sidebar"""
    cal, hol, sports = get_upcoming_events(user_id, days=30)
    items = []
    for x in cal:
        items.append({
            "title": x["event"].title,
            "date": x["next_date"],
            "kind": _t("kind_calendar"),
            "url": "/calendar",
            "days_left": x["days_left"],
        })
    for x in hol:
        items.append({
            "title": x["holiday"].title,
            "date": x["next_date"],
            "kind": _t("kind_holiday"),
            "url": "/holidays",
            "days_left": x["days_left"],
        })
    for ev in sports[:10]:
        items.append({
            "title": ev.title,
            "date": ev.event_time.date(),
            "kind": _t("kind_sports"),
            "url": "/sports",
            "days_left": (ev.event_time.date() - date.today()).days,
        })
    items.sort(key=lambda x: (x["days_left"], x["date"]))
    return items[:limit]




@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/reminders")
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if not username or not email or not password:
            return render_template("register.html", error=_t("err_all_required"))
        if len(password) < 6:
            return render_template("register.html", error=_t("err_password_short"))
        if User.query.filter_by(email=email).first():
            return render_template("register.html", error=_t("err_email_taken"))
        if User.query.filter_by(username=username).first():
            return render_template("register.html", error=_t("err_username_taken"))
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect("/login")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session.permanent = True
            return redirect("/reminders")
        return render_template("login.html", error=_t("login_error"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/lang/<lang>")
def set_lang(lang):
    if lang in SUPPORTED_LANGS:
        session["lang"] = lang
        session.permanent = True
        session.modified = True
    # redirect back but strip the host to avoid open-redirect
    ref = request.referrer or "/"
    from urllib.parse import urlparse
    path = urlparse(ref).path or "/"
    return redirect(path)


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")
    user = db.session.get(User, session["user_id"])
    if not user:
        session.clear()
        return redirect("/login")

    total = Reminder.query.filter_by(user_id=user.id).count()
    pending = Reminder.query.filter_by(user_id=user.id, completed=False).count()
    completed = Reminder.query.filter_by(user_id=user.id, completed=True).count()
    badges = Badge.query.filter_by(user_id=user.id).order_by(Badge.earned_at.desc()).all()
    next_level_xp = xp_for_next_level(user.level)
    progress_pct = int((user.xp / next_level_xp) * 100) if next_level_xp else 0

    cal_count = CalendarEvent.query.filter_by(user_id=user.id).count()
    holiday_count = HolidayEvent.query.filter_by(user_id=user.id).count()
    sports_count = (
        SportsEvent.query
        .filter(SportsEvent.user_id == user.id, SportsEvent.event_time >= datetime.now())
        .count()
    )

    return render_template(
        "profile.html", user=user,
        total_reminders=total, pending_reminders=pending, completed_reminders=completed,
        badges=badges, next_level_xp=next_level_xp, progress_pct=progress_pct,
        cal_count=cal_count, holiday_count=holiday_count, sports_count=sports_count,
        active_page="profile", user_theme=user.theme,
    )


@app.route("/theme", methods=["POST"])
def set_theme():
    if "user_id" not in session:
        return jsonify({"ok": False})
    data = request.get_json()
    theme = data.get("theme", "light")
    if theme not in ("light", "dark"):
        theme = "light"
    user = db.session.get(User, session["user_id"])
    if user:
        user.theme = theme
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/ai-suggest", methods=["POST"])
def ai_suggest():
    data = request.get_json()
    title = data.get("title", "").lower()
    suggestions = {
        "Assignment": {"time": "17:00", "label": "School assignment?"},
        "Doctor":    {"time": "10:00", "label": "Doctor visit?"},
        "Sport":  {"time": "08:00", "label": "Morning exercise?"},
        "Meeting":{"time": "14:00", "label": "Business meeting?"},
        "Study":  {"time": "16:00", "label": "Study session?"},
        "Cinema":    {"time": "20:00", "label": "Evening entertainment?"},
    }
    for keyword, suggestion in suggestions.items():
        if keyword in title:
            return jsonify(suggestion)
    return jsonify({"time": None, "label": None})


@app.route("/weather-tip")
def weather_tip():
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key:
        return jsonify({"tip": None})
    import urllib.request, json as jsonlib
    try:
        city = "Tbilisi"
        url = (f"https://api.openweathermap.org/data/2.5/forecast"
               f"?q={city}&appid={api_key}&units=metric&lang=ka")
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = jsonlib.loads(resp.read())
        tomorrow = data["list"][8]
        weather_main = tomorrow["weather"][0]["main"]
        temp = round(tomorrow["main"]["temp"])
        tips = {
            "Rain":        "🌧️It's going to rain tomorrow - don't forget your umbrella.!",
            "Snow":        "❄️ It's snowing tomorrow - dress warmly.!",
            "Clear":       f"☀️ Tomorrow is sunny, {temp}°C — a good day for a walk!",
            "Clouds":      f"☁️ It will be cloudy tomorrow., {temp}°C",
            "Thunderstorm":"⛈️ There will be thunderstorms tomorrow, stay home.!",
        }
        return jsonify({"tip": tips.get(weather_main, f"🌤️ tomorrow {temp}°C")})
    except Exception:
        return jsonify({"tip": None})


@app.route("/reminders", methods=["GET", "POST"])
def reminders():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect("/login")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        time_str = request.form.get("time", "")
        category = request.form.get("category", "Personal")
        repeat = request.form.get("repeat", "none")
        if not title or not time_str:
            flash("Title and time are required.", "error")
        else:
            try:
                remind_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M")
                reminder = Reminder(
                    title=title, description=description,
                    remind_time=remind_time, user_id=user_id,
                    category=category, repeat=repeat
                )
                db.session.add(reminder)
                db.session.commit()
                flash("Reminder added", "success")
            except ValueError:
                flash("The time is in the wrong format.", "error")
        return redirect(url_for("reminders"))

    filter_cat = request.args.get("category", "All")
    status = request.args.get("status", "active")

    query = Reminder.query.filter_by(user_id=user_id)
    if filter_cat and filter_cat != "All":
        query = query.filter_by(category=filter_cat)
    if status == "active":
        query = query.filter_by(completed=False)
    elif status == "done":
        query = query.filter_by(completed=True)

    reminders_list = query.order_by(
        Reminder.completed.asc(),
        Reminder.remind_time.asc()
    ).all()

    now = datetime.now()
    pending_count = Reminder.query.filter_by(user_id=user_id, completed=False).count()
    overdue_count = Reminder.query.filter(
        Reminder.user_id == user_id,
        Reminder.completed == False,
        Reminder.remind_time < now
    ).count()
    upcoming_summary = get_upcoming_summary(user_id)

    return render_template(
        "reminders.html",
        reminders=reminders_list,
        user=user,
        filter_cat=filter_cat,
        status=status,
        pending_count=pending_count,
        overdue_count=overdue_count,
        upcoming_summary=upcoming_summary,
        now=now,
        active_page="reminders",
        user_theme=user.theme,
    )


@app.route("/complete/<int:id>")
def complete_reminder_route(id):
    if "user_id" not in session:
        return redirect("/login")
    reminder = db.session.get(Reminder, id)
    if reminder and reminder.user_id == session["user_id"] and not reminder.completed:
        reminder.completed = True
        user = db.session.get(User, session["user_id"])
        total_completed = Reminder.query.filter_by(user_id=user.id, completed=True).count()
        complete_reminder(user, reminder, total_completed)
        flash(_t("rem_flash_complete"), "success")
    return redirect(url_for("reminders"))


@app.route("/delete/<int:id>")
def delete_reminder(id):
    if "user_id" not in session:
        return redirect("/login")
    reminder = db.session.get(Reminder, id)
    if reminder and reminder.user_id == session["user_id"]:
        db.session.delete(reminder)
        db.session.commit()
        flash(_t("rem_flash_delete"), "success")
    return redirect(url_for("reminders"))


@app.route("/calendar", methods=["GET", "POST"])
def calendar():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        event_date_str = request.form.get("event_date", "")
        event_type = request.form.get("event_type", "other")
        note = request.form.get("note", "").strip()
        repeat_yearly = request.form.get("repeat_yearly") == "on"
        if title and event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                event = CalendarEvent(
                    title=title, event_date=event_date, event_type=event_type,
                    note=note, repeat_yearly=repeat_yearly, user_id=user_id
                )
                db.session.add(event)
                db.session.commit()
                flash(_t("cal_flash_added"), "success")
            except ValueError:
                flash(_t("cal_flash_bad_date"), "error")
        return redirect(url_for("calendar"))

    events = CalendarEvent.query.filter_by(user_id=user_id).all()
    today = date.today()
    upcoming = []
    for e in events:
        if e.repeat_yearly:
            nd = e.event_date.replace(year=today.year)
            if nd < today:
                nd = e.event_date.replace(year=today.year + 1)
        else:
            nd = e.event_date
        days_left = (nd - today).days
        upcoming.append({"event": e, "next_date": nd, "days_left": days_left})
    upcoming.sort(key=lambda x: x["days_left"])
    return render_template("calendar.html", upcoming=upcoming, active_page="calendar", user_theme="light")


@app.route("/calendar/delete/<int:id>")
def delete_calendar_event(id):
    if "user_id" not in session:
        return redirect("/login")
    event = db.session.get(CalendarEvent, id)
    if event and event.user_id == session["user_id"]:
        db.session.delete(event)
        db.session.commit()
    return redirect("/calendar")


@app.route("/holidays", methods=["GET", "POST"])
def holidays():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        event_date_str = request.form.get("event_date", "")
        time_str = request.form.get("event_time", "").strip()
        note = request.form.get("note", "").strip()
        repeat_yearly = request.form.get("repeat_yearly") == "on"
        remind_before = request.form.get("remind_before") == "on"
        if title and event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                event_time = datetime.strptime(time_str, "%H:%M").time() if time_str else None
                holiday = HolidayEvent(
                    title=title, event_date=event_date, event_time=event_time,
                    note=note, repeat_yearly=repeat_yearly,
                    remind_before=(remind_before if event_time else False),
                    user_id=user_id
                )
                db.session.add(holiday)
                db.session.commit()
                flash(_t("hol_flash_added"), "success")
            except ValueError:
                flash(_t("hol_flash_bad_dt"), "error")
        return redirect(url_for("holidays"))

    all_holidays = HolidayEvent.query.filter_by(user_id=user_id).all()
    today = date.today()
    upcoming = []
    for h in all_holidays:
        if h.repeat_yearly:
            nd = h.event_date.replace(year=today.year)
            if nd < today:
                nd = h.event_date.replace(year=today.year + 1)
        else:
            nd = h.event_date
        days_left = (nd - today).days
        upcoming.append({"holiday": h, "next_date": nd, "days_left": days_left})
    upcoming.sort(key=lambda x: x["days_left"])
    return render_template("holidays.html", upcoming=upcoming, active_page="holidays", user_theme="light")


@app.route("/holidays/delete/<int:id>")
def delete_holiday(id):
    if "user_id" not in session:
        return redirect("/login")
    holiday = db.session.get(HolidayEvent, id)
    if holiday and holiday.user_id == session["user_id"]:
        db.session.delete(holiday)
        db.session.commit()
    return redirect("/holidays")


@app.route("/sports")
def sports():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect("/login")
    
    sports_events = SportsEvent.query.filter_by(user_id=user_id).order_by(SportsEvent.event_time).all()
    return render_template("sports.html", active_page="sports", user_theme=user.theme, sports_events=sports_events)


@app.route("/sports/remind", methods=["POST"])
def sports_remind():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    title = request.form.get("title", "").strip()
    event_date = request.form.get("event_date", "")
    event_time = request.form.get("event_time", "")
    sport_type = request.form.get("sport_type", "other")

    if title and event_date:
        try:
            time_part = event_time if event_time else "12:00"
            event_dt = datetime.strptime(f"{event_date} {time_part}", "%Y-%m-%d %H:%M")
            ev = SportsEvent(
                title=title, sport_type=sport_type,
                event_time=event_dt, remind_before=True, user_id=user_id
            )
            db.session.add(ev)
            db.session.commit()
            flash(_t("sports_flash_added"), "success")
        except Exception as e:
            print(f"Sports remind error: {e}")
            flash(_t("sports_flash_fail"), "error")

    return redirect(url_for("sports"))


@app.route("/sports/delete/<int:id>")
def delete_sports_event(id):
    if "user_id" not in session:
        return redirect("/login")
    ev = db.session.get(SportsEvent, id)
    if ev and ev.user_id == session["user_id"]:
        db.session.delete(ev)
        db.session.commit()
        flash(_t("rem_flash_delete"), "success")
    return redirect(url_for("sports"))


if __name__ == "__main__":
    app.run(debug=True, port=8000)
