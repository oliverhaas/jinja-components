"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from jinja2 import DictLoader, Environment

from jinja_components import clear_registry, setup

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Each test starts and ends with an empty component registry."""
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def env_factory() -> Callable[[Mapping[str, str]], Environment]:
    """Build a components-enabled Environment over a DictLoader of templates."""

    def make(templates: Mapping[str, str] | None = None) -> Environment:
        env = Environment(loader=DictLoader(dict(templates or {})), autoescape=True)
        setup(env)
        return env

    return make
