from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = "test-secret-key"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "components"],
        "APP_DIRS": False,
        "OPTIONS": {
            "environment": "jinja_components.django.environment",
        },
    },
]

# jinja-components configuration consumed by jinja_components.django.environment.
JINJA_COMPONENTS = {"package": ""}

USE_TZ = True
