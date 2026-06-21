"""The compile-time tag and slot rewriter."""

import pytest
from jinja2 import Environment

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
def test_fill_via_slot_attribute_projects_the_element():
    # `slot="x"` on an element fills slot x; the element itself is the content,
    # and the slot attribute is stripped from the projected markup.
    out = compile_tags('<Card><h2 slot="header">x</h2>body</Card>')
    assert "{% set _jc_content_1 %}body{% endset %}" in out
    assert "{% set _jc_slot_2 %}<h2>x</h2>{% endset %}" in out
    assert "_jc_content=_jc_content_1" in out
    assert '_jc_slots={"header": _jc_slot_2}' in out
    assert "<h2 slot" not in out


@pytest.mark.unit
def test_fill_via_template_slot_strips_the_wrapper():
    # A <template slot="x"> projects only its inner HTML; the wrapper is dropped.
    out = compile_tags('<Card><template slot="footer">a<b>c</b></template>body</Card>')
    assert "{% set _jc_slot_2 %}a<b>c</b>{% endset %}" in out
    assert '_jc_slots={"footer": _jc_slot_2}' in out
    assert "<template" not in out


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


@pytest.mark.unit
def test_mismatched_closing_tag_does_not_pair_with_open():
    # A close whose name differs from the innermost open component must not be
    # paired with it (that would silently drop the close). The open is left
    # unclosed and the stray close is kept, both verbatim.
    assert compile_tags("<A></B>") == "<A></B>"


@pytest.mark.unit
def test_matched_nested_components_still_pair():
    out = compile_tags("<Outer><Inner>x</Inner></Outer>")
    assert 'component("Inner"' in out
    assert 'component("Outer"' in out


@pytest.mark.unit
def test_two_mustaches_in_quoted_value_become_a_literal_string():
    # Two {{ }} in one value is not a single expression; emit a literal string
    # rather than the invalid Jinja the greedy match used to produce.
    out = compile_tags('<Button value="{{ a }} {{ b }}"/>')
    assert out == '{{ component("Button", value="{{ a }} {{ b }}") }}'
    Environment(autoescape=True).from_string(out)  # must compile, not raise TemplateSyntaxError


@pytest.mark.unit
def test_quoted_single_mustache_becomes_expression():
    assert compile_tags('<Title value="{{ page }}"/>') == '{{ component("Title", value=(page)) }}'


@pytest.mark.unit
def test_bound_attribute_with_embedded_mustache_raises():
    with pytest.raises(ValueError, match="bound expression"):
        compile_tags('<Button :value="{{ a }} {{ b }}"/>')


@pytest.mark.unit
def test_multiple_fills_for_one_slot_concatenate_in_order():
    out = compile_tags('<Card><li slot="item">a</li><li slot="item">b</li></Card>')
    assert "{% set _jc_slot_1 %}<li>a</li><li>b</li>{% endset %}" in out
    assert '_jc_slots={"item": _jc_slot_1}' in out


@pytest.mark.unit
def test_void_element_can_fill_a_slot():
    out = compile_tags('<Card><img slot="logo" src="x.png"></Card>')
    assert '{% set _jc_slot_1 %}<img src="x.png">{% endset %}' in out
    assert "slot=" not in out.split("_jc_slots")[0]


@pytest.mark.unit
def test_nested_element_fill_keeps_its_whole_subtree():
    out = compile_tags('<Card><div slot="body"><span>deep</span></div></Card>')
    assert "{% set _jc_slot_1 %}<div><span>deep</span></div>{% endset %}" in out


@pytest.mark.unit
def test_fill_with_same_named_nested_elements_matches_outer_close():
    out = compile_tags('<Card><div slot="body"><div>inner</div></div></Card>')
    assert "{% set _jc_slot_1 %}<div><div>inner</div></div>{% endset %}" in out


@pytest.mark.unit
def test_unclosed_fill_element_runs_to_end_of_children():
    # A forgotten close on a fill element degrades gracefully: the fill captures
    # the rest of the children rather than dropping anything.
    out = compile_tags('<Card><section slot="body">no close</Card>')
    assert "{% set _jc_slot_1 %}<section>no close{% endset %}" in out


@pytest.mark.unit
def test_slot_attribute_below_a_direct_child_is_not_a_fill():
    # Only a component's direct children carry slot assignment (matching native
    # shadow-DOM slotting). A slot= deeper in the tree stays literal content.
    out = compile_tags('<Card><div slot="outer"><span slot="inner">x</span></div></Card>')
    assert '_jc_slots={"outer":' in out
    assert '"inner":' not in out
    assert '<span slot="inner">x</span>' in out


@pytest.mark.unit
def test_component_child_can_fill_a_slot_via_slot_attribute():
    # A slot= on a component child assigns it to the parent's slot; it must not
    # leak into the child component's own keyword arguments.
    out = compile_tags('<Card><Badge slot="header" label="hi"/></Card>')
    assert '{% set _jc_slot_1 %}{{ component("Badge", label="hi") }}{% endset %}' in out
    assert '_jc_slots={"header": _jc_slot_1}' in out
    assert "slot=" not in out.split("_jc_slots")[0]


@pytest.mark.unit
def test_real_template_element_without_slot_is_left_as_content():
    out = compile_tags('<Card><template id="row">x</template>body</Card>')
    assert '{% set _jc_content_1 %}<template id="row">x</template>body{% endset %}' in out
    assert "_jc_slots" not in out


@pytest.mark.unit
def test_quoted_values_stay_literal_and_do_not_inject_adjacent_attrs():
    # A quoted value ending in a backslash is a literal backslash; the following
    # quoted attribute stays a literal string, never an evaluated expression.
    assert compile_tags('<Img src="C:\\" alt="x"/>') == '{{ component("Img", src="C:\\\\", alt="x") }}'
