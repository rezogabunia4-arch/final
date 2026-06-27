from datetime import date, timedelta
from models import db, Badge

def xp_for_next_level(level):
    return level * 100


def add_xp(user, amount):
    """Add XP and recalculate level"""
    user.xp += amount
    user.coins += amount // 2

    leveled_up = False
    while user.xp >= xp_for_next_level(user.level):
        user.xp -= xp_for_next_level(user.level)
        user.level += 1
        leveled_up = True

    return leveled_up


def update_streak(user):
    """Today's finishing streak update"""
    today = date.today()

    if user.last_completed_date == today:
        return  

    if user.last_completed_date == today - timedelta(days=1):
        user.streak += 1
    else:
        user.streak = 1

    user.last_completed_date = today


BADGE_DEFINITIONS = {
    "first_task": {"name": "first step", "icon": "🎯", "check": lambda u, total: total >= 1},
    "ten_tasks": {"name": "10 Assignments", "icon": "⭐", "check": lambda u, total: total >= 10},
    "fifty_tasks": {"name": "50 Assignments", "icon": "🌟", "check": lambda u, total: total >= 50},
    "hundred_tasks": {"name": "100 Assignments", "icon": "🏆", "check": lambda u, total: total >= 100},
    "streak_7": {"name": "7-Day series", "icon": "🔥", "check": lambda u, total: u.streak >= 7},
    "streak_30": {"name": "30-Day series", "icon": "💎", "check": lambda u, total: u.streak >= 30},
    "level_5": {"name": "Level 5", "icon": "🚀", "check": lambda u, total: u.level >= 5},
    "level_10": {"name": "Level 10", "icon": "👑", "check": lambda u, total: u.level >= 10},
}


def check_new_badges(user, total_completed):
    """Checking and returning new badges"""
    existing_codes = {b.code for b in user.badges}
    new_badges = []

    for code, info in BADGE_DEFINITIONS.items():
        if code not in existing_codes and info["check"](user, total_completed):
            badge = Badge(code=code, name=info["name"], icon=info["icon"], user_id=user.id)
            db.session.add(badge)
            new_badges.append(badge)

    return new_badges


def complete_reminder(user, reminder, total_completed):
    """Summoned upon completion of a task — XP, streak, badges"""
    leveled_up = add_xp(user, 15)
    update_streak(user)
    new_badges = check_new_badges(user, total_completed)
    db.session.commit()
    return {"leveled_up": leveled_up, "new_badges": new_badges}
