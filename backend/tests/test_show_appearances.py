"""Проверяем границы извлечения, основной состав и запрет массового создания людей."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import services.show_appearances as appearances
from services.show_appearances import apply_participant_card_links, extract, choose, caption, table_grid, Tree, text


def show(path, content='', modules=None):
    return {'_id': path, 'slug': path.split('/')[-1], 'full_path': path, 'title': path,
            'modules': modules or [{'type': 'text_block', 'data': {'content': content}}]}


PEOPLE = [{'_id': 'ivan', 'slug': 'ivan', 'full_name': 'Иван Иванов'},
          {'_id': 'petr', 'slug': 'petr', 'full_name': 'Пётр Петров'}]


def test_participants_not_judges_and_unselected_shows_untouched():
    content = '<table><tr><td>Сезон</td><td>Победитель</td><td>Наставник</td></tr><tr><td>1</td><td>Иван Иванов</td><td>Пётр Петров</td></tr></table>'
    rows, _ = extract([show('openmicrophone', content), show('unselected', content)], PEOPLE, [], [])
    assert len(rows) == 1
    assert rows[0]['person_id'] == 'ivan' and rows[0]['achievement'] == 'winner'


def test_episode_winner_is_only_participant_and_missing_person_is_pending():
    content = '<table><tr><td>Выпуск</td><td>Участники</td><td>Победитель</td></tr><tr><td>1</td><td>Иван Иванов, Новый Человек</td><td>Иван Иванов</td></tr></table>'
    rows, _ = extract([show('stendap-ruletka', content)], PEOPLE, [], [])
    assert len(rows) == 2
    assert all(r['achievement'] == 'participant' for r in rows)
    assert next(r for r in rows if r['person_name'] == 'Новый Человек')['person_id'] is None


def test_team_membership_links_to_show_without_flattening_team():
    team = {'_id': 't', 'name': 'Плюшки', 'show_id': 'zvezdy-ntv', 'slug': 'plushki'}
    member = {'team_id': 't', 'person_name': 'Иван Иванов', 'person_slug': 'ivan'}
    rows, _ = extract([show('zvezdy-ntv')], PEOPLE, [team], [member])
    assert len(rows) == 1 and rows[0]['person_id'] == 'ivan'
    assert caption(rows[0], 'Звёзды на НТВ') == 'Участник проекта «Звёзды на НТВ» в составе команды «Плюшки»'


def test_ubojnaya_counts_main_group_and_first_episode():
    modules = [{'type': 'table', 'data': {'headers': ['ФИО', 'Участия', 'Состав'], 'rows': [
        ['Дуэт «Красивые»', '44', 'Иван Иванов, Пётр Петров'], ['Дуэт «Другие»', '2', 'Иван Иванов, Новый Человек']] }},
        {'type': 'text_block', 'title': 'Статистика выпусков: 1-й сезон', 'data': {'content': '<table><tr><td>Выпуск</td><td>3</td></tr><tr><td>Участники:</td></tr><tr><td>Дуэт «Красивые»</td></tr></table>'}}]
    rows, _ = extract([show('ubojnaya-liga', modules=modules)], PEOPLE, [], [])
    chosen = choose([r for r in rows if r['person_id'] == 'ivan'])
    assert len(chosen) == 1 and chosen[0]['group_name'] == 'Красивые'
    assert chosen[0]['first_episode'] == 3


def test_tie_uses_first_episode_manual_override_and_highest_achievement():
    base = {'show_id': 's', 'achievement': 'participant', 'appearances': 5, 'group_name': 'Один', 'group_kind': 'duet'}
    rows = [{**base, '_id': 'a', 'first_episode': 9}, {**base, '_id': 'b', 'first_episode': 2, 'achievement': 'finalist'}]
    assert choose(rows)[0]['_id'] == 'b'
    rows[0]['preferred'] = True
    assert choose(rows)[0]['_id'] == 'a' and choose(rows)[0]['achievement'] == 'finalist'
    assert 'сезон' not in caption(choose(rows)[0], 'Шоу')


def test_rowspan_keeps_winner_column():
    table = next(Tree('<table><tr><td rowspan="2">1</td><td>Иван Иванов</td><td>Жюри</td></tr><tr><td>Пётр Петров</td><td>Жюри</td></tr></table>').root.find('table'))
    assert [[text(c) for c in r] for r in table_grid(table)] == [['1', 'Иван Иванов', 'Жюри'], ['1', 'Пётр Петров', 'Жюри']]


def test_ambiguous_names_are_not_matched():
    people = PEOPLE + [{'_id': 'other-ivan', 'slug': 'other', 'full_name': 'Иван Иванов'}]
    content = '<h3>Участники</h3><ul><li>Иван Иванов</li><li><a href="/people/ivan">Иван Иванов</a></li></ul>'
    rows, _ = extract([show('standup', content)], people, [], [])
    assert {r['person_id'] for r in rows} == {None, 'ivan'}


def test_nested_show_does_not_include_its_parent_or_siblings():
    content = '<h3>Участники</h3><ul><li>Иван Иванов</li></ul>'
    rows, _ = extract([show('medium-quality/dvij/jam', content), show('medium-quality', content), show('medium-quality/other', content)], PEOPLE, [], [])
    assert len(rows) == 1 and rows[0]['show_path'] == 'medium-quality/dvij/jam'


def test_final_table_excludes_jury_and_semifinal_is_not_final():
    def table(episode):
        return '<table><tr><td>Выпуск</td><td>' + episode + '</td></tr><tr><td>Жюри</td><td>Пётр Петров</td></tr><tr><td>Участник</td><td>Результат</td></tr><tr><td>Иван Иванов</td><td>Победитель</td></tr></table>'
    root = show('smeh-bez-pravil')
    rows, _ = extract([root, show('smeh-bez-pravil/season1', table('Выпуск 9, 1/2 финала'))], PEOPLE, [], [])
    assert len(rows) == 1 and rows[0]['achievement'] == 'participant'
    rows, _ = extract([root, show('smeh-bez-pravil/season1', table('Выпуск 10, финал'))], PEOPLE, [], [])
    assert len(rows) == 1 and rows[0]['achievement'] == 'winner'


def test_final_order_does_not_include_votes_of_mentors():
    page = show('openmicrophone/season1', '<h3>Финал</h3><ol><li>Иван Иванов</li></ol><ul><li>Пётр Петров – Иван Иванов</li></ul>')
    rows, _ = extract([show('openmicrophone'), page], PEOPLE, [], [])
    assert len(rows) == 1 and rows[0]['person_id'] == 'ivan' and rows[0]['achievement'] == 'finalist'


def test_legacy_duet_page_is_expanded_to_members_not_spouses():
    group = {'_id': 'duet', 'slug': 'duet', 'full_name': 'Дуэт «Красивые»', 'modules': [
        {'title': 'Биография', 'data': {'content': '<p><a href="/people/ivan">Иван Иванов</a> и <a href="/people/petr">Пётр Петров</a>.</p><p>Супруги и коллеги: Новый Человек</p>'}}]}
    page = show('comedy-club', '<h3>Резиденты</h3><ul><li><a href="/people/duet">Дуэт «Красивые»</a></li></ul>')
    rows, _ = extract([page], PEOPLE + [group], [], [])
    assert {r['person_id'] for r in rows} == {'ivan', 'petr'}
    assert all(r['group_name'] == 'Красивые' for r in rows)


def test_zero_appearances_does_not_make_a_person_a_participant():
    modules = [{'type': 'table', 'data': {'headers': ['ФИО', 'Участия', 'Состав'],
                'rows': [['Дуэт «Облачко»', '0', 'Иван Иванов, Пётр Петров']]}}]
    rows, _ = extract([show('ubojnaya-liga', modules=modules)], PEOPLE, [], [])
    assert rows == []


def test_known_name_variant_selects_most_frequent_group():
    people = PEOPLE + [{'_id': 'andrey', 'slug': 'andrey-rodnoi', 'full_name': 'Андрей Родной'}]
    modules = [{'type': 'table', 'data': {'headers': ['ФИО', 'Участия', 'Состав'], 'rows': [
        ['Дуэт «Родной и Федяй»', '33', 'Андрей Родных, Новый Человек'],
        ['Дуэт «Праздник»', '1', 'Андрей Родной, Пётр Петров'],
    ]}}]
    rows, _ = extract([show('ubojnaya-liga', modules=modules)], people, [], [])
    assert choose([r for r in rows if r['person_id'] == 'andrey'])[0]['group_name'] == 'Родной и Федяй'


def test_startup_sync_runs_only_for_an_empty_collection(monkeypatch):
    collection = SimpleNamespace(find_one=AsyncMock(side_effect=[None, {'_id': 'existing'}]))
    db = SimpleNamespace(show_appearances=collection)
    sync = AsyncMock(return_value={'variants': 1})
    monkeypatch.setattr(appearances, 'sync', sync)

    assert asyncio.run(appearances.ensure_show_appearances(db)) == {'variants': 1}
    assert asyncio.run(appearances.ensure_show_appearances(db)) is None
    sync.assert_awaited_once_with(db, apply=True)


def test_existing_participant_cards_get_only_verified_person_links():
    modules = [{'type': 'participants', 'data': {'items': [
        {'name': 'Иван Иванов', 'person_slug': 'old-ivan'},
        {'name': 'Пётр Петров', 'person_slug': 'missing'},
        {'name': 'Тёзка'},
    ]}}]
    rows = [
        {'person_id': 'ivan', 'person_name': 'Иван Иванов', 'person_slug': 'old-ivan'},
        {'person_id': 'one', 'person_name': 'Тёзка', 'person_slug': None},
        {'person_id': 'two', 'person_name': 'Тёзка', 'person_slug': None},
    ]
    people = [{'_id': 'ivan', 'slug': 'ivan'}, {'_id': 'one', 'slug': 'one'}, {'_id': 'two', 'slug': 'two'}]

    apply_participant_card_links(modules, rows, people)

    items = modules[0]['data']['items']
    assert items[0]['person_url'] == '/people/ivan'
    assert 'person_url' not in items[1]
    assert 'person_url' not in items[2]
