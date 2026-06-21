"""A small, class-based component system for Jinja2 with HTML-tag syntax and native-style slots."""

from jinja_components.extension import ComponentsExtension, setup
from jinja_components.registry import Component, clear_registry, get_component, register

__all__ = [
    "Component",
    "ComponentsExtension",
    "clear_registry",
    "get_component",
    "register",
    "setup",
]
__version__ = "0.1.0a1"
