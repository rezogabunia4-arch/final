from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    theme = db.Column(db.String(20), default='light')

    # Gamification
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    coins = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    last_completed_date = db.Column(db.Date, nullable=True)

    reminders = db.relationship("Reminder", backref="user", lazy=True, cascade="all, delete-orphan")
    badges = db.relationship("Badge", backref="user", lazy=True, cascade="all, delete-orphan")
    calendar_events = db.relationship("CalendarEvent", backref="user", lazy=True, cascade="all, delete-orphan")
    sports_events = db.relationship("SportsEvent", backref="user", lazy=True, cascade="all, delete-orphan")
    holidays = db.relationship("HolidayEvent", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    remind_time = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent = db.Column(db.Boolean, default=False)
    completed = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50), default='პირადი')
    repeat = db.Column(db.String(20), default='none')
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), default='🏅')
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    event_type = db.Column(db.String(30), default='other')
    note = db.Column(db.String(300), nullable=True)
    repeat_yearly = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class SportsEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    sport_type = db.Column(db.String(30), default='other')
    event_time = db.Column(db.DateTime, nullable=False)
    note = db.Column(db.String(300), nullable=True)
    remind_before = db.Column(db.Boolean, default=False)
    reminded = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class HolidayEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.Time, nullable=True)
    note = db.Column(db.String(300), nullable=True)
    repeat_yearly = db.Column(db.Boolean, default=True)
    remind_before = db.Column(db.Boolean, default=False)
    last_reminded_year = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
