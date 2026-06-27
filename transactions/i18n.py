"""
RemindMe — i18n (internationalisation) module
Supports: ge (Georgian), en (English), ru (Russian)
"""

import json
import os
from flask import session, request, g

SUPPORTED_LANGS = ["ge", "en", "ru"]
DEFAULT_LANG = "ge"

_translations: dict[str, dict] = {}


def _load_translations(app):
    """Load all JSON translation files from static/lang/ or project root."""
    base_dirs = [
        os.path.join(app.root_path, "static", "lang"),
        os.path.join(app.root_path, "lang"),
        app.root_path,
    ]
    for lang in SUPPORTED_LANGS:
        for d in base_dirs:
            path = os.path.join(d, f"{lang}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    _translations[lang] = json.load(f)
                break
        else:
            _translations[lang] = {}


def get_lang() -> str:
    """Return the active language code for this request."""
    # 1. session
    lang = session.get("lang")
    if lang in SUPPORTED_LANGS:
        return lang
    # 2. Accept-Language header (first match)
    al = request.headers.get("Accept-Language", "")
    for part in al.replace("-", "_").split(","):
        code = part.strip().split(";")[0][:2].lower()
        if code in SUPPORTED_LANGS:
            return code
    return DEFAULT_LANG


def t(key: str, **kwargs) -> str:
    """
    Translate *key* in the current language.
    Falls back: current lang → ge → key itself.

    Supports {n} placeholders:  t("days_in", n=3)
    """
    lang = get_lang()
    data = _translations.get(lang, {})
    value = data.get(key)

    # fallback chain: ge → raw key
    if value is None:
        value = _translations.get("ge", {}).get(key, key)

    if kwargs:
        try:
            value = value.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return value


def _make_t_for_template():
    """Return a t() that is safe to call from Jinja2 templates."""
    # Capture lang once per request so all template calls are consistent.
    lang = get_lang()
    data = _translations.get(lang, {})
    fallback = _translations.get("ge", {})

    def _t(key: str, **kwargs) -> str:
        value = data.get(key) or fallback.get(key) or key
        if kwargs:
            try:
                value = value.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return value

    return _t


def _context_processor():
    lang = get_lang()
    lang_names = {code: _translations.get(code, {}).get("lang_name", code.upper())
                  for code in SUPPORTED_LANGS}
    return {
        "t": _make_t_for_template(),
        "current_lang": lang,
        "supported_langs": SUPPORTED_LANGS,
        "lang_names": lang_names,
    }


def init_app(app):
    _load_translations(app)
    app.context_processor(_context_processor)
