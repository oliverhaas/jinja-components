"""The compile-time tag and slot rewriter."""

import pytest

from jinja_components.tags import compile_component_tags as compile_tags


@pytest.mark.unit
def test_self_closing_no_attrs():
    assert compile_tags("<Button/>") == '{{ component("Button") }}'


@pytest.mark.unit
def test_literal_attribute():
    assert compile_tags('<Button type="submit"/>') == '{{ component("Button", type="submit") }}'


@pytest.mark.unit
def test_colon_bound_attribute():
    assert compile_tags('<Badge :count="items|length"/>') == '{{ component("Badge", count=(items|length)) }}'


@pytest.mark.unit
def test_mustache_attribute():
    assert compile_tags("<Title value={{ page }}/>") == '{{ component("Title", value=(page)) }}'


@pytest.mark.unit
def test_boolean_attribute():
    assert compile_tags("<Button disabled/>") == '{{ component("Button", disabled=True) }}'


@pytest.mark.unit
def test_children_become_content():
    out = compile_tags("<Card><b>hi</b></Card>")
    assert "{% set _jc_content_1 %}<b>hi</b>{% endset %}" in out
    assert 'component("Card", _jc_content=_jc_content_1)' in out


@pytest.mark.unit
def test_jinja_constructs_pass_through_untouched():
    src = "{% if count < Max %}{{ x }}{% endif %}"
    assert compile_tags(src) == src


@pytest.mark.unit
def test_lowercase_html_is_left_alone():
    assert compile_tags("<div>hello</div>") == "<div>hello</div>"


@pytest.mark.unit
def test_named_template_fill_and_default_content():
    out = compile_tags("<Card><template #header><h2>x</h2></template>body</Card>")
    assert "{% set _jc_content_1 %}body{% endset %}" in out
    assert "{% set _jc_slot_2 %}<h2>x</h2>{% endset %}" in out
    assert "_jc_content=_jc_content_1" in out
    assert '_jc_slots={"header": _jc_slot_2}' in out


@pytest.mark.unit
def test_slot_definition_named_with_fallback():
    out = compile_tags('<slot name="header">none</slot>')
    assert out == '{% if "header" in slots %}{{ slots["header"] }}{% else %}none{% endif %}'


@pytest.mark.unit
def test_slot_definition_default():
    assert compile_tags("<slot></slot>") == '{{ content if content is not none else "" }}'


@pytest.mark.unit
def test_slot_self_closing_named():
    assert compile_tags('<slot name="footer"/>') == '{{ slots.get("footer", "") }}'


@pytest.mark.unit
def test_unquoted_attribute_values():
    assert compile_tags("<Echo value=5/>") == '{{ component("Echo", value=5) }}'
    assert compile_tags("<Echo :value=count/>") == '{{ component("Echo", value=(count)) }}'


@pytest.mark.unit
def test_mustache_attribute_with_gt_operator():
    # The '>' lives inside {{ }}, so it must not terminate the tag early.
    assert compile_tags("<Title :visible={{ count > 0 }}/>") == '{{ component("Title", visible=(count > 0)) }}'
    assert compile_tags("<Card value={{ a > b }}>x</Card>").endswith("value=(a > b), _jc_content=_jc_content_1) }}")


@pytest.mark.unit
def test_quoted_attribute_value_with_backslash_is_escaped():
    # A trailing backslash must not escape the closing quote of the emitted literal.
    assert compile_tags('<B label="C:\\"/>') == '{{ component("B", label="C:\\\\") }}'


@pytest.mark.unit
def test_unclosed_component_tag_is_preserved_not_dropped():
    # A forgotten </Card> keeps the tag and following content as literal text.
    assert compile_tags("before <Card>inside") == "before <Card>inside"


@pytest.mark.unit
def test_stray_closing_tag_is_left_as_literal():
    assert compile_tags("</Card> after") == "</Card> after"


@pytest.mark.unit
def test_invalid_attribute_name_raises():
    with pytest.raises(ValueError, match="keyword argument"):
        compile_tags('<Button data-id="1"/>')
