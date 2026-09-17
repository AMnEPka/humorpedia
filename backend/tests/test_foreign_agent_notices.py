from services.foreign_agent_notices import _has_legacy_notice, mark_html
from scripts.migrate_foreign_agent_notices import (
    clean_subject_value,
    annotate_unlinked_foreign_agents,
    link_known_mentions,
    remove_obsolete_notes,
    normalize_special_tatyana_marker,
    remove_empty_text_modules,
    rich_text_slots,
)


def test_marks_only_links_to_flagged_people():
    html = (
        '<p><a href="/people/ruslan-belyi">Руслан Белый</a> и '
        '<a href="/people/pavel-volya">Павел Воля</a></p>'
    )

    result, marked = mark_html(html, {"ruslan-belyi"})

    assert marked is True
    assert result.count('class="foreign-agent-marker"') == 1
    assert '<a href="/people/pavel-volya">Павел Воля</a>' in result


def test_marker_is_idempotent():
    html = (
        '<a href="/people/ruslan-belyi">Руслан Белый</a>'
        '<sup class="foreign-agent-marker">*</sup>'
    )

    result, marked = mark_html(html, {"ruslan-belyi"})

    assert marked is False
    assert result == html


def test_marks_annotated_external_link():
    html = '<a href="https://example.test" data-foreign-agent-person="danila-poperechniy">Интервью Данилы Поперечного</a>'

    result, marked = mark_html(html, {"danila-poperechniy"})

    assert marked is True
    assert result.endswith('<sup class="foreign-agent-marker" title="признан в РФ иностранным агентом">*</sup>')


def test_marks_annotated_plain_name_without_adding_link():
    html = '<p><span data-foreign-agent-person="ruslan-belyi">Руслан Белый</span></p>'

    result, marked = mark_html(html, {"ruslan-belyi"})

    assert marked is True
    assert 'href=' not in result
    assert result.count('class="foreign-agent-marker"') == 1


def test_marks_structured_special_notice_with_its_own_marker():
    html = (
        '<span data-foreign-agent-marker="**" '
        'data-foreign-agent-notice="признана в РФ иностранным агентом, экстремистом и террористом">'
        'Татьяна Лазарева</span>'
    )
    notices = {}

    result, marked = mark_html(html, set(), notices=notices)

    assert marked is True
    assert result.endswith(
        '<sup class="foreign-agent-marker" '
        'title="признана в РФ иностранным агентом, экстремистом и террористом">**</sup>'
    )
    assert notices == {
        "**": "признана в РФ иностранным агентом, экстремистом и террористом"
    }


def test_unwraps_link_to_current_person():
    html = '<p><a href="/people/ruslan-belyi">Руслан Белый</a></p>'

    result, marked = mark_html(html, {"ruslan-belyi"}, unlink_slug="ruslan-belyi")

    assert marked is True
    assert '<a ' not in result
    assert 'Руслан Белый<sup class="foreign-agent-marker"' in result


def test_migration_annotates_old_starred_mention_without_link():
    result, count = link_known_mentions('<p>Наставник — Русланом Белым*.</p>')

    assert count == 1
    assert result == '<p>Наставник — <span data-foreign-agent-person="ruslan-belyi">Русланом Белым</span>.</p>'


def test_migration_replaces_generated_person_link_with_annotation():
    result, count = link_known_mentions('<p><a href="/people/ruslan-belyi">Руслан Белый</a>.</p>')

    assert count == 1
    assert result == '<p><span data-foreign-agent-person="ruslan-belyi">Руслан Белый</span>.</p>'


def test_migration_keeps_note_when_unknown_star_remains():
    document = {"modules": [
        {"data": {"content": "<p>Семён Слепаков* выступил.</p>"}},
        {"data": {"content": "<p>* - признан в РФ иностранным агентом.</p>"}},
    ]}

    assert remove_obsolete_notes(document) == 0
    assert len(document["modules"]) == 2


def test_migration_removes_note_replaced_by_structured_status():
    document = {"modules": [
        {"data": {"content": '<p><a href="/people/ruslan-belyi">Руслан Белый</a>.</p>'}},
        {"data": {"content": "<p>* - признан в РФ иностранным агентом.</p>"}},
    ]}

    assert remove_obsolete_notes(document) == 1
    assert len(document["modules"]) == 1


def test_subject_cleanup_does_not_touch_other_names():
    value = "Михаил Шац * и Татьяна Лазарева**"

    assert clean_subject_value(value, "mikhail-shats") == "Михаил Шац и Татьяна Лазарева**"


def test_special_notice_does_not_suppress_dynamic_standard_notice():
    assert _has_legacy_notice({"modules": [{"data": {
        "content": "<p>** - признана в РФ иностранным агентом, экстремистом и террористом.</p>"
    }}]}) is False


def test_special_tatyana_marker_gets_distinct_symbol():
    document = {"modules": [{"data": {
        "content": "<p>Татьяна Лазарева* и Михаил Шац.</p><p>* - признана в РФ иностранным агентом, экстремистом и террористом.</p>"
    }}]}

    assert normalize_special_tatyana_marker(document) == 1
    content = document["modules"][0]["data"]["content"]
    assert 'data-foreign-agent-marker="**"' in content
    assert ">Татьяна Лазарева</span>" in content
    assert "признана в РФ" in content
    assert "<p>*" not in content


def test_migration_processes_structured_table_cells():
    document = {"modules": [{"data": {
        "rows": [["Белый*", "Руслан Белый* и Антон Иванов", 42]],
    }}]}

    for holder, key in rich_text_slots(document):
        holder[key], _ = link_known_mentions(holder[key])

    first, second, number = document["modules"][0]["data"]["rows"][0]
    assert 'data-foreign-agent-person="ruslan-belyi"' in first
    assert 'data-foreign-agent-person="ruslan-belyi"' in second
    assert number == 42


def test_migration_structures_foreign_agent_without_person_page():
    document = {"modules": [{"data": {
        "content": "<p>В выпуске участвовал Максим Покровский*.</p>",
    }}]}

    assert annotate_unlinked_foreign_agents(document) == 1
    content = document["modules"][0]["data"]["content"]
    assert 'data-foreign-agent-marker="*"' in content
    assert 'data-foreign-agent-notice="признан в РФ иностранным агентом"' in content
    assert "Покровский*" not in content


def test_migration_removes_empty_text_module_left_by_notice():
    document = {"modules": [
        {"id": "notice", "type": "text_block", "data": {"content": "  "}},
        {"id": "content", "type": "text_block", "data": {"content": "<p>Текст</p>"}},
        {"id": "system", "type": "tags_cloud", "data": {}},
    ]}

    assert remove_empty_text_modules(document) == 1
    assert [module["id"] for module in document["modules"]] == ["content", "system"]
