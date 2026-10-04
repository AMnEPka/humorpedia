from scripts.normalize_editorial_quotes import normalize_text, transform_document
import pytest


def test_normalizes_multiple_pairs_and_preserves_html_attributes_byte_for_byte():
    source = '<p class="lead">Шоу &quot;Союз&quot; и <a href="/shows/foo?q=%22" title="Текст">"Игра"</a>.</p>'
    result = normalize_text(source)
    assert result["value"] == '<p class="lead">Шоу «Союз» и <a href="/shows/foo?q=%22" title="Текст">«Игра»</a>.</p>'
    assert result["pairs"] == 2
    assert result["issues"] == []


def test_pairs_can_cross_inline_tags_and_numeric_entities():
    result = normalize_text('<p>&#34;Творческое <b>объединение</b>&#x22;</p>')
    assert result["value"] == '<p>«Творческое <b>объединение</b>»</p>'


def test_nested_pairs_use_lapki_only_when_inside_outer_quotes():
    result = normalize_text('«Планета "Парни из Баку"», затем "Игра".')
    assert result["value"] == '«Планета „Парни из Баку“», затем «Игра».'
    assert result["pairs"] == 2


def test_unbalanced_cell_does_not_shift_quotes_in_other_cells():
    result = normalize_text('<table><tr><td>"Союз</td><td>Дуэт "Красивые"</td></tr></table>')
    assert result["value"] == '<table><tr><td>"Союз</td><td>Дуэт «Красивые»</td></tr></table>'
    assert result["pairs"] == 1
    assert len(result["issues"]) == 1


def test_line_break_inside_a_cell_or_paragraph_does_not_break_a_pair():
    source = '<td>Трио "Просто попутчица,<br />и ты об этом знаешь"</td>'
    assert normalize_text(source)["value"] == '<td>Трио «Просто попутчица,<br />и ты об этом знаешь»</td>'


def test_mixed_quotes_require_explicit_repair():
    source = 'Сериал «Реальные пацаны"?'
    assert normalize_text(source)["value"] == source
    assert normalize_text(source, repair_mixed=True)["value"] == 'Сериал «Реальные пацаны»?'


def test_technical_blocks_and_measurement_quotes_are_not_changed():
    source = '<p>Экран 15"; шоу "Союз".</p><pre>print("x")</pre><script>"x"</script>'
    result = normalize_text(source)
    assert '<pre>print("x")</pre><script>"x"</script>' in result["value"]
    assert '15"' in result["value"]
    assert result["issues"]


def test_already_normalized_text_is_idempotent():
    source = '<p>«Планета „Парни из Баку“» и «Игра».</p>'
    assert normalize_text(source) == {"value": source, "pairs": 0, "issues": []}


def test_document_preserves_urls_ids_taxonomy_and_other_data():
    document = {
        "_id": "id", "slug": '"slug"', "tags": ['"tag"'], "primary_tag": '"tag"',
        "aliases": ['"alias"'], "title": 'Шоу "Союз"',
        "modules": [{"id": "module", "type": "text_block", "data": {
            "content": '<p>"Игра"</p>', "url": 'https://example.test/"x"',
        }}],
    }
    updated, changes, issues = transform_document("shows", document)
    assert updated["title"] == 'Шоу «Союз»'
    assert updated["modules"][0]["data"]["content"] == '<p>«Игра»</p>'
    for key in ("_id", "slug", "tags", "primary_tag", "aliases"):
        assert updated[key] == document[key]
    assert updated["modules"][0]["data"]["url"] == document["modules"][0]["data"]["url"]
    assert document["title"] == 'Шоу "Союз"'
    assert len(changes) == 2
    assert issues == []


def test_fact_label_and_order_are_renamed_together_without_data_loss():
    document = {"facts": {'Лига "Москва"': 'Победитель "Кубка"'}, "facts_order": ['Лига "Москва"']}
    updated, changes, issues = transform_document("teams", document)
    assert updated["facts"] == {'Лига «Москва»': 'Победитель «Кубка»'}
    assert updated["facts_order"] == ['Лига «Москва»']
    assert issues == []


def test_only_approved_empty_timeline_descriptions_are_cleared():
    document = {"modules": [{"type": "timeline", "data": {"events": [
        {"title": "Событие", "description": '"'},
    ]}}]}
    updated, changes, issues = transform_document("teams", document)
    assert updated["modules"][0]["data"]["events"][0] == {"title": "Событие", "description": ""}
    assert len(changes) == 1
    assert issues == []


def test_season_internal_notes_are_preserved_but_public_contests_are_normalized():
    document = {"extra": {"editorial_notes": 'Источник "X"'}, "stages": [{"games": [{
        "contests": ['Количество "да"'], "notes": '<p>"Союз"</p>',
    }]}]}
    updated, changes, issues = transform_document("seasons", document)
    assert updated["extra"] == document["extra"]
    assert updated["stages"][0]["games"][0]["contests"] == ['Количество «да»']
    assert updated["stages"][0]["games"][0]["notes"] == '<p>«Союз»</p>'


@pytest.mark.parametrize("collection,identifier,index,source,expected", [
    ("shows", "fdf9cf6c-fd3b-41e5-ad96-9f474c7047f3", 16,
     '<td>Итальянское "Поле чудес</td>', '<td>Итальянское «Поле чудес»</td>'),
    ("shows", "e3f66a7b-f77f-4102-b2f1-5d53b26d494d", 13,
     '<td>Дуэт "Клан Ниндзя</td>', '<td>Дуэт «Клан Ниндзя»</td>'),
    ("shows", "0228436e-56ca-4ea1-90a8-600c7bb0393e", 6,
     '<td>Дуэт "ИП "Успех"</td>', '<td>Дуэт «ИП „Успех“»</td>'),
    ("kvn", "8f62260f-13b8-482c-9e54-0b0fd9315082", 6,
     'Сборная Амурской области" (Благовещенск)', '«Сборная Амурской области» (Благовещенск)'),
    ("shows", "af0d6bda-61cf-43d1-ab4d-c0a280c54742", 8,
     '<td>Саратов" </td>', '<td>Саратов </td>'),
])
def test_approved_manual_repairs_are_scoped_to_one_document_and_field(
        collection, identifier, index, source, expected):
    document = {"_id": identifier, "modules": [{} for _ in range(index)] + [
        {"type": "text_block", "data": {"content": source}}]}
    updated, changes, issues = transform_document(collection, document)
    assert updated["modules"][index]["data"]["content"] == expected
    assert issues == []
    document["_id"] = "another-document"
    other, _, _ = transform_document(collection, document)
    assert other["modules"][index]["data"]["content"] == source


def test_approved_truncated_word_is_restored_only_in_the_two_agreed_fields():
    document = {"_id": "939c7089-1b54-42f6-a068-9fbefac401e1",
                "excerpt": 'И "дес…', "seo": {"meta_description": 'И "дес…'}}
    updated, changes, issues = transform_document("news", document)
    assert updated["excerpt"] == 'И «десятых»…'
    assert updated["seo"]["meta_description"] == 'И «десятых»…'
    assert issues == []


def test_public_season_text_arrays_are_covered():
    document = {"jury": ['Представитель "Союза"'], "editors": ['Редактор "Кубка"']}
    updated, changes, issues = transform_document("seasons", document)
    assert updated == {"jury": ['Представитель «Союза»'], "editors": ['Редактор «Кубка»']}
    assert issues == []


def test_nested_fact_labels_and_score_keys_match_normalized_contest_names():
    document = {"modules": [{"type": "facts_table", "data": {
        "facts": {'Лига "Москва"': "Победитель"}, "facts_order": ['Лига "Москва"'],
    }}], "stages": [{"games": [{"contests": ['Количество "да"'], "results": [
        {"team_id": "abc", "scores": {'Количество "да"': 7.5}, "total": 7.5},
    ]}]}]}
    updated, changes, issues = transform_document("seasons", document)
    assert updated["modules"][0]["data"]["facts"] == {'Лига «Москва»': "Победитель"}
    assert updated["modules"][0]["data"]["facts_order"] == ['Лига «Москва»']
    game = updated["stages"][0]["games"][0]
    assert game["results"][0]["scores"][game["contests"][0]] == 7.5
    assert game["results"][0]["total"] == 7.5
    assert game["results"][0]["team_id"] == "abc"
    assert issues == []


def test_fact_key_collision_is_reported_without_losing_values():
    document = {"facts": {'Лига "Москва"': "А", 'Лига «Москва»': "Б"}}
    updated, changes, issues = transform_document("teams", document)
    assert updated == document
    assert issues[0]["reason"] == "конфликт названий фактов"
