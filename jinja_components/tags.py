"""Compile component HTML-tags and Vue-style slots into plain Jinja2 source.

This runs in the Jinja2 ``preprocess`` step, once per template compile, so the
rewritten source is what Jinja2 parses and bytecode-caches. Three things are
rewritten:

* ``<PascalCase .../>`` and ``<PascalCase>...</PascalCase>`` into
  ``{{ component("Name", ...) }}`` calls.
* ``<template #name>...</template>`` children of a component into named slots.
* ``<slot name="x">fallback</slot>`` (and bare ``<slot>``) in a component
  template into a lookup against the ``slots`` mapping (or ``content``).
"""

from __future__ import annotations

import keyword
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_PASCAL = r"[A-Z][A-Za-z0-9]*"

# Jinja2 constructs are matched first so their contents are never parsed as tags.
_TOKEN = re.compile(
    r"(?P<jinja>\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\})"
    rf"|</(?P<close>{_PASCAL})\s*>"
    rf"|<(?P<open>{_PASCAL})(?P<attrs>(?:\"[^\"]*\"|'[^']*'|\{{\{{.*?\}}\}}|[^>])*)>",
    re.DOTALL,
)

_ATTR = re.compile(
    r"\s*(?P<colon>:?)(?P<name>[A-Za-z_][\w-]*)"
    r"(?:\s*=\s*(?P<value>\"[^\"]*\"|'[^']*'|\{\{.*?\}\}|[^\s>]+))?",
    re.DOTALL,
)

_MUSTACHE = re.compile(r"^\{\{(?P<expr>.*)\}\}$", re.DOTALL)

_TEMPLATE_FILL = re.compile(
    r"<template\s+#(?P<name>[A-Za-z_][\w-]*)\s*>(?P<body>.*?)</template\s*>",
    re.DOTALL,
)

_SLOT = re.compile(
    r"<slot\b(?P<attrs>[^>]*?)\s*(?:/>|>(?P<body>.*?)</slot\s*>)",
    re.DOTALL,
)

_SLOT_NAME = re.compile(r"""name\s*=\s*["'](?P<name>[A-Za-z_][\w-]*)["']""")


def compile_component_tags(source: str) -> str:
    """Rewrite component tags and slots in ``source`` into plain Jinja2."""
    rewritten = _rewrite_components(source)
    return _SLOT.sub(_rewrite_slot, rewritten)


def _string_literal(text: str) -> str:
    """Emit ``text`` as a double-quoted Jinja string literal, escaping safely."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _attribute_kwarg(match: re.Match[str]) -> str:
    name = match.group("name")
    if not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError(f'Component attribute "{name}" is not a usable keyword argument name')

    value = match.group("value")
    if value is None:
        return f"{name}=True"

    if value[0] in "\"'":
        inner = value[1:-1]
        mustache = _MUSTACHE.match(inner.strip())
        if match.group("colon") or mustache:
            expr = mustache.group("expr") if mustache else inner
            return f"{name}=({expr.strip()})"
        return f"{name}={_string_literal(inner)}"

    mustache = _MUSTACHE.match(value.strip())
    if mustache:
        return f"{name}=({mustache.group('expr').strip()})"
    if match.group("colon"):
        return f"{name}=({value})"
    return f"{name}={value}"


def _build_slots(children: str, fresh: Callable[[], int]) -> tuple[str, str]:
    """Split a component's children into a default slot and named slots.

    Returns the ``component(...)`` call suffix (``, content=..., slots={...}``)
    and the ``{% set %}`` prelude that captures each slot's content.
    """
    fills: dict[str, str] = {}

    def take(match: re.Match[str]) -> str:
        fills[match.group("name")] = match.group("body")
        return ""

    default = _TEMPLATE_FILL.sub(take, children)
    prelude: list[str] = []
    suffix = ""
    if default.strip():
        var = f"_jc_content_{fresh()}"
        prelude.append(f"{{% set {var} %}}{default}{{% endset %}}")
        suffix += f", _jc_content={var}"
    if fills:
        pairs = []
        for slot_name, body in fills.items():
            var = f"_jc_slot_{fresh()}"
            prelude.append(f"{{% set {var} %}}{body}{{% endset %}}")
            pairs.append(f'"{slot_name}": {var}')
        suffix += ", _jc_slots={" + ", ".join(pairs) + "}"
    return suffix, "".join(prelude)


def _rewrite_components(source: str) -> str:
    counter = 0

    def fresh() -> int:
        nonlocal counter
        counter += 1
        return counter

    root: list[str] = []
    stack: list[tuple[str, str, list[str], str]] = []
    buffer = root
    position = 0

    while True:
        match = _TOKEN.search(source, position)
        if match is None:
            buffer.append(source[position:])
            break

        buffer.append(source[position : match.start()])
        position = match.end()

        if match.group("jinja") is not None:
            buffer.append(match.group("jinja"))
            continue

        if match.group("open") is not None:
            name = match.group("open")
            attrs = match.group("attrs")
            self_closing = attrs.rstrip().endswith("/")
            if self_closing:
                attrs = attrs.rstrip()[:-1]
            suffix = "".join(f", {_attribute_kwarg(m)}" for m in _ATTR.finditer(attrs))
            if self_closing:
                buffer.append(f'{{{{ component("{name}"{suffix}) }}}}')
            else:
                stack.append((name, suffix, buffer, match.group(0)))
                buffer = []
            continue

        # Closing tag: pair it with the most recent open tag and emit the call.
        if not stack:
            buffer.append(match.group(0))
            continue
        name, suffix, parent, _raw = stack.pop()
        slot_suffix, prelude = _build_slots("".join(buffer), fresh)
        parent.append(f'{prelude}{{{{ component("{name}"{suffix}{slot_suffix}) }}}}')
        buffer = parent

    # Unclosed component tags: emit them verbatim so their content is preserved
    # rather than silently dropped.
    while stack:
        _name, _suffix, parent, raw = stack.pop()
        parent.append(raw + "".join(buffer))
        buffer = parent

    return "".join(root)


def _rewrite_slot(match: re.Match[str]) -> str:
    attrs = match.group("attrs") or ""
    body = match.group("body")
    fallback = body if body is not None else ""
    name_match = _SLOT_NAME.search(attrs)
    if name_match:
        name = name_match.group("name")
        if fallback.strip():
            return f'{{% if "{name}" in slots %}}{{{{ slots["{name}"] }}}}{{% else %}}{fallback}{{% endif %}}'
        return f'{{{{ slots.get("{name}", "") }}}}'
    if fallback.strip():
        return f"{{% if content is not none %}}{{{{ content }}}}{{% else %}}{fallback}{{% endif %}}"
    return '{{ content if content is not none else "" }}'
