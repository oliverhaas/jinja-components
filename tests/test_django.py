"""Integration with Django's Jinja2 template backend."""

import pytest
from django.template import engines
from django.test import RequestFactory

from jinja_components import Component
from jinja_components.django import environment


@pytest.mark.unit
def test_django_jinja2_backend_renders_component():
    class Greeting(Component):
        template_name = "greeting/template.jinja"

        def get_context_data(self, name="World"):
            return {"name": name}

    engine = engines["jinja2"]
    template = engine.from_string('<Greeting name="Spock"/>')

    assert template.render({}) == "<p>Hello Spock</p>"


@pytest.mark.unit
def test_django_backend_passes_request_to_component():
    captured = {}

    class Probe(Component):
        template_name = "greeting/template.jinja"

        def get_context_data(self, name="World"):
            captured["request"] = self.request
            return {"name": name}

    request = RequestFactory().get("/")
    engine = engines["jinja2"]
    template = engine.from_string("<Probe/>")
    template.render({}, request)

    assert captured["request"] is request


@pytest.mark.unit
def test_environment_loads_components_from_root_setting(tmp_path, settings):
    # The JINJA_COMPONENTS "root" setting must reach setup() as a filesystem
    # search root, so a co-located template resolves without a DIRS entry.
    (tmp_path / "greeting").mkdir()
    (tmp_path / "greeting" / "template.jinja").write_text("<p>Hi {{ name }}</p>")
    settings.JINJA_COMPONENTS = {"package": "", "root": tmp_path}

    class Greeting(Component):
        template_name = "greeting/template.jinja"

        def get_context_data(self, name="World"):
            return {"name": name}

    env = environment(autoescape=True)

    assert env.from_string('<Greeting name="Bones"/>').render() == "<p>Hi Bones</p>"
