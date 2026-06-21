"""Native-style slots: named fills, the default slot, and fallbacks."""

import pytest

from jinja_components import Component


@pytest.mark.unit
def test_named_and_default_slots(env_factory):
    class Card(Component):
        template_name = "card.html"

    env = env_factory(
        {
            "card.html": (
                '<div><header><slot name="header">H</slot></header>'
                "<main><slot></slot></main>"
                '<footer><slot name="footer">F</slot></footer></div>'
            ),
            "page.html": (
                '<Card><template slot="header">Head</template>Body<template slot="footer">Foot</template></Card>'
            ),
        },
    )

    expected = "<div><header>Head</header><main>Body</main><footer>Foot</footer></div>"
    assert env.get_template("page.html").render() == expected


@pytest.mark.unit
def test_named_fill_via_slot_attribute_projects_the_element(env_factory):
    class Card(Component):
        template_name = "card.html"

    env = env_factory(
        {
            "card.html": '<div><header><slot name="header"/></header><main><slot></slot></main></div>',
            "page.html": '<Card><h2 slot="header">Title</h2>Body</Card>',
        },
    )

    expected = "<div><header><h2>Title</h2></header><main>Body</main></div>"
    assert env.get_template("page.html").render() == expected


@pytest.mark.unit
def test_named_slot_fallback_used_when_not_filled(env_factory):
    class Card(Component):
        template_name = "card.html"

    env = env_factory(
        {
            "card.html": '<header><slot name="header">Default</slot></header>',
            "page.html": "<Card></Card>",
        },
    )

    assert env.get_template("page.html").render() == "<header>Default</header>"


@pytest.mark.unit
def test_default_slot_fallback_used_when_no_children(env_factory):
    class Card(Component):
        template_name = "card.html"

    env = env_factory(
        {
            "card.html": "<main><slot>Empty</slot></main>",
            "page.html": "<Card/>",
        },
    )

    assert env.get_template("page.html").render() == "<main>Empty</main>"


@pytest.mark.unit
def test_filled_named_slot_suppresses_fallback_even_when_empty(env_factory):
    # Filling a slot with empty content is a deliberate choice and must win over
    # the fallback -- presence of the fill, not its truthiness, decides.
    class Card(Component):
        template_name = "card.html"

    env = env_factory(
        {
            "card.html": '<header><slot name="header">Default</slot></header>',
            "page.html": '<Card><template slot="header"></template></Card>',
        },
    )

    assert env.get_template("page.html").render() == "<header></header>"


@pytest.mark.unit
def test_nested_components_inside_a_slot(env_factory):
    class Card(Component):
        template_name = "card.html"

    class Badge(Component):
        template_name = "badge.html"

        def get_context_data(self, label=""):
            return {"label": label}

    env = env_factory(
        {
            "card.html": '<div><slot name="header">x</slot></div>',
            "badge.html": "<span>{{ label }}</span>",
            "page.html": '<Card><template slot="header"><Badge label="New"/></template></Card>',
        },
    )

    assert env.get_template("page.html").render() == "<div><span>New</span></div>"


@pytest.mark.unit
def test_component_fills_slot_via_slot_attribute(env_factory):
    # A component can be slotted directly with slot="name", without a wrapper.
    class Card(Component):
        template_name = "card.html"

    class Badge(Component):
        template_name = "badge.html"

        def get_context_data(self, label=""):
            return {"label": label}

    env = env_factory(
        {
            "card.html": '<div><slot name="header">x</slot></div>',
            "badge.html": "<span>{{ label }}</span>",
            "page.html": '<Card><Badge slot="header" label="New"/></Card>',
        },
    )

    assert env.get_template("page.html").render() == "<div><span>New</span></div>"
