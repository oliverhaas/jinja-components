"""Environment wiring via setup()."""

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment

from jinja_components import Component, ComponentsExtension, setup


@pytest.mark.unit
def test_setup_is_idempotent():
    env = Environment(autoescape=True)
    setup(env)
    setup(env)

    identifiers = [e for e in env.extensions if e == ComponentsExtension.identifier]
    assert len(identifiers) == 1
    assert "component" in env.globals


@pytest.mark.unit
def test_setup_repeated_does_not_stack_loaders_or_wipe_package(tmp_path):
    env = Environment(loader=DictLoader({}), autoescape=True)
    setup(env, package="myapp.components", root=tmp_path)
    setup(env, root=tmp_path)  # a defensive second call
    setup(env)  # a bare call must not reset the package

    assert env.globals["_jinja_components_package"] == "myapp.components"
    # The components loader is chained exactly once, not nested on every call.
    assert isinstance(env.loader, ChoiceLoader)
    assert len(env.loader.loaders) == 2


@pytest.mark.unit
def test_setup_root_adds_filesystem_loader(tmp_path):
    (tmp_path / "widget").mkdir()
    (tmp_path / "widget" / "template.jinja").write_text("<i>{{ content }}</i>")

    class Widget(Component):
        pass

    Widget.__module__ = "components.widget.widget"

    env = Environment(autoescape=True)
    setup(env, package="components", root=tmp_path)

    assert env.from_string("<Widget>x</Widget>").render() == "<i>x</i>"


@pytest.mark.unit
def test_setup_root_keeps_existing_loader_ahead(tmp_path):
    # Same key in both loaders, different content, so ordering is observable.
    (tmp_path / "card.html").write_text("from-root")

    env = Environment(loader=DictLoader({"card.html": "from-existing"}), autoescape=True)
    setup(env, root=tmp_path)

    assert env.get_template("card.html").render() == "from-existing"
