# jinja-components

[![PyPI version](https://img.shields.io/pypi/v/jinja-components.svg?style=flat)](https://pypi.org/project/jinja-components/)
[![Python versions](https://img.shields.io/pypi/pyversions/jinja-components.svg)](https://pypi.org/project/jinja-components/)
[![CI](https://github.com/oliverhaas/jinja-components/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/jinja-components/actions/workflows/ci.yml)

A class-based component system for Jinja2. A component is a Python class paired
with a co-located template. Components are authored in templates with
HTML-element tags (`<Button/>`) and native-style slots.

The tag syntax is rewritten to plain Jinja2 at compile time, during the
`preprocess` step, so rendered output goes through Jinja2's normal compiled and
bytecode-cached path with no per-render parsing overhead.

It works with plain Jinja2 and with any framework that exposes a Jinja2
`Environment` (Flask, FastAPI, Django's Jinja2 backend).

## Installation

```console
pip install jinja-components
```

For the Django backend integration:

```console
pip install "jinja-components[django]"
```

## Defining a component

A component is a subclass of `Component`. Subclassing registers it under its
class name automatically.

```python
from jinja_components import Component


class Button(Component):
    template_name = "button.html"

    def get_context_data(self, type="button", variant="primary"):
        return {"type": type, "variant": variant}
```

`get_context_data` receives the attributes passed at the call site as keyword
arguments and returns the context the template renders with. Its default
implementation returns the keyword arguments unchanged, so a component with no
class body still receives its attributes as template variables.

The component's template:

```html
<!-- button.html -->
<button type="{{ type }}" class="btn btn--{{ variant }}">{{ content }}</button>
```

`content` holds the children passed between the opening and closing tags (the
default slot).

## Using a component

Wire the extension into an environment with `setup`, then author components with
HTML-element tags:

```python
from jinja2 import Environment, FileSystemLoader
from jinja_components import setup

env = setup(Environment(loader=FileSystemLoader("templates"), autoescape=True))

env.from_string('<Button variant="danger">Delete</Button>').render()
# '<button type="button" class="btn btn--danger">Delete</button>'
```

A component tag must start with an uppercase letter (`<Button/>`); lowercase tags
(`<button>`) are treated as ordinary HTML and left untouched.

### Attributes

| Syntax | Compiles to | Meaning |
| --- | --- | --- |
| `type="submit"` | `type="submit"` | String literal |
| `:count="items \| length"` | `count=(items \| length)` | Jinja expression |
| `value={{ page }}` | `value=(page)` | Jinja expression (mustache form) |
| `disabled` | `disabled=True` | Boolean shorthand |

Attribute names must be valid Python keyword argument names. A name such as
`data-id` raises an error at compile time; bind it to a context dict in the
component instead.

### Template name resolution

If `template_name` is left at its default (`template.jinja`), the template is
looked up next to the component module, in a folder named after the package the
component lives in. Set `template_name` explicitly to point anywhere on the
environment's loader search path.

### Registering aliases

Use `register` to expose a component under an additional name:

```python
from jinja_components import Component, register


class Alert(Component): ...


register("Banner")(Alert)  # usable as both <Alert/> and <Banner/>
```

## Slots

Slots follow the native Web Components model. A component template declares slots;
the call site fills them.

Declare slots in the component template with `<slot>`. Content between the tags
is the fallback shown when the slot is not filled:

```html
<!-- card.html -->
<div class="card">
  <header><slot name="header">Untitled</slot></header>
  <main><slot></slot></main>
  <footer><slot name="footer"/></footer>
</div>
```

`<slot></slot>` with no name is the default slot, equivalent to `{{ content }}`.

Fill named slots at the call site with the `slot` attribute, the same way native
Web Components assign slots. The element carrying `slot="name"` is projected into
the matching `<slot name="name">`; anything without a `slot` attribute becomes the
default slot:

```html
<Card>
  <h2 slot="header">Invoice #42</h2>
  Thanks for your order.
  <p slot="footer">Paid in full</p>
</Card>
```

To fill a slot without an extra wrapper element (plain text, or several nodes),
use `<template slot="name">`. Its inner HTML is projected and the wrapper is
dropped:

```html
<Card>
  <template slot="footer">Paid <b>in full</b></template>
</Card>
```

Components can be slotted directly (`<Badge slot="header"/>`) and nested inside
fills. Multiple elements sharing a `slot` name fill it in document order.

## Django

Add the Jinja2 backend and point it at the bundled environment function:

```python
# settings.py
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

JINJA_COMPONENTS = {
    "package": "myproject.components",  # import package your component classes live in
    # "root": BASE_DIR / "components",  # optional extra template search root
}
```

The bundled `environment` function installs the extension only. If you already
have a custom environment function (to register `static`, `url`, `csrf_input`,
and your filters), keep it and call `setup` yourself instead:

```python
# myproject/jinja2_env.py
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from jinja2 import Environment
from jinja_components import setup


def environment(**options):
    env = Environment(**options)
    env.globals.update(static=staticfiles_storage.url, url=reverse)
    return setup(env, package="myproject.components")
```

A component's `get_context_data` can reach the current request through
`self.request`; the Django backend passes it through automatically.

## Limitations

- Scoped slots (passing data from a component back into a slot fill) are not
  supported.
- Rendering is synchronous; Jinja2's async rendering is not yet supported.
- A component's opening and closing tags must sit in the same Jinja block. The
  rewriter pairs them and lifts the children into a `{% set %}` capture, so
  splitting a pair across branches (`{% if x %}<Card>{% endif %} ... {% if x
  %}</Card>{% endif %}`) produces invalid Jinja. Wrap the whole `<Card>...</Card>`
  in the conditional instead.
- Attribute names must be valid Python identifiers, so hyphenated or namespaced
  HTML attributes (`data-id`, `aria-label`, `hx-get`) cannot be passed as props.
  Collect them into a dict in `get_context_data` and spread it in the template.
- Only `request` is forwarded into a component's isolated render context. Other
  Django context-processor values (`csrf_input`, `messages`, `perms`) are not
  auto-propagated; pass what a component needs explicitly via `get_context_data`
  or environment globals.
- Only a component's direct children are slotted, matching native slot
  assignment. A `slot=` on a deeper element stays part of the surrounding
  content rather than filling a slot of the outer component.
- Slot names must be literal. `slot="header"` assigns a slot, but a bound
  `:slot="x"` is passed through as an ordinary prop; dynamic slot targets are
  not supported.
- The `:` and mustache binding forms are mutually exclusive. A `:`-bound value
  is already an expression, so it must not contain `{{ }}` (`:value="{{ x }}"`
  raises); write `:value="x"` or `value="{{ x }}"` instead.

## License

MIT
