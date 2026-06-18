"""Integration with Django's Jinja2 template backend.

The primary integration is to call :func:`jinja_components.setup` from your own
environment function, so your other globals (``static``, ``url``, ``csrf_input``)
stay in place::

    from jinja2 import Environment
    from jinja_components import setup

    def environment(**options):
        env = Environment(**options)
        env.globals.update(static=..., url=...)
        return setup(env, package="myapp.components", root=BASE_DIR / "myapp" / "components")

For components-only projects, :func:`environment` below is a ready-made callable
that reads its configuration from the ``JINJA_COMPONENTS`` setting.
"""

from typing import Any

from django.conf import settings
from jinja2 import Environment

from jinja_components.extension import setup


def environment(**options: Any) -> Environment:
    """Environment factory for Django's ``Jinja2`` backend ``environment`` option.

    Configure it through the ``JINJA_COMPONENTS`` setting::

        TEMPLATES = [{
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {"environment": "jinja_components.django.environment"},
        }]
        JINJA_COMPONENTS = {
            "package": "myapp.components",
            "root": BASE_DIR / "myapp" / "components",
        }
    """
    # Django's Jinja2 backend always passes autoescape through **options.
    return _configure(Environment(**options))  # noqa: S701


def _configure(env: Environment) -> Environment:
    config = getattr(settings, "JINJA_COMPONENTS", {})
    root = config.get("root")
    return setup(
        env,
        package=config.get("package", ""),
        root=str(root) if root is not None else None,
    )
