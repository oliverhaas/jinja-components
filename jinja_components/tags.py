"""Compile component HTML-tags and slots into plain Jinja2 source.

This runs in the Jinja2 ``preprocess`` step, once per template compile, so the
rewritten source is what Jinja2 parses and bytecode-caches. Three things are
rewritten:

* ``<PascalCase .../>`` and ``<PascalCase>...</PascalCase>`` into
  ``{{ component("Name", ...) }}`` calls.
* ``slot="name"`` on a component's children (or ``<template slot="name">``) into
  named slots, mirroring native Web Components slot assignment.
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

# A single, whole mustache: nothing between the braces may itself contain
# ``}}`` so two adjacent mustaches in one value never collapse into one match.
_MUSTACHE = re.compile(r"^\{\{(?P<expr>(?:(?!\}\}).)*)\}\}$", re.DOTALL)

# HTML void elements have no closing tag, so a fill built on one is the start
# tag alone.
_VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"},
)

# One token within a component's children: a Jinja construct, an HTML close tag,
# or an HTML open/void/self-closing tag. Nesting is tracked in Python; the regex
# only ever matches a single tag at a time.
_CHILD_TOKEN = re.compile(
    r"(?P<jinja>\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\})"
    r"|</(?P<close>[A-Za-z][\w-]*)\s*>"
    r"|<(?P<open>[A-Za-z][\w-]*)(?P<attrs>(?:\"[^\"]*\"|'[^']*'|\{\{.*?\}\}|[^>])*)>",
    re.DOTALL,
)

# A literal ``slot="name"`` attribute (not ``:slot``); marks a named slot fill.
_SLOT_ATTR = re.compile(r"(?:^|\s)slot\s*=\s*(?P<q>[\"'])(?P<name>.*?)(?P=q)")

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

    quoted = value[0] in "\"'"
    inner = value[1:-1] if quoted else value

    # A whole-value mustache is the expression; this also rejects the two-mustache
    # case (no single match), which then falls through to a literal below.
    mustache = _MUSTACHE.match(inner.strip())
    if mustache:
        return f"{name}=({mustache.group('expr').strip()})"

    if match.group("colon"):
        expr = inner.strip()
        if "{{" in expr or "}}" in expr:
            raise ValueError(
                f'Component attribute ":{name}" is a bound expression and must not contain "{{{{ }}}}"',
            )
        return f"{name}=({expr})"

    # Quoted values are string literals; unquoted values pass through as raw Jinja.
    return f"{name}={_string_literal(inner) if quoted else value}"


def _read_slot(attrs: str) -> str | None:
    """Return the literal ``slot="..."`` name in ``attrs``, or ``None``."""
    match = _SLOT_ATTR.search(attrs)
    return match.group("name") if match else None


def _remove_slot(attrs: str) -> str:
    """Drop the ``slot="..."`` attribute from an element's attribute string."""
    return _SLOT_ATTR.sub("", attrs, count=1)


def _wrap_slot(call: str, slot_name: str | None) -> str:
    """Wrap a component call so it fills ``slot_name`` of its parent, if named."""
    if slot_name is None:
        return call
    return f'<template slot="{slot_name}">{call}</template>'


def _match_element(children: str, name: str, start: int) -> tuple[int, int]:
    """Find where the element ``name``, opened just before ``start``, closes.

    Returns ``(extent_end, inner_end)``: ``children[start:inner_end]`` is the
    element's inner HTML and ``children[:extent_end]`` ends just past its close
    tag. An unclosed element runs to the end of ``children``.
    """
    depth = 1
    pos = start
    while True:
        match = _CHILD_TOKEN.search(children, pos)
        if match is None:
            return len(children), len(children)
        pos = match.end()
        if match.group("jinja") is not None:
            continue
        if match.group("close") is not None:
            if match.group("close").lower() == name.lower():
                depth -= 1
                if depth == 0:
                    return match.end(), match.start()
            continue
        opened = match.group("open")
        self_closing = match.group("attrs").rstrip().endswith("/")
        if opened.lower() == name.lower() and not self_closing and opened.lower() not in _VOID_ELEMENTS:
            depth += 1


def _extract_fills(children: str) -> tuple[str, list[tuple[str, str]]]:
    """Split ``children`` into default content and ``(slot_name, body)`` fills.

    Only direct children carry slot assignment (matching native slotting); a
    ``slot=`` deeper in the tree stays part of the surrounding content.
    """
    default: list[str] = []
    fills: list[tuple[str, str]] = []
    pos = 0
    length = len(children)
    while pos < length:
        match = _CHILD_TOKEN.search(children, pos)
        if match is None:
            default.append(children[pos:])
            break
        default.append(children[pos : match.start()])
        if match.group("open") is None:
            # A Jinja construct or a stray close tag is plain content.
            default.append(match.group(0))
            pos = match.end()
            continue
        name = match.group("open")
        attrs = match.group("attrs")
        if attrs.rstrip().endswith("/") or name.lower() in _VOID_ELEMENTS:
            extent_end = inner_end = match.end()
        else:
            extent_end, inner_end = _match_element(children, name, match.end())
        slot_name = _read_slot(attrs)
        if slot_name is None:
            default.append(children[match.start() : extent_end])
        elif name.lower() == "template":
            fills.append((slot_name, children[match.end() : inner_end]))
        else:
            open_tag = f"<{name}{_remove_slot(attrs)}>"
            fills.append((slot_name, open_tag + children[match.end() : extent_end]))
        pos = extent_end
    return "".join(default), fills


def _build_slots(children: str, fresh: Callable[[], int]) -> tuple[str, str]:
    """Split a component's children into a default slot and named slots.

    Returns the ``component(...)`` call suffix (``, _jc_content=..., _jc_slots=...``)
    and the ``{% set %}`` prelude that captures each slot's content.
    """
    default, fills = _extract_fills(children)
    grouped: dict[str, str] = {}
    for slot_name, body in fills:
        grouped[slot_name] = grouped.get(slot_name, "") + body

    prelude: list[str] = []
    suffix = ""
    if default.strip():
        var = f"_jc_content_{fresh()}"
        prelude.append(f"{{% set {var} %}}{default}{{% endset %}}")
        suffix += f", _jc_content={var}"
    if grouped:
        pairs = []
        for slot_name, body in grouped.items():
            var = f"_jc_slot_{fresh()}"
            prelude.append(f"{{% set {var} %}}{body}{{% endset %}}")
            pairs.append(f'"{slot_name}": {var}')
        suffix += ", _jc_slots={" + ", ".join(pairs) + "}"
    return suffix, "".join(prelude)


def _parse_open(match: re.Match[str]) -> tuple[str, str, str | None, bool]:
    """Parse a component open tag into ``(name, props_suffix, slot_name, self_closing)``.

    A literal ``slot="x"`` is pulled out as the parent slot assignment rather than
    passed on as a prop.
    """
    name = match.group("open")
    attrs = match.group("attrs")
    self_closing = attrs.rstrip().endswith("/")
    if self_closing:
        attrs = attrs.rstrip()[:-1]
    slot_name = _read_slot(attrs)
    if slot_name is not None:
        attrs = _remove_slot(attrs)
    suffix = "".join(f", {_attribute_kwarg(m)}" for m in _ATTR.finditer(attrs))
    return name, suffix, slot_name, self_closing


def _rewrite_components(source: str) -> str:
    counter = 0

    def fresh() -> int:
        nonlocal counter
        counter += 1
        return counter

    root: list[str] = []
    stack: list[tuple[str, str, list[str], str, str | None]] = []
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
            name, suffix, slot_name, self_closing = _parse_open(match)
            if self_closing:
                buffer.append(_wrap_slot(f'{{{{ component("{name}"{suffix}) }}}}', slot_name))
            else:
                stack.append((name, suffix, buffer, match.group(0), slot_name))
                buffer = []
            continue

        # Closing tag: pair it only with a matching innermost open tag. A stray
        # or mismatched close is kept as literal text instead of being paired
        # with an unrelated opener (which would silently drop it).
        if not stack or stack[-1][0] != match.group("close"):
            buffer.append(match.group(0))
            continue
        name, suffix, parent, _raw, slot_name = stack.pop()
        slot_suffix, prelude = _build_slots("".join(buffer), fresh)
        call = f'{prelude}{{{{ component("{name}"{suffix}{slot_suffix}) }}}}'
        parent.append(_wrap_slot(call, slot_name))
        buffer = parent

    # Unclosed component tags: emit them verbatim so their content is preserved
    # rather than silently dropped.
    while stack:
        _name, _suffix, parent, raw, _slot = stack.pop()
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
