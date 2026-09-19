"""Участие людей в утверждённых шоу. Источник — локальные страницы, не SQL-дамп.

show_appearances хранит варианты участия с доказательством из контента. Новые люди
не создаются при синхронизации. Неопознанные имена доступны только редактору.
"""
from __future__ import annotations

import hashlib
import html
import re
from collections import defaultdict
from html.parser import HTMLParser

from services.memberships import PersonLookup, name_key
from services.show_teams import team_url

# Точные пути: вложенное шоу не означает включение всего родительского раздела.
TEAM_SHOWS = ('igra', 'zvezdy-ntv', 'ls', 'improv-teams', 'liga-gorodov', 'komandy', 'kontserty', 'superliga')
PERSON_SHOWS = (
    '22-komika', 'medium-quality/outside-stand-up', 'medium-quality/dvij/jam',
    'openmicrophone', 'standup', 'standupwomen', 'leningradskij-stand-up-club',
    'ubojnaya-liga', 'ubojnoj-nochi', 'ubojnyij-vecher', 'comedy-club', 'comedywoman',
    'bitva-za-vremya', 'rassmeshi-komika', 'mezhdu-nami-show', 'miniatures', 'money-mic',
    'iks/istoricheskiy-kviz-stendap', 'ne-spat', 'smeh-bez-pravil',
    'standup-underground', 'stendap-ruletka', 'central-microphone', 'comedy-battle',
)
SHOW_PATHS = TEAM_SHOWS + PERSON_SHOWS
RANK = {'participant': 0, 'finalist': 1, 'winner': 2}
LABELS = {'participant': 'Участник', 'finalist': 'Финалист', 'winner': 'Победитель'}
# Известные варианты имени в исходных таблицах. Значения — slug уже существующей
# страницы; список намеренно короткий и проверяемый, без приблизительного поиска.
PERSON_ALIASES = {'андрей родных': 'andrey-rodnoi'}


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def text(self, separator=' '):
        return separator.join(c.text(separator) if isinstance(c, Node) else c for c in self.children)

    def find(self, *tags):
        for child in self.children:
            if isinstance(child, Node):
                if child.tag in tags:
                    yield child
                yield from child.find(*tags)


class Tree(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
        self.feed(value or '')

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in ('br', 'img', 'hr', 'input', 'meta', 'link', 'wbr'):
            self.current = node
        elif tag == 'br':
            node.children.append('\n')

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def text(value):
    if isinstance(value, Node):
        value = value.text()
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', str(value or '')))).strip()


def clean_name(value):
    value = text(value).replace('*', '').strip(' ,;«»"')
    value = re.sub(r'\s*[–—]\s*.*$', '', value)
    value = re.sub(r'\([^)]*\)', '', value)
    value = re.sub(r'[«"].*?[»"]', '', value)
    return re.sub(r'\s+', ' ', value).strip(' ,;')


def group_info(value, count=0):
    value = text(value)
    match = re.search(r'(дуэт|трио|группа|ансамбль)\s*[«"]([^»"]+)[»"]', value, re.I)
    if match:
        return {'group_kind': {'дуэт': 'duet', 'трио': 'trio'}.get(match[1].lower(), 'group'), 'group_name': match[2]}
    if count > 1:
        return {'group_kind': 'duet' if count == 2 else 'trio' if count == 3 else 'group',
                'group_name': re.sub(r'\s*\(.*', '', value).strip(' «»"')}
    return {'group_kind': '', 'group_name': ''}


def person_tokens(node):
    """Имена только из заранее выбранной ячейки/списка; ссылки сохраняют точный slug."""
    if not isinstance(node, Node):
        node = Tree(str(node)).root
    result, seen = [], set()
    for a in node.find('a'):
        match = re.search(r'(?:^|/)people/([\w-]+)(?:\.html)?/?$', a.attrs.get('href', ''))
        if match:
            name = clean_name(a.text())
            result.append({'person_name': name, 'person_slug': match[1]})
            seen.add(name_key(name))
    # Сохраняем разделители строк и запятые, удаляем уже извлечённые ссылки.
    def remaining(n):
        if isinstance(n, str):
            return n
        if n.tag == 'a' and '/people/' in n.attrs.get('href', ''):
            return '\n'
        return ('\n' if n.tag in ('br', 'p', 'li') else '') + ''.join(remaining(c) for c in n.children)
    for part in re.split(r'[,;\n]+|\s+и\s+', remaining(node)):
        name = clean_name(part)
        if name_key(name) in seen or not re.fullmatch(r'[А-ЯЁA-Z][а-яёa-z-]+(?:\s+[А-ЯЁA-Z][а-яёa-z-]+){1,3}', name):
            continue
        if re.search(r'дуэт|сезон|команда|группа|трио|первый|второй', name, re.I):
            continue
        seen.add(name_key(name))
        result.append({'person_name': name, 'person_slug': None})
    return result


def table_grid(table):
    """Разворачивает rowspan/colspan, чтобы победитель не съехал в колонку наставника."""
    grid, spans = [], {}
    for tr in table.find('tr'):
        row, col = [], 0
        for cell in (n for n in tr.children if isinstance(n, Node) and n.tag in ('td', 'th')):
            while col in spans:
                node, left = spans[col]; row.append(node)
                if left > 1: spans[col] = (node, left - 1)
                else: del spans[col]
                col += 1
            width = min(int(cell.attrs.get('colspan', 1)), 100)
            height = min(int(cell.attrs.get('rowspan', 1)), 1000)
            for _ in range(width):
                row.append(cell)
                if height > 1: spans[col] = (cell, height - 1)
                col += 1
        while col in spans:
            node, left = spans[col]; row.append(node)
            if left > 1: spans[col] = (node, left - 1)
            else: del spans[col]
            col += 1
        grid.append(row)
    return grid


def module_parts(module):
    """Заголовки внутри старого HTML ограничивают область списков участников."""
    data = module.get('data') or {}
    heading = module.get('title') or data.get('title') or ''
    content = data.get('content', '')
    pieces = re.split(r'(<h[1-6]\b[^>]*>.*?</h[1-6]>)', content, flags=re.I | re.S)
    for piece in pieces:
        if re.match(r'<h[1-6]\b', piece, re.I):
            heading = text(piece)
        elif piece.strip():
            yield heading, Tree(piece).root
    if module.get('type') == 'table':
        rows = data.get('rows') or []
        headers = data.get('headers') or []
        values = ([headers] if headers else []) + rows
        markup = '<table>' + ''.join('<tr>' + ''.join('<td>' + str(c) + '</td>' for c in row) + '</tr>' for row in values) + '</table>'
        yield heading, Tree(markup).root


def selected_show(page, roots):
    path = page.get('full_path') or page.get('slug', '')
    matches = [r for r in roots if path == r or path.startswith(r + '/')]
    return roots[max(matches, key=len)] if matches else None


def extract(shows, people, teams, memberships):
    """Чистая функция: варианты участия и отчёт, никаких записей/публикаций."""
    roots = {(s.get('full_path') or s.get('slug')): s for s in shows if (s.get('full_path') or s.get('slug')) in SHOW_PATHS}
    lookup = PersonLookup(people)
    # В тексте ссылок есть сценические имена; принимаем лишь однозначные алиасы
    # уже существующих страниц, не угадываем человека по одной фамилии.
    aliases = defaultdict(set)
    for page in shows + teams:
        for m in page.get('modules', []):
            for a in Tree((m.get('data') or {}).get('content', '')).root.find('a'):
                match = re.search(r'/people/([\w-]+)(?:\.html)?/?$', a.attrs.get('href', ''))
                if match:
                    pid, _ = lookup.resolve(match[1])
                    if pid: aliases[name_key(clean_name(a.text()))].add(pid)
    for key, ids in aliases.items():
        if len(ids) == 1 and key not in lookup.by_key: lookup.by_key[key] = next(iter(ids))
    for alias, slug in PERSON_ALIASES.items():
        person_id, _ = lookup.resolve(slug=slug)
        if person_id: lookup.by_key[alias] = person_id
    rows, groups = [], defaultdict(list)
    collectives = {}
    for person in people:
        info = group_info(person.get('full_name') or person.get('title'))
        if not info['group_name']: continue
        # У старых страниц дуэтов первый абзац биографии описывает состав.
        # Дальнейшие абзацы могут упоминать супругов и коллег.
        for m in person.get('modules', []):
            if (m.get('title') or '').lower() != 'биография': continue
            paragraph = next(Tree((m.get('data') or {}).get('content', '')).root.find('p'), None)
            if paragraph:
                tokens = [t for t in person_tokens(paragraph) if t.get('person_slug') != person.get('slug')]
                if len(tokens) >= 2:
                    collectives[person['_id']] = [(t, info) for t in tokens]
                    groups[name_key(info['group_name'])] = collectives[person['_id']]
            break
    # Явно раскрытые в тексте составы: «дуэт X (Имя Фамилия и Имя Фамилия)».
    # Не пытаемся восстанавливать состав по совпадающим именам/фамилиям.
    for page in shows:
        if not selected_show(page, roots): continue
        for m in page.get('modules', []):
            value = text((m.get('data') or {}).get('content', ''))
            for match in re.finditer(r'((?:дуэт|трио|группа)\s*[«"][^»"]+[»"])\s*\(([^)]+)\)', value, re.I):
                tokens = person_tokens(match[2])
                info = group_info(match[1])
                if len(tokens) > 1:
                    groups[name_key(info['group_name'])] = [(t, info) for t in tokens]
    team_by_id = {t['_id']: t for t in teams}
    team_by_path = {}
    for t in teams:
        path = '/shows/' + str(t.get('full_path')) if t.get('show_id') else '/kvn/teams/' + t.get('slug', '')
        team_by_path[path] = t
    rosters = defaultdict(list)
    for m in memberships: rosters[m['team_id']].append(m)

    def add(root, page, module, token, **extra):
        if not token.get('person_name'): return
        pid, _ = lookup.resolve(token.get('person_slug'), token['person_name'])
        if pid in collectives:
            for member, info in collectives[pid]:
                # Переносим факт участия коллектива на его явно указанных участников.
                add(root, page, module, member, **{**extra, **info})
            return
        row = {'show_id': root['_id'], 'show_path': root.get('full_path') or root['slug'],
               'person_id': pid, 'person_name': token['person_name'], 'person_slug': token.get('person_slug'),
               'achievement': 'participant', 'group_kind': '', 'group_name': '', 'team_id': None,
               'appearances': 0, 'first_episode': None, 'source_page_id': page['_id'],
               'source_path': page.get('full_path') or page.get('slug'), 'source_title': module.get('title') or 'Участники',
               'source': 'local_content', **extra}
        rows.append(row)

    def record(root, page, module, cell, achievement='participant', appearances=0, composition=None, first_episode=None):
        tokens = person_tokens(composition if composition is not None else cell)
        label = text(cell)
        info = group_info(label, len(tokens)) if re.search(r'дуэт|трио|группа|ансамбль', label, re.I) or composition is not None else group_info('')
        if composition is not None and appearances == 0:
            # В сводке есть отобравшиеся из СБП, которые ни разу не выступили в УЛ.
            return
        known = groups.get(name_key(group_info(label)['group_name'] or label))
        if known and composition is None:
            for token, g in known:
                add(root, page, module, token, **g, achievement=achievement, appearances=appearances, first_episode=first_episode)
            return
        if info['group_name'] and len(tokens) > 1:
            groups[name_key(info['group_name'])] = [(t, info) for t in tokens]
        if not tokens:
            # Именованный коллектив может быть раскрыт другим блоком этой же страницы/шоу.
            key = name_key(group_info(label)['group_name'] or label)
            for token, g in groups.get(key, []):
                add(root, page, module, token, **g, achievement=achievement, appearances=appearances, first_episode=first_episode)
        for token in tokens:
            add(root, page, module, token, **info, achievement=achievement, appearances=appearances, first_episode=first_episode)

    # Сначала явно записанные составы из статистики. Они также раскрывают дуэты в таблицах победителей.
    for page in shows:
        root = selected_show(page, roots)
        if not root or root['slug'] != 'ubojnaya-liga': continue
        for m in page.get('modules', []):
            for heading, tree in module_parts(m):
                for table in tree.find('table'):
                    grid = table_grid(table)
                    if not grid: continue
                    headers = [text(c).lower() for c in grid[0]]
                    ci = next((i for i,h in enumerate(headers) if h.startswith('состав')), None)
                    if ci is None or 'участия' not in headers: continue
                    for cells in grid[1:]:
                        if len(cells) <= ci: continue
                        count = text(cells[headers.index('участия')])
                        record(root, page, m, cells[0], appearances=int(count) if count.isdigit() else 0, composition=cells[ci])

    # Первое выступление для разрешения равенства, исключительно по строкам участников.
    first_episodes = {}
    for page in shows:
        if page.get('slug') != 'ubojnaya-liga': continue
        for m in page.get('modules', []):
            if not (m.get('title') or '').startswith('Статистика выпусков:'): continue
            for table in Tree((m.get('data') or {}).get('content', '')).root.find('table'):
                grid = table_grid(table)
                if not grid or len(grid[0]) < 2 or not text(grid[0][1]).isdigit(): continue
                number, started = int(text(grid[0][1])), False
                for cells in grid[1:]:
                    if not cells: continue
                    value = text(cells[0])
                    if value.startswith('Участники'): started = True; continue
                    if started:
                        key = name_key(group_info(value)['group_name'] or clean_name(value))
                        first_episodes[key] = min(number, first_episodes.get(key, number))
    for row in rows:
        key = name_key(row['group_name'] or clean_name(row['person_name']))
        row['first_episode'] = first_episodes.get(key)

    def team_members(root, page, m, team, achievement='participant'):
        for member in rosters[team['_id']]:
            # Авторы/администраторы в составе не становятся выступающими без подтверждения.
            roles = member.get('roles') or []
            if roles and all(re.search('автор|администратор|директор|продюсер', role, re.I) for role in roles): continue
            add(root, page, m, member, team_id=team['_id'], group_kind='team',
                group_name=team.get('name') or team.get('title'), achievement=achievement,
                evidence='Состав команды: ' + (team.get('name') or team.get('title', '')))

    for root in roots.values():
        if root['slug'] not in TEAM_SHOWS: continue
        for team in teams:
            if team.get('show_id') == root['_id']:
                team_members(root, root, {'title': 'Составы команд шоу'}, team)

    participant_heading = re.compile(r'участник|резидент|состав шоу|акт[её]р|комики|финалист|победител|топ.?5|команды .*сезона', re.I)
    excluded_heading = re.compile(r'жюри|наставник|автор|продюсер|ведущ|правила|формат|история|факт', re.I)
    for page in shows:
        root = selected_show(page, roots)
        if not root: continue
        team_mode = root['slug'] in TEAM_SHOWS
        for m in page.get('modules', []):
            data = m.get('data') or {}
            if not team_mode and m.get('type') == 'participants':
                for item in data.get('items') or []:
                    add(root, page, m, {'person_name': item.get('name'), 'person_slug': item.get('person_slug')})
            for heading, tree in module_parts(m):
                for table in tree.find('table'):
                    grid = table_grid(table)
                    if len(grid) < 2: continue
                    final_table = False
                    # Старые таблицы выпусков начинают с номера и жюри. Заголовок
                    # участников ниже, а rowspan дублирует метку в первом столбце.
                    if text(grid[0][0]).lower() == 'выпуск' and len(grid[0]) > 1:
                        episode_label = text(grid[0][1]).lower()
                        final_table = bool(re.search(r'(?<![/\w])финал\b', episode_label)) and root['slug'] == 'smeh-bez-pravil'
                        header_index = next((n for n,r in enumerate(grid) if any(text(c).lower() == 'участник' for c in r)), None)
                        if header_index is not None: grid = grid[header_index:]
                    headers = [text(c).lower() for c in grid[0]]
                    if any(h.startswith('состав') for h in headers) and 'участия' in headers: continue
                    episode_table = any(re.search(r'выпуск|дата|эфир', h) for h in headers)
                    season_table = any(re.search(r'сезон|год', h) for h in headers)
                    for i,h in enumerate(headers):
                        if i and h in headers[:i]: continue
                        if h == 'участники' and 'участник' in headers: continue
                        participant = bool(re.fullmatch(r'участники?|комики?|акт[её]ры?|фио|имя|исполнитель', h))
                        participant |= root['slug'] == 'jam' and bool(re.fullmatch(r'команда [12]', h))
                        achievement = 'participant'
                        if re.fullmatch(r'победител[ьи]|чемпионы?|финалисты?', h):
                            participant = True
                            if season_table and not episode_table:
                                achievement = 'finalist' if h.startswith('финалист') else 'winner'
                        if team_mode:
                            participant = participant or h in ('команда', 'команды')
                        if not participant: continue
                        for cells in grid[1:]:
                            if len(cells) <= i: continue
                            cell = cells[i]
                            if team_mode:
                                for a in cell.find('a'):
                                    team = team_by_path.get(a.attrs.get('href', '').rstrip('/'))
                                    if team: team_members(root, page, m, team, achievement)
                            else:
                                row_achievement = achievement
                                if final_table:
                                    row_achievement = 'winner' if any(text(c).lower() == 'победитель' for c in cells) else 'finalist'
                                record(root, page, m, cell, row_achievement)
                # В финале список порядка выступлений — подтверждённые финалисты.
                # Последующие списки голосов наставников не являются участниками.
                if heading.strip().lower() == 'финал' and root['slug'] == 'openmicrophone':
                    ordered = next(tree.find('ol'), None)
                    if ordered:
                        for li in ordered.find('li'): record(root, page, m, li, 'finalist')
                    continue
                # Явные предложения об участниках выпусков (например, «Это миниатюры»).
                # Ведущие/жюри/авторы и отрицательные формулировки не подходят.
                if not team_mode:
                    for paragraph in tree.find('p'):
                        value = text(paragraph)
                        if re.search(r'(?:участники выпуска:|в выпуске .*выступили|в качестве зв[её]здного дуэта выступили|зв[её]здны[ей] (?:участники|дуэт) выпуска:)', value, re.I) and not re.search(r'не (?:выступили|участвовали)|ведущ|жюри', value, re.I):
                            for token in person_tokens(paragraph):
                                add(root, page, m, token)
                if not participant_heading.search(heading) or excluded_heading.search(heading): continue
                # Таблицы уже разобраны: списки вне них не должны захватывать соседние разделы.
                for li in tree.find('li', 'p'):
                    if team_mode:
                        for a in li.find('a'):
                            team = team_by_path.get(a.attrs.get('href', '').rstrip('/'))
                            if team: team_members(root, page, m, team)
                    else:
                        # В абзаце берём только имя до описания биографии.
                        if li.tag == 'p':
                            leading = re.split(r'\s*[–—]\s*', li.text(), maxsplit=1)[0]
                            if len(leading) > 150: continue
                            record(root, page, m, leading)
                        else:
                            record(root, page, m, li)

    # Стабильный идентификатор не зависит от наличия страницы человека.
    unique = {}
    for row in rows:
        identity = row.get('person_slug') or name_key(row['person_name'])
        key = '|'.join((row['show_id'], identity, row.get('team_id') or '', row['group_kind'], row['group_name'], row['source_page_id']))
        row['_id'] = hashlib.sha256(key.encode()).hexdigest()[:32]
        row['evidence'] = row.get('evidence') or row['person_name'] + (' / ' + row['group_name'] if row['group_name'] else '')
        old = unique.get(row['_id'])
        if old:
            row['achievement'] = max((old['achievement'], row['achievement']), key=RANK.get)
            row['appearances'] = max(old['appearances'], row['appearances'])
        unique[row['_id']] = row
    return list(unique.values()), {'missing_shows': sorted(set(SHOW_PATHS) - set(roots)), 'shows': len(roots)}


def choose(rows):
    """Одна запись на шоу; ручной выбор, частота, первое подтверждённое выступление."""
    by_show = defaultdict(list)
    for row in rows:
        if not row.get('excluded'): by_show[row['show_id']].append(row)
    result = []
    for variants in by_show.values():
        # Сумма отдельных источников не используется: сводка и выпуски могут дублироваться.
        best = min(variants, key=lambda r: (not r.get('preferred', False), -r.get('appearances', 0),
                   r.get('first_episode') if r.get('first_episode') is not None else 10**9,
                   not bool(r.get('group_name')), r['_id']))
        best = dict(best)
        best['achievement'] = max((r['achievement'] for r in variants), key=RANK.get)
        result.append(best)
    return result


def caption(row, show_title):
    result = f'{LABELS[row["achievement"]]} проекта «{show_title}»'
    if row.get('group_name'):
        kind = {'team': 'команды', 'duet': 'дуэта', 'trio': 'трио', 'group': 'группы'}[row['group_kind']]
        result += f' в составе {kind} «{row["group_name"]}»'
    return result


def appearance_url(row, show, team=None):
    """Командное участие ведёт на команду, индивидуальное — на основной проект."""
    if row.get('team_id') and team:
        return team_url(team)
    return '/shows/' + (show.get('full_path') or show['slug'])


async def sync(db, apply=False):
    shows = await db.shows.find({}).to_list(None)
    people = await db.people.find({}, {'title': 1, 'full_name': 1, 'slug': 1, 'old_urls': 1, 'modules': 1}).to_list(None)
    teams = await db.teams.find({}).to_list(None)
    memberships = await db.memberships.find({}).to_list(None)
    rows, report = extract(shows, people, teams, memberships)
    report.update(variants=len(rows), linked=sum(bool(r['person_id']) for r in rows), unresolved=sum(not r['person_id'] for r in rows))
    report['linked_people'] = len({r['person_id'] for r in rows if r['person_id']})
    report['unresolved_candidates'] = len({(r['show_id'], name_key(r['person_name'])) for r in rows if not r['person_id']})
    report['by_show'] = {path: {'linked': sum(bool(r['person_id']) for r in rows if r['show_path'] == path),
                              'unresolved': sum(not r['person_id'] for r in rows if r['show_path'] == path)} for path in SHOW_PATHS}
    if apply:
        from pymongo import UpdateOne
        await db.show_appearances.create_index([('person_id', 1), ('show_id', 1)])
        await db.show_appearances.create_index('show_id')
        existing = {r['_id']: r for r in await db.show_appearances.find({}).to_list(None)}
        operations = []
        for row in rows:
            old = existing.get(row['_id'])
            if old:
                for field in ('preferred', 'excluded', 'manual_person_id', 'manual_achievement', 'manual_group_name', 'manual_group_kind'):
                    if field in old: row[field] = old[field]
                if 'manual_person_id' in old: row['person_id'] = old['manual_person_id']
            operations.append(UpdateOne({'_id': row['_id']}, {'$set': row}, upsert=True))
        if operations: await db.show_appearances.bulk_write(operations, ordered=False)
        await db.show_appearances.delete_many({'source': 'local_content', '_id': {'$nin': [r['_id'] for r in rows]}})
        from services.cache import cache_service
        await cache_service.invalidate_everywhere(db)
        public = await public_rows(db)
        report['public_links'] = len(public)
        report['public_people'] = len({row['person_id'] for row in public})
    return report


async def ensure_show_appearances(db):
    """Первично построить связи на новой/восстановленной базе, не трогая заполненную коллекцию."""
    if await db.show_appearances.find_one({}, {'_id': 1}):
        return None
    return await sync(db, apply=True)


async def create_show_appearance_indexes(ensure_index, db):
    await ensure_index(db.show_appearances, [('person_id', 1), ('show_id', 1)])
    await ensure_index(db.show_appearances, 'show_id')


def manual_values(row):
    row = dict(row)
    for field in ('achievement', 'group_name', 'group_kind'):
        if 'manual_' + field in row: row[field] = row['manual_' + field]
    return row


async def public_rows(db, *, person_id=None, person_ids=None, show_id=None, include_show_id=False):
    query = {'excluded': {'$ne': True}, 'person_id': {'$ne': None}}
    if person_id: query['person_id'] = person_id
    elif person_ids is not None:
        person_ids = list(dict.fromkeys(person_ids))
        if not person_ids:
            return []
        query['person_id'] = {'$in': person_ids}
    if show_id: query['show_id'] = show_id
    rows = [manual_values(r) for r in await db.show_appearances.find(query).to_list(None)]
    available = {'status': {'$ne': 'archived'}}
    people = {p['_id']: p for p in await db.people.find({'_id': {'$in': [r['person_id'] for r in rows]}, **available}, {'title': 1, 'full_name': 1, 'slug': 1}).to_list(None)}
    shows = {s['_id']: s for s in await db.shows.find({'_id': {'$in': [r['show_id'] for r in rows]}, **available}, {'title': 1, 'full_path': 1, 'slug': 1}).to_list(None)}
    sources = {s['_id'] for s in await db.shows.find({'_id': {'$in': [r['source_page_id'] for r in rows]}, **available}, {'_id': 1}).to_list(None)}
    teams = {t['_id']: t for t in await db.teams.find(
        {'_id': {'$in': [r.get('team_id') for r in rows]}, **available},
        {'slug': 1, 'show_id': 1, 'full_path': 1},
    ).to_list(None)}
    by_person = defaultdict(list)
    for row in rows:
        if (row['person_id'] in people and row['show_id'] in shows and row['source_page_id'] in sources
                and (not row.get('team_id') or row['team_id'] in teams)):
            by_person[row['person_id']].append(row)
    result = []
    for pid, variants in by_person.items():
        for row in choose(variants):
            show, person = shows[row['show_id']], people[pid]
            show_url = '/shows/' + (show.get('full_path') or show['slug'])
            item = {'id': row['_id'], 'person_id': pid,
                    'person_name': person.get('full_name') or person['title'],
                    'person_url': '/people/' + person['slug'], 'show_title': show['title'],
                    'show_url': show_url, 'link_url': appearance_url(row, show, teams.get(row.get('team_id'))),
                    'caption': caption(row, show['title'])}
            if include_show_id:
                item['show_id'] = row['show_id']
            result.append(item)
    return sorted(result, key=lambda r: (r['show_title'], r['person_name']))


async def public_team_projects(db, team_id):
    """Проекты участников команды КВН без дублирования шоу и людей."""
    memberships = await db.memberships.find(
        {'team_id': team_id, 'person_id': {'$ne': None}}, {'person_id': 1},
    ).to_list(None)
    person_ids = sorted({row['person_id'] for row in memberships if row.get('person_id')})
    rows = await public_rows(db, person_ids=person_ids, include_show_id=True)

    projects = {}
    for row in rows:
        project = projects.setdefault(row['show_id'], {
            'show_id': row['show_id'],
            'show_title': row['show_title'],
            'show_url': row['show_url'],
            'members': {},
        })
        project['members'][row['person_id']] = {
            'person_id': row['person_id'],
            'person_name': row['person_name'],
            'person_url': row['person_url'],
            'caption': row['caption'],
            'appearance_url': row['link_url'],
        }

    result = []
    for project in projects.values():
        project['members'] = sorted(
            project['members'].values(),
            key=lambda member: (member['person_name'].casefold(), member['person_id']),
        )
        result.append(project)
    return sorted(result, key=lambda project: (project['show_title'].casefold(), project['show_id']))


def apply_participant_card_links(modules, rows, people):
    """Добавить проверенные URL в существующие карточки участников, не меняя данные страницы."""
    people_by_id = {person['_id']: person for person in people}
    by_slug = defaultdict(set)
    by_name = defaultdict(set)
    for person in people:
        if person.get('slug'):
            by_slug[person['slug'].lower()].add('/people/' + person['slug'])
    for row in rows:
        person = people_by_id.get(row.get('person_id'))
        if not person or not person.get('slug'):
            continue
        url = '/people/' + person['slug']
        if row.get('person_slug'):
            by_slug[row['person_slug'].lower()].add(url)
        by_name[name_key(row.get('person_name') or '')].add(url)

    for module in modules or []:
        if module.get('type') != 'participants':
            continue
        for item in (module.get('data') or {}).get('items') or []:
            urls = by_slug.get((item.get('person_slug') or '').lower(), set())
            if not urls:
                urls = by_name.get(name_key(item.get('name') or ''), set())
            if len(urls) == 1:
                item['person_url'] = next(iter(urls))
            else:
                item.pop('person_url', None)
    return modules


async def link_participant_cards(db, show):
    """Связать карточки только на страницах, попавших в согласованную синхронизацию."""
    modules = show.get('modules') or []
    if not any(m.get('type') == 'participants' for m in modules):
        return show
    rows = await db.show_appearances.find({
        'source_page_id': show['_id'], 'person_id': {'$ne': None}, 'excluded': {'$ne': True},
    }).to_list(None)
    if not rows:
        return show
    people = await db.people.find({
        '_id': {'$in': list({row['person_id'] for row in rows})}, 'status': {'$ne': 'archived'},
    }, {'slug': 1}).to_list(None)
    apply_participant_card_links(modules, rows, people)
    return show


async def link_new_person(db, person):
    """Связывает ожидающие записи после ручного создания/публикации человека."""
    people = await db.people.find({}, {'title': 1, 'full_name': 1, 'slug': 1, 'old_urls': 1}).to_list(None)
    lookup = PersonLookup(people)
    async for row in db.show_appearances.find({'person_id': None}):
        pid, _ = lookup.resolve(row.get('person_slug'), row['person_name'])
        if pid == person['_id']:
            await db.show_appearances.update_one({'_id': row['_id']}, {'$set': {'person_id': pid}})
