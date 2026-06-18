"""Component base class and the component registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from markupsafe import Markup

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from jinja2 import Environment

DEFAULT_TEMPLATE_NAME = "template.jinja"


class Component:
    """Base class for components.

    Subclasses auto-register under their class name, so ``class Button`` is
    reachable from a template as ``<Button/>``. Override
    :meth:`get_context_data` to turn the component's props into its template
    context.
    """

    template_name: ClassVar[str] = DEFAULT_TEMPLATE_NAME

    def __init_subclass__(cls, *, abstract: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not abstract:
            register(cls.__name__)(cls)

    def __init__(self, request: Any = None) -> None:
        self.request = request

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Map the component's props (keyword arguments) to a template context."""
        return kwargs

    @classmethod
    def get_template_name(cls, package: str = "") -> str:
        """Return the loader key for this component's co-located template.

        An explicit ``template_name`` is used verbatim. Otherwise, when
        ``package`` is configured and this class lives under it, a nested
        ``folder/template.jinja`` key is derived from the module path (so
        ``myapp.components.sidebar.sidebar`` resolves to
        ``sidebar/template.jinja``). With no configured package, the class's own
        package folder name is used.
        """
        if cls.template_name != DEFAULT_TEMPLATE_NAME:
            return cls.template_name
        module = cls.__module__
        prefix = f"{package}." if package else ""
        if prefix and module.startswith(prefix):
            folder = module[len(prefix) :].rsplit(".", 1)[0].replace(".", "/")
            return f"{folder}/{cls.template_name}"
        parent = module.rpartition(".")[0]
        if parent:
            folder = parent.rpartition(".")[2]
            return f"{folder}/{cls.template_name}"
        return cls.template_name

    @classmethod
    def render(cls, environment: Environment, /, **kwargs: Any) -> str:
        """Instantiate, build context, and render this component's template.

        The compiler passes the slot machinery under reserved ``_jc_*`` keys so
        they can never collide with a component's own props. ``request``,
        ``content`` (the default slot) and ``slots`` (named slots) are then
        reserved variables in the component template; the remaining keyword
        arguments are the component's props and reach :meth:`get_context_data`.
        """
        request = kwargs.pop("_jc_request", None)
        content = kwargs.pop("_jc_content", None)
        slots: Mapping[str, Any] | None = kwargs.pop("_jc_slots", None)
        component = cls(request=request)
        context = component.get_context_data(**kwargs)
        globals_ = cast("Mapping[str, Any]", environment.globals)
        package = globals_.get("_jinja_components_package", "")
        template = environment.get_template(cls.get_template_name(package))
        render_context = {
            **context,
            "request": request,
            "content": content,
            "slots": dict(slots or {}),
        }
        rendered = template.render(render_context)
        autoescape = environment.autoescape
        if callable(autoescape):
            autoescape = autoescape(template.name)
        # Only mark the output safe when the component template autoescaped its
        # own interpolations. Otherwise return a plain str so the caller's
        # autoescaping still applies, instead of laundering unescaped output.
        return Markup(rendered) if autoescape else rendered  # noqa: S704


_registry: dict[str, type[Component]] = {}


def register(name: str) -> Callable[[type[Component]], type[Component]]:
    """Register a component class under ``name`` (usable as a decorator)."""

    def decorator(component_cls: type[Component]) -> type[Component]:
        _registry[name] = component_cls
        return component_cls

    return decorator


def get_component(name: str) -> type[Component]:
    """Return the component class registered under ``name``."""
    try:
        return _registry[name]
    except KeyError:
        raise LookupError(f'Component "{name}" is not registered') from None


def clear_registry() -> None:
    """Remove every registered component (mainly for tests)."""
    _registry.clear()
