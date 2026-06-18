"""End-to-end rendering through a standalone Jinja2 environment."""

import pytest
from jinja2 import DictLoader, Environment, pass_context, select_autoescape

from jinja_components import Component, setup


@pytest.mark.unit
def test_render_simple_component(env_factory):
    class Button(Component):
        template_name = "button.html"

        def get_context_data(self, type="button"):
            return {"type": type}

    env = env_factory(
        {
            "button.html": '<button type="{{ type }}">{{ content }}</button>',
            "page.html": '<Button type="submit">Save</Button>',
        },
    )

    assert env.get_template("page.html").render() == '<button type="submit">Save</button>'


@pytest.mark.unit
def test_self_closing_component_without_children(env_factory):
    class Divider(Component):
        template_name = "divider.html"

    env = env_factory({"divider.html": "<hr>", "page.html": "<Divider/>"})

    assert env.get_template("page.html").render() == "<hr>"


@pytest.mark.unit
def test_bound_attribute_is_evaluated(env_factory):
    class Echo(Component):
        template_name = "echo.html"

        def get_context_data(self, value=None):
            return {"value": value}

    env = env_factory(
        {
            "echo.html": "{{ value }}",
            "page.html": '{% set items = [1, 2, 3] %}<Echo :value="items|length"/>',
        },
    )

    assert env.get_template("page.html").render() == "3"


@pytest.mark.unit
def test_component_output_is_not_double_escaped(env_factory):
    class Box(Component):
        template_name = "box.html"

    env = env_factory(
        {
            "box.html": "<div>{{ content }}</div>",
            "page.html": "<Box><em>hi</em></Box>",
        },
    )

    assert env.get_template("page.html").render() == "<div><em>hi</em></div>"


@pytest.mark.unit
def test_props_are_escaped_under_autoescape(env_factory):
    # Caller data interpolated by a component must be escaped, not injected raw.
    class Box(Component):
        template_name = "box.html"

        def get_context_data(self, body=""):
            return {"body": body}

    env = env_factory(
        {
            "box.html": "<div>{{ body }}</div>",
            "page.html": '<Box :body="payload"/>',
        },
    )

    out = env.get_template("page.html").render(payload="<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


@pytest.mark.unit
def test_non_autoescaping_component_output_is_not_marked_safe():
    # With select_autoescape, a .jinja component renders unescaped; its output
    # must come back as a plain str so the autoescaping caller still escapes it.
    class Comment(Component):
        template_name = "comment.jinja"

        def get_context_data(self, body=""):
            return {"body": body}

    env = Environment(
        loader=DictLoader(
            {
                "comment.jinja": "<div>{{ body }}</div>",
                "page.html": '<main><Comment :body="payload"/></main>',
            },
        ),
        autoescape=select_autoescape(),
    )
    setup(env)

    out = env.get_template("page.html").render(payload="<img src=x onerror=alert(1)>")
    assert "<img" not in out
    assert "&lt;img" in out


@pytest.mark.unit
def test_request_is_available_to_context_globals_inside_component():
    class Widget(Component):
        template_name = "widget.html"

    env = Environment(
        loader=DictLoader({"widget.html": "rid={{ rid() }}", "page.html": "<Widget/>"}),
        autoescape=True,
    )
    setup(env)
    env.globals["rid"] = pass_context(lambda ctx: ctx.get("request") or "NONE")

    assert env.get_template("page.html").render(request="REQ-1") == "rid=REQ-1"


@pytest.mark.unit
def test_props_named_like_reserved_keys_reach_get_context_data(env_factory):
    # content/slots/request are reserved template vars, but a same-named prop
    # must still reach get_context_data instead of crashing or being dropped.
    seen = {}

    class Probe(Component):
        template_name = "probe.html"

        def get_context_data(self, **props):
            seen.update(props)
            return {}

    env = env_factory(
        {
            "probe.html": "ok",
            "page.html": '<Probe content="c" :slots="[1, 2]" request="r"/>',
        },
    )

    assert env.get_template("page.html").render() == "ok"
    assert seen == {"content": "c", "slots": [1, 2], "request": "r"}
