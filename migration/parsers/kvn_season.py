#!/usr/bin/env python3
"""
Парсер для сезонов КВН.

Модуль парсит HTML-контент страницы сезона КВН и извлекает структурированную информацию:
- Стадии сезона (1/8, 1/4, 1/2, финал)
- Игры внутри каждой стадии
- Команды-участники
- Результаты (баллы по конкурсам)
- Жюри и ведущих
- Даты игр
- Прошедшие/выбывшие команды

Архитектура:
-----------
KVNSeasonParser - главный класс, который парсит всю страницу сезона
    ├── parse_stages() - парсит все стадии сезона
    │   └── StageParser - парсит одну стадию (1/8, 1/4, и т.д.)
    │       └── GameParser - парсит одну игру
    │           ├── parse_table() - парсит таблицу результатов
    │           ├── parse_teams() - извлекает команды
    │           └── parse_jury() - извлекает жюри
    └── parse_metadata() - парсит общую информацию сезона

Как добавить новый паттерн парсинга:
-----------------------------------
1. Для новых форматов стадий - добавить паттерн в STAGE_PATTERNS
2. Для новых форматов игр - добавить паттерн в GAME_PATTERNS
3. Для новых форматов дат - добавить в DATE_PATTERNS
4. Для новых форматов таблиц - расширить TableParser.parse()
5. Для особых случаев - добавить обработчик в _parse_special_cases()

Пример использования:
--------------------
```python
from parsers.kvn_season import KVNSeasonParser

parser = KVNSeasonParser()
html = "<div>...</div>"  # HTML контент сезона

result = parser.parse(html, league="premier-liga", year=2023)
# result = {
#     'league': 'premier-liga',
#     'year': 2023,
#     'teams': [...],
#     'stages': [
#         {
#             'name': '1/8 финала',
#             'order': 1,
#             'games': [
#                 {
#                     'name': 'Первая 1/8 финала',
#                     'date': '2023-03-27',
#                     'teams': [...],
#                     'scores': {...},
#                     'jury': [...],
#                     'passed': [...],
#                 }
#             ]
#         }
#     ]
# }
```
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from html import unescape


# ==============================================================================
# ПАТТЕРНЫ ДЛЯ ПАРСИНГА
# ==============================================================================

# Паттерны для определения стадий сезона
# ВАЖНО: порядок имеет значение! Более специфичные паттерны должны быть первыми
STAGE_PATTERNS = [
    # Стандартные стадии (более специфичные сначала)
    (r'\b1/8\s*финал[аеы]?\b', '1/8 финала', 1),
    (r'\bодна\s+восьм[аяо]я\s+финал[аеы]?\b', '1/8 финала', 1),
    (r'\bРезультаты\s+1/8\s*финал', '1/8 финала', 1),
    (r'\b1/4\s*финал[аеы]?\b', '1/4 финала', 2),
    (r'\bчетверть\s*финал[аеы]?\b', '1/4 финала', 2),
    (r'\bРезультаты\s+1/4\s*финал', '1/4 финала', 2),
    (r'\b1/2\s*финал[аеы]?\b', '1/2 финала', 3),
    (r'\bполу\s*финал[аеы]?\b', '1/2 финала', 3),
    (r'\bРезультаты\s+1/2\s*финал', '1/2 финала', 3),
    # Финал должен быть последним и не совпадать с дробными
    (r'(?<!/)\bфинал[аеы]?\b(?!\s*\d)', 'Финал', 4),
    # Альтернативные названия
    (r'\bКубок мэра\b', 'Кубок мэра', 5),
    (r'\bГолосящий КиВиН\b', 'Голосящий КиВиН', 6),
]

# Паттерны для определения игр внутри стадии
GAME_PATTERNS = [
    # "Первая 1/8 финала (дата)" или "Первая игра"
    (r'(Перв(?:ая|ый|ое))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 1),
    (r'(Втор(?:ая|ой|ое))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 2),
    (r'(Треть(?:я|ий|е))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 3),
    (r'(Четверт(?:ая|ый|ое))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 4),
    (r'(Пят(?:ая|ый|ое))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 5),
    (r'(Шест(?:ая|ой|ое))\s*(?:игра\s+)?', 6),
    # Просто "Игра 1", "Игра 2"
    (r'[Ии]гра\s*(\d+)', None),
]

# Паттерны для дат
DATE_PATTERNS = [
    # "27 марта 2023"
    r'(\d{1,2})\s*(январ[яьи]|феврал[яьи]|март[ае]?|апрел[яьи]|ма[яй]|июн[яьи]|июл[яьи]|август[ае]?|сентябр[яьи]|октябр[яьи]|ноябр[яьи]|декабр[яьи])\s*(\d{4})?',
    # "27.03.2023"
    r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
    # "27/03/2023"
    r'(\d{1,2})/(\d{1,2})/(\d{4})',
]

# Маппинг месяцев на номера
MONTH_MAP = {
    'январ': 1, 'феврал': 2, 'март': 3, 'апрел': 4, 'ма': 5, 'май': 5,
    'июн': 6, 'июл': 7, 'август': 8, 'сентябр': 9, 'октябр': 10,
    'ноябр': 11, 'декабр': 12
}

# Паттерны для результатов (прошли/не прошли)
RESULT_PATTERNS = [
    (r'прош[её]?л[иа]?\s*(?:в|на|дальше)?', 'passed'),
    (r'выш[её]?л[иа]?\s*(?:в|на|дальше)?', 'passed'),
    (r'не\s*прош[её]?л[иа]?', 'eliminated'),
    (r'выбы[лв][иа]?', 'eliminated'),
    (r'победител[ьяи]', 'winner'),
    (r'чемпион[ыа]?', 'winner'),
]


# ==============================================================================
# МОДЕЛИ ДАННЫХ
# ==============================================================================

@dataclass
class TeamScore:
    """Результаты команды в игре."""
    team_slug: str = ""       # Slug команды
    team_name: str = ""       # Название команды (для отображения)
    team_link: str = ""       # Ссылка на страницу команды
    place: int = 0            # Место в игре
    scores: Dict[str, float] = field(default_factory=dict)  # Баллы по конкурсам
    total: float = 0.0        # Итоговый балл
    passed: bool = False      # Прошла ли в следующий этап
    is_winner: bool = False   # Победитель (только для финала)
    city: str = ""            # Город команды


@dataclass
class Game:
    """Одна игра сезона."""
    id: str = ""              # Уникальный ID игры (league-year-stage-game)
    name: str = ""            # Название игры ("Первая 1/8 финала")
    order: int = 0            # Порядковый номер игры в стадии
    date: str = ""            # Дата игры (ISO формат)
    date_raw: str = ""        # Оригинальная дата из HTML
    
    teams: List[TeamScore] = field(default_factory=list)  # Команды и их результаты
    contests: List[str] = field(default_factory=list)     # Названия конкурсов
    
    jury: List[str] = field(default_factory=list)         # ФИО членов жюри
    host: str = ""                                         # Ведущий игры
    
    notes: str = ""           # Дополнительная информация (добор, снятие и т.д.)
    is_cancelled: bool = False  # Игра отменена (например, из-за COVID)


@dataclass
class Stage:
    """Стадия сезона (1/8, 1/4, и т.д.)."""
    name: str = ""            # Название стадии
    order: int = 0            # Порядок стадии (1/8=1, 1/4=2, 1/2=3, финал=4)
    games: List[Game] = field(default_factory=list)
    
    # Добор после стадии
    additional_teams: List[str] = field(default_factory=list)  # Команды, прошедшие добором
    additional_notes: str = ""  # Комментарий к добору
    
    # Общая информация по стадии
    notes: str = ""           # Дополнительные заметки


@dataclass
class SeasonData:
    """Полная информация о сезоне КВН."""
    league_slug: str = ""     # Slug лиги
    league_name: str = ""     # Название лиги
    year: int = 0             # Год сезона
    season_number: int = 0    # Номер сезона (если есть)
    
    # Все команды-участники сезона
    all_teams: List[str] = field(default_factory=list)  # Список slug команд
    
    # Стадии сезона
    stages: List[Stage] = field(default_factory=list)
    
    # Победители
    winners: List[str] = field(default_factory=list)  # Slug команд-победителей
    
    # Жюри сезона (общий список)
    jury: List[str] = field(default_factory=list)
    
    # Редакторы сезона
    editors: List[str] = field(default_factory=list)
    
    # Ведущий сезона
    host: str = ""
    
    # Общий текст/описание (не структурированная информация)
    description: str = ""
    
    # Ссылки на соседние сезоны
    prev_season: str = ""
    next_season: str = ""


# ==============================================================================
# ПАРСЕРЫ
# ==============================================================================

class TableParser:
    """Парсер HTML-таблиц с результатами игр."""
    
    def parse(self, table_html: str) -> Tuple[List[str], List[TeamScore]]:
        """
        Парсит HTML-таблицу с результатами.
        
        Args:
            table_html: HTML код таблицы
            
        Returns:
            (список названий конкурсов, список результатов команд)
        """
        soup = BeautifulSoup(table_html, 'html.parser')
        table = soup.find('table') if soup.name != 'table' else soup
        
        if not table:
            return [], []
        
        rows = table.find_all('tr')
        if not rows:
            return [], []
        
        # Первая строка - заголовки (конкурсы)
        header_row = rows[0]
        headers = [self._clean_text(th.get_text()) for th in header_row.find_all(['td', 'th'])]
        
        # Определяем колонки
        contests = []
        team_col = -1
        place_col = -1
        total_col = -1
        
        for i, h in enumerate(headers):
            h_lower = h.lower()
            if h_lower in ('команда', 'команды', 'team'):
                team_col = i
            elif h_lower in ('м', 'место', 'place', '#'):
                place_col = i
            elif h_lower in ('итого', 'сумма', 'total', 'всего'):
                total_col = i
            elif h and h_lower not in ('м', 'место', 'place', '#'):
                contests.append(h)
        
        # Корректируем если место в первой колонке
        if team_col == -1 and len(headers) > 1:
            team_col = 1 if place_col == 0 else 0
        
        # Парсим строки с командами
        teams = []
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            
            team_score = TeamScore()
            
            # Место
            if place_col >= 0 and place_col < len(cells):
                place_text = self._clean_text(cells[place_col].get_text())
                try:
                    team_score.place = int(place_text)
                except:
                    pass
            
            # Команда
            if team_col >= 0 and team_col < len(cells):
                team_cell = cells[team_col]
                team_score.team_name = self._clean_text(team_cell.get_text())
                
                # Ищем ссылку на команду
                link = team_cell.find('a')
                if link:
                    href = link.get('href', '')
                    team_score.team_link = href
                    # Извлекаем slug из ссылки
                    if 'kvn/teams/' in href:
                        team_score.team_slug = href.split('kvn/teams/')[-1].replace('.html', '').strip('/')
                
                # Проверяем выделение жирным (прошедшие команды)
                if team_cell.find('strong') or team_cell.find('b'):
                    team_score.passed = True
            
            # Баллы по конкурсам
            score_cols = [i for i in range(len(cells)) if i not in (place_col, team_col, total_col)]
            for i, col_idx in enumerate(score_cols):
                if col_idx < len(cells) and i < len(contests):
                    score_text = self._clean_text(cells[col_idx].get_text())
                    try:
                        score = float(score_text.replace(',', '.'))
                        team_score.scores[contests[i]] = score
                    except:
                        pass
            
            # Итого
            if total_col >= 0 and total_col < len(cells):
                total_text = self._clean_text(cells[total_col].get_text())
                try:
                    team_score.total = float(total_text.replace(',', '.'))
                except:
                    pass
            else:
                # Считаем сумму сами
                team_score.total = sum(team_score.scores.values())
            
            if team_score.team_name:
                teams.append(team_score)
        
        # Определяем места если не были указаны
        if teams and all(t.place == 0 for t in teams):
            sorted_teams = sorted(teams, key=lambda t: t.total, reverse=True)
            for i, team in enumerate(sorted_teams):
                team.place = i + 1
        
        return contests, teams
    
    def _clean_text(self, text: str) -> str:
        """Очищает текст от лишних пробелов."""
        return ' '.join(text.split()).strip()


class GameParser:
    """Парсер отдельной игры."""
    
    def __init__(self, default_year: int = None):
        self.table_parser = TableParser()
        self.default_year = default_year or datetime.now().year
    
    def parse(self, html_section: str, stage_name: str, game_order: int) -> Optional[Game]:
        """
        Парсит секцию HTML с информацией об одной игре.
        
        Args:
            html_section: HTML секция с игрой
            stage_name: Название стадии
            game_order: Порядковый номер игры
            
        Returns:
            Объект Game или None
        """
        soup = BeautifulSoup(html_section, 'html.parser')
        game = Game(order=game_order)
        
        # Пробуем найти название и дату игры
        game_name, date_raw = self._find_game_header(html_section, stage_name, game_order)
        game.name = game_name
        game.date_raw = date_raw
        game.date = self._parse_date(date_raw) if date_raw else ""
        
        # Парсим таблицу результатов
        table = soup.find('table')
        if table:
            contests, teams = self.table_parser.parse(str(table))
            game.contests = contests
            game.teams = teams
        else:
            # Нет таблицы - ищем результаты в тексте
            game.teams = self._parse_text_results(html_section)
        
        # Ищем жюри
        game.jury = self._find_jury(html_section)
        
        # Ищем ведущего
        game.host = self._find_host(html_section)
        
        # Определяем прошедшие команды если не определено
        self._detect_passed_teams(game, html_section)
        
        # Парсим дату с годом по умолчанию
        if game.date_raw and not game.date:
            game.date = self._parse_date(game.date_raw, self.default_year)
        
        return game
    
    def _find_game_header(self, html: str, stage_name: str, game_order: int) -> Tuple[str, str]:
        """Находит заголовок игры и дату."""
        # Паттерны для поиска заголовка игры
        ordinals = {
            1: 'Первая', 2: 'Вторая', 3: 'Третья',
            4: 'Четвёртая', 5: 'Пятая', 6: 'Шестая'
        }
        
        ordinal = ordinals.get(game_order, f'{game_order}-я')
        
        # Ищем паттерн "Первая 1/8 финала (дата)" или похожий
        for pattern, order in GAME_PATTERNS:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                groups = match.groups()
                name_parts = [g for g in groups[:2] if g]
                name = ' '.join(name_parts) if name_parts else f"{ordinal} игра"
                date = groups[-1] if len(groups) > 2 and groups[-1] else ""
                return name, date
        
        # Ищем отдельно дату
        date = ""
        for pattern in DATE_PATTERNS:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date = ' '.join(g for g in match.groups() if g)
                break
        
        return f"{ordinal} {stage_name}", date
    
    def _parse_date(self, date_str: str, default_year: int = None) -> str:
        """Парсит дату в ISO формат."""
        if not date_str:
            return ""
        
        year_to_use = default_year or self.default_year
        
        # "27 марта 2023"
        match = re.search(DATE_PATTERNS[0], date_str, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            month_str = match.group(2).lower()
            year = int(match.group(3)) if match.group(3) else year_to_use
            
            # Находим номер месяца
            month = 1
            for key, val in MONTH_MAP.items():
                if month_str.startswith(key):
                    month = val
                    break
            
            try:
                return datetime(year, month, day).strftime('%Y-%m-%d')
            except:
                pass
        
        # "27.03.2023"
        match = re.search(DATE_PATTERNS[1], date_str)
        if match:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                return datetime(year, month, day).strftime('%Y-%m-%d')
            except:
                pass
        
        return ""
    
    def _parse_text_results(self, html: str) -> List[TeamScore]:
        """Парсит результаты из текста (когда нет таблицы)."""
        teams = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем ссылки на команды
        links = soup.find_all('a', href=re.compile(r'kvn/teams/'))
        for link in links:
            team = TeamScore()
            team.team_name = link.get_text(strip=True)
            href = link.get('href', '')
            team.team_link = href
            team.team_slug = href.split('kvn/teams/')[-1].replace('.html', '').strip('/') if 'kvn/teams/' in href else ''
            
            # Ищем балл рядом с названием
            parent = link.parent
            if parent:
                text = parent.get_text()
                score_match = re.search(r'(\d+[.,]\d+)', text)
                if score_match:
                    try:
                        team.total = float(score_match.group(1).replace(',', '.'))
                    except:
                        pass
            
            # Проверяем выделение
            if link.find_parent(['strong', 'b']) or link.find(['strong', 'b']):
                team.passed = True
            
            teams.append(team)
        
        # Сортируем по баллам
        teams.sort(key=lambda t: t.total, reverse=True)
        for i, team in enumerate(teams):
            team.place = i + 1
        
        return teams
    
    def _find_jury(self, html: str) -> List[str]:
        """Находит список жюри."""
        jury = []
        
        # Ищем "Жюри:" и извлекаем имена
        match = re.search(r'[Жж]юри:?\s*([^<]+)', html)
        if match:
            jury_text = match.group(1)
            # Разделяем по запятым
            names = re.split(r'[,;]', jury_text)
            jury = [name.strip() for name in names if name.strip()]
        
        # Также ищем ссылки на людей после слова "жюри"
        soup = BeautifulSoup(html, 'html.parser')
        jury_section = soup.find(string=re.compile(r'[Жж]юри', re.IGNORECASE))
        if jury_section:
            parent = jury_section.find_parent()
            if parent:
                links = parent.find_all('a', href=re.compile(r'people/'))
                for link in links:
                    name = link.get_text(strip=True)
                    if name and name not in jury:
                        jury.append(name)
        
        return jury
    
    def _find_host(self, html: str) -> str:
        """Находит ведущего игры."""
        match = re.search(r'[Вв]едущ(?:ий|ая|ие):?\s*([^<,;]+)', html)
        if match:
            return match.group(1).strip()
        return ""
    
    def _detect_passed_teams(self, game: Game, html: str) -> None:
        """Определяет прошедшие команды по контексту."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем секции "прошли" / "не прошли"
        for pattern, result_type in RESULT_PATTERNS:
            match = soup.find(string=re.compile(pattern, re.IGNORECASE))
            if match:
                # Ищем команды рядом с этой секцией
                parent = match.find_parent()
                if parent:
                    links = parent.find_all('a', href=re.compile(r'kvn/teams/'))
                    for link in links:
                        slug = link.get('href', '').split('kvn/teams/')[-1].replace('.html', '').strip('/') if 'kvn/teams/' in link.get('href', '') else ''
                        for team in game.teams:
                            if team.team_slug == slug or team.team_name == link.get_text(strip=True):
                                if result_type == 'passed':
                                    team.passed = True
                                elif result_type == 'winner':
                                    team.passed = True
                                    team.is_winner = True
                                elif result_type == 'eliminated':
                                    team.passed = False
        
        # Если выделены жирным - прошли
        for strong in soup.find_all(['strong', 'b']):
            name = strong.get_text(strip=True)
            for team in game.teams:
                if team.team_name and name and (team.team_name in name or name in team.team_name):
                    team.passed = True


class StageParser:
    """Парсер стадии сезона (1/8, 1/4, и т.д.)."""
    
    def __init__(self, default_year: int = None):
        self.default_year = default_year
        self.game_parser = GameParser(default_year=default_year)
    
    def parse(self, html_section: str, stage_name: str, stage_order: int) -> Stage:
        """
        Парсит секцию HTML со стадией.
        
        Args:
            html_section: HTML секция со стадией
            stage_name: Название стадии
            stage_order: Порядок стадии
            
        Returns:
            Объект Stage
        """
        stage = Stage(name=stage_name, order=stage_order)
        
        # Разбиваем на игры
        game_sections = self._split_into_games(html_section)
        
        for i, game_html in enumerate(game_sections, 1):
            game = self.game_parser.parse(game_html, stage_name, i)
            if game and (game.teams or game.notes):
                game.id = f"{stage_name.lower().replace(' ', '-').replace('/', '-')}-{i}"
                stage.games.append(game)
        
        # Ищем информацию о доборе
        stage.additional_teams, stage.additional_notes = self._find_additional(html_section)
        
        return stage
    
    def _split_into_games(self, html: str) -> List[str]:
        """Разбивает секцию стадии на отдельные игры."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем заголовки игр
        game_headers = []
        for pattern, order in GAME_PATTERNS:
            for element in soup.find_all(['strong', 'b', 'h4', 'h3', 'div', 'p']):
                if re.search(pattern, element.get_text(), re.IGNORECASE):
                    game_headers.append((element, order if order else len(game_headers) + 1))
        
        if not game_headers:
            # Если нет явных заголовков игр - вся секция это одна игра
            return [html]
        
        # Сортируем по порядку в документе
        game_headers.sort(key=lambda x: str(soup).find(str(x[0])))
        
        # Разбиваем HTML по заголовкам
        sections = []
        html_str = str(soup)
        
        for i, (header, _) in enumerate(game_headers):
            start = html_str.find(str(header))
            if i < len(game_headers) - 1:
                end = html_str.find(str(game_headers[i + 1][0]))
            else:
                end = len(html_str)
            
            if start >= 0:
                sections.append(html_str[start:end])
        
        return sections if sections else [html]
    
    def _find_additional(self, html: str) -> Tuple[List[str], str]:
        """Находит информацию о доборе."""
        teams = []
        notes = ""
        
        # Ищем "добор" или "дополнительно прошли"
        match = re.search(r'[Дд]обор[а]?:?\s*([^<]+)', html)
        if match:
            notes = match.group(1).strip()
        
        # Ищем команды в секции добора
        soup = BeautifulSoup(html, 'html.parser')
        additional_section = soup.find(string=re.compile(r'[Дд]обор', re.IGNORECASE))
        if additional_section:
            parent = additional_section.find_parent()
            if parent:
                links = parent.find_all('a', href=re.compile(r'kvn/teams/'))
                for link in links:
                    slug = link.get('href', '').split('kvn/teams/')[-1].replace('.html', '').strip('/')
                    if slug:
                        teams.append(slug)
        
        return teams, notes


class KVNSeasonParser:
    """
    Главный парсер сезонов КВН.
    
    Использование:
    ```python
    parser = KVNSeasonParser()
    result = parser.parse(html_content, league="premier-liga", year=2023)
    ```
    """
    
    def __init__(self):
        self.stage_parser = None  # Инициализируется в parse() с годом сезона
    
    def parse(self, html: str, league: str = "", year: int = 0) -> SeasonData:
        """
        Парсит полный HTML контент страницы сезона.
        
        Args:
            html: HTML контент страницы
            league: Slug лиги
            year: Год сезона
            
        Returns:
            SeasonData с полной информацией о сезоне
        """
        season = SeasonData(league_slug=league, year=year)
        
        # Инициализируем stage_parser с годом сезона
        self.stage_parser = StageParser(default_year=year)
        
        # Парсим метаданные
        self._parse_metadata(html, season)
        
        # Находим и парсим стадии
        stages = self._split_into_stages(html)
        for stage_name, stage_order, stage_html in stages:
            stage = self.stage_parser.parse(stage_html, stage_name, stage_order)
            if stage.games or stage.notes:
                season.stages.append(stage)
        
        # Собираем всех команд
        season.all_teams = self._collect_all_teams(season)
        
        # Определяем победителей
        season.winners = self._find_winners(season)
        
        # Собираем жюри
        season.jury = self._collect_jury(html, season)
        
        # Ссылки на соседние сезоны
        season.prev_season, season.next_season = self._find_adjacent_seasons(html)
        
        return season
    
    def _parse_metadata(self, html: str, season: SeasonData) -> None:
        """Парсит общую информацию о сезоне."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем редакторов
        match = re.search(r'[Рр]едактор[ыа]?:?\s*([^<]+)', html)
        if match:
            editors_text = match.group(1)
            editors = re.split(r'[,;]', editors_text)
            season.editors = [e.strip() for e in editors if e.strip()]
        
        # Ищем ведущего
        match = re.search(r'[Вв]едущ(?:ий|ая|ие)\s*(?:сезона)?:?\s*([^<,;]+)', html)
        if match:
            season.host = match.group(1).strip()
    
    def _split_into_stages(self, html: str) -> List[Tuple[str, int, str]]:
        """
        Разбивает HTML на стадии сезона.
        
        Returns:
            Список кортежей (название стадии, порядок, HTML секция)
        """
        soup = BeautifulSoup(html, 'html.parser')
        stages = []
        
        # Находим заголовки стадий
        stage_headers = []
        found_positions = {}  # Для дедупликации по позиции
        
        for element in soup.find_all(['h2', 'h3', 'h4']):
            text = element.get_text()
            
            # Пропускаем если это заголовок игры (содержит "Первая", "Вторая" итд)
            if re.search(r'(перв|втор|трет|четвёрт|пят|шест)[аяыойое]+\s', text, re.IGNORECASE):
                continue
            
            # Проверяем каждый паттерн стадии
            for pattern, name, order in STAGE_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    # Проверяем, не добавили ли уже этот элемент или стадию с таким именем
                    elem_str = str(element)
                    if elem_str not in found_positions:
                        # Проверяем, нет ли уже этой стадии
                        existing_names = [h[1] for h in stage_headers]
                        if name not in existing_names:
                            stage_headers.append((element, name, order))
                            found_positions[elem_str] = True
                    break
        
        if not stage_headers:
            # Если нет явных стадий - возвращаем весь HTML как одну стадию
            return [("Основная игра", 1, html)]
        
        # Сортируем по порядку в документе
        html_str = str(soup)
        stage_headers.sort(key=lambda x: html_str.find(str(x[0])))
        
        # Разбиваем HTML по стадиям
        for i, (header, name, order) in enumerate(stage_headers):
            start = html_str.find(str(header))
            if i < len(stage_headers) - 1:
                end = html_str.find(str(stage_headers[i + 1][0]))
            else:
                end = len(html_str)
            
            if start >= 0:
                stages.append((name, order, html_str[start:end]))
        
        return stages
    
    def _collect_all_teams(self, season: SeasonData) -> List[str]:
        """Собирает список всех команд сезона."""
        teams = set()
        for stage in season.stages:
            for game in stage.games:
                for team in game.teams:
                    if team.team_slug:
                        teams.add(team.team_slug)
            for team_slug in stage.additional_teams:
                teams.add(team_slug)
        return list(teams)
    
    def _find_winners(self, season: SeasonData) -> List[str]:
        """Находит победителей сезона."""
        winners = []
        
        # Ищем в финале
        finals = [s for s in season.stages if s.order == 4 or 'финал' in s.name.lower()]
        for final in finals:
            for game in final.games:
                for team in game.teams:
                    if team.is_winner or (team.place == 1 and team.passed):
                        if team.team_slug:
                            winners.append(team.team_slug)
        
        return winners
    
    def _collect_jury(self, html: str, season: SeasonData) -> List[str]:
        """Собирает список членов жюри сезона."""
        jury = set()
        
        # Из игр
        for stage in season.stages:
            for game in stage.games:
                for member in game.jury:
                    jury.add(member)
        
        # Из общей секции "Жюри"
        soup = BeautifulSoup(html, 'html.parser')
        jury_section = soup.find(['h3', 'h4', 'strong'], string=re.compile(r'[Жж]юри', re.IGNORECASE))
        if jury_section:
            # Ищем следующие элементы со ссылками на людей
            next_elements = jury_section.find_next_siblings()[:10]
            for elem in next_elements:
                links = elem.find_all('a', href=re.compile(r'people/'))
                for link in links:
                    jury.add(link.get_text(strip=True))
        
        return list(jury)
    
    def _find_adjacent_seasons(self, html: str) -> Tuple[str, str]:
        """Находит ссылки на соседние сезоны."""
        prev_season = ""
        next_season = ""
        
        # Ищем паттерны типа "< сезон 2022" и "сезон 2024 >"
        prev_match = re.search(r'<\s*сезон\s*(\d{4})', html, re.IGNORECASE)
        if prev_match:
            prev_season = prev_match.group(1)
        
        next_match = re.search(r'сезон\s*(\d{4})\s*>', html, re.IGNORECASE)
        if next_match:
            next_season = next_match.group(1)
        
        # Также ищем ссылки
        soup = BeautifulSoup(html, 'html.parser')
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text()
            if 'сезон' in text.lower():
                year_match = re.search(r'(\d{4})', href)
                if year_match:
                    year = year_match.group(1)
                    if '<' in text and not prev_season:
                        prev_season = year
                    elif '>' in text and not next_season:
                        next_season = year
        
        return prev_season, next_season
    
    def to_dict(self, season: SeasonData) -> dict:
        """Конвертирует SeasonData в словарь для MongoDB."""
        return {
            'league_slug': season.league_slug,
            'league_name': season.league_name,
            'year': season.year,
            'season_number': season.season_number,
            'all_teams': season.all_teams,
            'winners': season.winners,
            'jury': season.jury,
            'editors': season.editors,
            'host': season.host,
            'prev_season': season.prev_season,
            'next_season': season.next_season,
            'stages': [
                {
                    'name': stage.name,
                    'order': stage.order,
                    'notes': stage.notes,
                    'additional_teams': stage.additional_teams,
                    'additional_notes': stage.additional_notes,
                    'games': [
                        {
                            'id': game.id,
                            'name': game.name,
                            'order': game.order,
                            'date': game.date,
                            'date_raw': game.date_raw,
                            'contests': game.contests,
                            'jury': game.jury,
                            'host': game.host,
                            'notes': game.notes,
                            'is_cancelled': game.is_cancelled,
                            'teams': [
                                {
                                    'team_slug': t.team_slug,
                                    'team_name': t.team_name,
                                    'team_link': t.team_link,
                                    'place': t.place,
                                    'scores': t.scores,
                                    'total': t.total,
                                    'passed': t.passed,
                                    'is_winner': t.is_winner,
                                    'city': t.city,
                                }
                                for t in game.teams
                            ]
                        }
                        for game in stage.games
                    ]
                }
                for stage in season.stages
            ]
        }


# ==============================================================================
# CLI для тестирования
# ==============================================================================

if __name__ == '__main__':
    import sys
    import json
    import pymongo
    
    # Тестируем на одном сезоне
    client = pymongo.MongoClient('mongodb://localhost:27017')
    db = client['humorpedia']
    
    test_path = sys.argv[1] if len(sys.argv) > 1 else 'kvn/premier-liga/2023'
    
    season_doc = db.kvn.find_one({'full_path': test_path})
    if not season_doc:
        print(f"❌ Сезон {test_path} не найден")
        sys.exit(1)
    
    # Получаем HTML контент
    text_modules = [m for m in season_doc.get('modules', []) if m.get('type') == 'text_block']
    if not text_modules:
        print("❌ Нет текстового контента")
        sys.exit(1)
    
    html = text_modules[0].get('data', {}).get('content', '')
    
    # Парсим
    parser = KVNSeasonParser()
    
    # Определяем лигу и год из пути
    path_parts = test_path.split('/')
    league = path_parts[1] if len(path_parts) > 1 else ''
    year_match = re.search(r'(\d{4})', path_parts[-1])
    year = int(year_match.group(1)) if year_match else 0
    
    result = parser.parse(html, league=league, year=year)
    
    print(f"\n{'='*60}")
    print(f"📋 {test_path}")
    print(f"{'='*60}")
    print(f"Лига: {result.league_slug}")
    print(f"Год: {result.year}")
    print(f"Команд: {len(result.all_teams)}")
    print(f"Победители: {result.winners}")
    print(f"Жюри: {len(result.jury)}")
    print(f"Редакторы: {result.editors}")
    print(f"Ведущий: {result.host}")
    
    print(f"\nСтадии ({len(result.stages)}):")
    for stage in result.stages:
        print(f"  📌 {stage.name} ({len(stage.games)} игр)")
        for game in stage.games:
            print(f"    🎮 {game.name} - {game.date}")
            print(f"       Команд: {len(game.teams)}, Конкурсов: {len(game.contests)}")
            if game.teams[:3]:
                for t in game.teams[:3]:
                    passed = "✅" if t.passed else "❌"
                    print(f"       {passed} {t.place}. {t.team_name}: {t.total}")
    
    # Сохраняем результат
    output_file = f"season_{league}_{year}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(parser.to_dict(result), f, ensure_ascii=False, indent=2)
    print(f"\n💾 Результат сохранён в {output_file}")
    
    client.close()

