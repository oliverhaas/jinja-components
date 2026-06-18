"""Jinja2 extension and environment setup for jinja-components."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, pass_context
from jinja2.ext import Extension

from jinja_components.registry import get_component
from jinja_components.tags import compile_component_tags

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from jinja2.runtime import Context


class ComponentsExtension(Extension):
    """Rewrite component tags at compile time and install the ``component()`` global."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        # jinja2 leaves Environment.globals' value type narrowed to its default
        # namespace, so cast the alias to assign arbitrary globals.
        globals_ = cast("MutableMapping[str, Any]", environment.globals)
        globals_.setdefault("component", _render_component)

    def preprocess(self, source: str, name: str | None, filename: str | None = None) -> str:  # noqa: ARG002
        return compile_component_tags(source)


@pass_context
def _render_component(context: Context, name: str, /, **kwargs: Any) -> str:
    component_cls = get_component(name)
    return component_cls.render(
        context.environment,
        _jc_request=context.get("request"),
        **kwargs,
    )


def setup(
    environment: Environment,
    *,
    package: str = "",
    root: str | os.PathLike[str] | None = None,
) -> Environment:
    """Enable jinja-components on ``environment`` and return it.

    Adds :class:`ComponentsExtension`, records the components ``package`` used for
    template resolution, and, when ``root`` is given, adds a filesystem loader for
    the co-located component templates while keeping any existing loader ahead of
    it. Safe to call more than once on the same environment: the extension, the
    package, and the components loader are each applied at most once (a later bare
    call does not wipe a package set earlier, and loaders are not re-stacked).
    """
    globals_ = cast("MutableMapping[str, Any]", environment.globals)
    if ComponentsExtension.identifier not in environment.extensions:
        environment.add_extension(ComponentsExtension)
    if package or "_jinja_components_package" not in globals_:
        globals_["_jinja_components_package"] = package
    if root is not None and not globals_.get("_jinja_components_loaded_root"):
        globals_["_jinja_components_loaded_root"] = True
        components_loader = FileSystemLoader(os.fspath(root))
        environment.loader = (
            ChoiceLoader([environment.loader, components_loader])
            if environment.loader is not None
            else components_loader
        )
    return environment
