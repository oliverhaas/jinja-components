"""Component base class and registry."""

import pytest

from jinja_components import Component, get_component, register


@pytest.mark.unit
def test_subclass_auto_registers():
    class Button(Component):
        pass

    assert get_component("Button") is Button


@pytest.mark.unit
def test_register_alias_adds_extra_name():
    class Alert(Component):
        pass

    register("Banner")(Alert)

    assert get_component("Banner") is Alert
    assert get_component("Alert") is Alert


@pytest.mark.unit
def test_get_component_unknown_raises_lookup_error():
    with pytest.raises(LookupError):
        get_component("DoesNotExist")


@pytest.mark.unit
def test_abstract_base_is_not_registered():
    class CardBase(Component, abstract=True):
        pass

    class InfoCard(CardBase):
        pass

    assert get_component("InfoCard") is InfoCard
    with pytest.raises(LookupError):
        get_component("CardBase")


@pytest.mark.unit
def test_get_context_data_default_returns_kwargs():
    class Card(Component):
        pass

    assert Card().get_context_data(a=1, b=2) == {"a": 1, "b": 2}


@pytest.mark.unit
def test_get_template_name_explicit_is_verbatim():
    class Widget(Component):
        template_name = "custom/widget.html"

    assert Widget.get_template_name("anything") == "custom/widget.html"


@pytest.mark.unit
def test_get_template_name_derives_nested_path_from_package():
    class Sidebar(Component):
        pass

    Sidebar.__module__ = "myapp.components.sidebar.sidebar"

    assert Sidebar.get_template_name("myapp.components") == "sidebar/template.jinja"


@pytest.mark.unit
def test_get_template_name_falls_back_to_package_folder():
    class Button(Component):
        pass

    Button.__module__ = "myapp.components.button.button"

    assert Button.get_template_name() == "button/template.jinja"


@pytest.mark.unit
def test_get_template_name_top_level_module_uses_default():
    class Loose(Component):
        pass

    Loose.__module__ = "loose"

    assert Loose.get_template_name() == "template.jinja"
