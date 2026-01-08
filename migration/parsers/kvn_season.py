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
    # Альтернативные названия - Кубок мэра между 1/4 и 1/2
    (r'\bКубок мэра\b', 'Кубок мэра', 2.5),  # order 2.5 = между 1/4(2) и 1/2(3)
    (r'\bУтешительн\w*\s*игр\w*\b', 'Утешительная игра', 2.5),
    (r'\bГолосящий КиВиН\b', 'Голосящий КиВиН', 6),
]

# Паттерны для определения игр внутри стадии
# ВАЖНО: [её] для поддержки обеих форм написания буквы ё/е
GAME_PATTERNS = [
    # "Первая 1/8 финала (дата)" или "Первая игра"
    (r'(Перв(?:ая|ый|ое))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 1),
    (r'(Втор(?:ая|ой|ое))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 2),
    (r'(Трет(?:ья|ь[яие]|ий|ье))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 3),
    # Четвёртая - поддержка обеих форм: Четвертая и Четвёртая
    (r'(Четв[её]рт(?:ая|ый|ое))\s*(?:игра\s+)?(\d/\d+\s*финал[аеы]?|1/8|1/4|1/2|полуфинал[аеы]?|четвертьфинал[аеы]?|финал[аеы]?)?\s*(?:\(([^)]+)\))?', 4),
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

# Дефолтные ведущие по лигам
# Используется, если ведущий не указан явно
DEFAULT_HOSTS = {
    'vl-kvn': {
        # До 2021 включительно - Александр Васильевич Масляков
        # С 2022 ведущие могут меняться
        'default': 'Александр Васильевич Масляков',
        'until_year': 2021,  # До этого года включительно используем default
    },
    'vysshaya-liga': {
        'default': 'Александр Васильевич Масляков',
        'until_year': 2021,
    },
    'premier-liga': {
        'default': 'Александр Александрович Масляков',
        'until_year': 2023,  # Обычно он вёл до конца
    },
    # Для остальных лиг ведущий должен быть указан явно
}

# Паттерны для команд, присоединившихся позже
LATE_JOIN_PATTERNS = [
    r'присоединил[аи]?сь?\s+к\s+сезону\s+(?:со\s+стадии\s+)?([^.]+)',
    r'(?:их\s+)?места?\s+(?:в\s+сезоне\s+)?заняли?\s+([^.]+)',
    r'вылетевши[еми]+\s+из\s+[Вв]ысшей\s+лиги\s+([^.]+)',
    r'финалист[ыа]?\s+прошлого\s+сезона\s+([^.]+)',
]

# Окончания падежей для нормализации названий команд в доборах
# "Сборную Пермского края" -> "Сборная Пермского края"
CASE_ENDINGS = {
    # Винительный падеж -> Именительный
    'ую': 'ая',    # Сборную -> Сборная
    'юю': 'яя',    # синюю -> синяя
    'ую': 'ая',    # красную -> красная
    'ого': 'ый',   # красного -> красный (но "Пермского" оставляем)
    'его': 'ий',   # синего -> синий
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
    is_additional: bool = False  # Прошла через добор (желтый цвет)
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
    all_teams: List[Dict[str, str]] = field(default_factory=list)  # Список команд: [{"slug": "...", "name": "..."}]
    
    # Стадии сезона
    stages: List[Stage] = field(default_factory=list)
    
    # Победители
    winners: List[str] = field(default_factory=list)  # Slug команд-победителей
    
    # Жюри сезона (общий список)
    jury: List[str] = field(default_factory=list)
    
    # Редакторы сезона
    editors: List[str] = field(default_factory=list)
    
    # Ведущие сезона (может быть несколько)
    hosts: List[str] = field(default_factory=list)
    host: str = ""  # Deprecated, оставляем для совместимости
    
    # Общий текст/описание (текст до "Результатов")
    description: str = ""
    
    # HTML-контент введения (до результатов)
    intro_html: str = ""
    
    # HTML-контент дополнительных секций (Кубок мэра и т.п.)
    extra_sections: List[Dict[str, str]] = field(default_factory=list)
    
    # Метаданные (из таблицы фактов)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Ссылки на соседние сезоны
    prev_season: str = ""
    next_season: str = ""
    
    # Команды, присоединившиеся к сезону позже (вылетевшие из высшей лиги и т.п.)
    # Формат: [{"name": "Команда", "stage": "1/8 финала", "note": "вылетели из Высшей лиги"}]
    late_joined_teams: List[Dict[str, str]] = field(default_factory=list)


# ==============================================================================
# ПАРСЕРЫ
# ==============================================================================

def normalize_case(name: str) -> str:
    """
    Нормализует падеж названия команды.
    
    Преобразует винительный падеж в именительный:
    - "Сборную Пермского края" -> "Сборная Пермского края"
    - "Команду КВН" -> "Команда КВН"
    
    НЕ меняет:
    - "Пермского края" (родительный падеж - часть названия)
    """
    if not name:
        return name
    
    # Разбиваем на слова
    words = name.split()
    if not words:
        return name
    
    # Нормализуем только первое слово (обычно это "Сборную", "Команду" и т.п.)
    first_word = words[0]
    
    # Проверяем окончания винительного падежа для первого слова
    if first_word.endswith('ую') and len(first_word) > 3:
        # Сборную -> Сборная
        words[0] = first_word[:-2] + 'ая'
    elif first_word.endswith('юю') and len(first_word) > 3:
        words[0] = first_word[:-2] + 'яя'
    elif first_word.endswith('у') and len(first_word) > 2:
        # Проверяем, не заканчивается ли на согласную + "у" (типа "Мастеру")
        # Команду -> Команда
        if first_word[-2] in 'аеёиоуыэюя':
            pass  # Оставляем как есть
        else:
            words[0] = first_word[:-1] + 'а'
    
    return ' '.join(words)


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
                    # Извлекаем slug из ссылки (поддерживаем оба формата: kvn/team/ и kvn/teams/)
                    if 'kvn/teams/' in href:
                        team_score.team_slug = href.split('kvn/teams/')[-1].replace('.html', '').strip('/')
                    elif 'kvn/team/' in href:
                        team_score.team_slug = href.split('kvn/team/')[-1].replace('.html', '').strip('/')
                
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
    
    def __init__(self, default_year: int = None, team_slug_map: dict = None, league: str = ""):
        self.table_parser = TableParser()
        self.default_year = default_year or datetime.now().year
        self.team_slug_map = team_slug_map or {}  # Кэш для поиска slug по названию команды (name -> slug)
        self.league = league  # Slug лиги для дефолтного ведущего
    
    
    def _fill_missing_slugs(self, teams: List[TeamScore]) -> None:
        """Заполняет slug'и для команд, у которых они отсутствуют, по названию."""
        for team in teams:
            if not team.team_slug and team.team_name:
                name_lower = team.team_name.lower()
                # Пробуем найти точное совпадение
                if name_lower in self.team_slug_map:
                    team.team_slug = self.team_slug_map[name_lower]
                else:
                    # Пробуем найти частичное совпадение
                    for map_name, map_slug in self.team_slug_map.items():
                        if name_lower in map_name or map_name in name_lower:
                            team.team_slug = map_slug
                            break
    
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
            # Заполняем slug'и для команд без ссылок
            self._fill_missing_slugs(game.teams)
        else:
            # Нет таблицы - ищем результаты в тексте
            game.teams = self._parse_text_results(html_section)
        
        # Ищем жюри
        game.jury = self._find_jury(html_section)
        
        # Ищем ведущего (с учётом дефолтного для лиги)
        game.host = self._find_host(html_section, self.league, self.default_year)
        
        # Определяем прошедшие команды если не определено
        self._detect_passed_teams(game, html_section, stage_name)
        
        # Парсим дату с годом по умолчанию
        if game.date_raw and not game.date:
            game.date = self._parse_date(game.date_raw, self.default_year)
        
        return game
    
    def _find_game_header(self, html: str, stage_name: str, game_order: int) -> Tuple[str, str]:
        """
        Находит заголовок игры и дату.
        
        УНИФИКАЦИЯ НАЗВАНИЙ:
        - "Первая 1/8 финала", "Вторая 1/8 финала" итд
        - "Первая 1/4 финала", "Вторая 1/4 финала" итд
        - "Первая 1/2 финала", "Вторая 1/2 финала" итд
        - "Финал" (без номера)
        """
        # Стандартные числительные
        ordinals = {
            1: 'Первая', 2: 'Вторая', 3: 'Третья',
            4: 'Четвёртая', 5: 'Пятая', 6: 'Шестая'
        }
        
        ordinal = ordinals.get(game_order, f'{game_order}-я')
        date = ""
        
        # Ищем паттерн "Первая 1/8 финала (дата)" или похожий
        for pattern, order in GAME_PATTERNS:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                groups = match.groups()
                # Извлекаем дату из последней группы если есть
                date = groups[-1] if len(groups) > 2 and groups[-1] else ""
                break
        
        # Если не нашли дату в паттерне - ищем отдельно
        if not date:
            for pattern in DATE_PATTERNS:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    date = ' '.join(g for g in match.groups() if g)
                    break
        
        # УНИФИКАЦИЯ НАЗВАНИЯ: всегда "Первая <стадия>" формат
        # Для финала - просто "Финал"
        if 'финал' in stage_name.lower() and '/' not in stage_name:
            # Это финал - без номера если одна игра
            name = stage_name
        else:
            # Унифицированный формат: "Первая 1/8 финала"
            name = f"{ordinal} {stage_name}"
        
        return name, date
    
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
        """
        Парсит результаты из текста (когда нет таблицы).
        
        Поддерживает форматы:
        1. Ссылки на команды: <a href="kvn/teams/komanda">Команда</a>
        2. Нумерованный список: "1. Команда – 14,2" или "1. **Команда** – 14,2"
        3. Просто список команд с баллами: "Команда – 14,2"
        4. Список с выделением жирным: "1. **Экипаж**"
        """
        teams = []
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        # Метод 1: Ищем ссылки на команды
        links = soup.find_all('a', href=re.compile(r'kvn/teams?/'))
        for link in links:
            team = TeamScore()
            team.team_name = link.get_text(strip=True)
            href = link.get('href', '')
            team.team_link = href
            
            if 'kvn/teams/' in href:
                team.team_slug = href.split('kvn/teams/')[-1].replace('.html', '').strip('/')
            elif 'kvn/team/' in href:
                team.team_slug = href.split('kvn/team/')[-1].replace('.html', '').strip('/')
            
            # Ищем балл рядом с названием
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                score_match = re.search(r'(\d+[.,]\d+)', parent_text)
                if score_match:
                    try:
                        team.total = float(score_match.group(1).replace(',', '.'))
                    except:
                        pass
            
            # Проверяем выделение жирным
            if link.find_parent(['strong', 'b']) or link.find(['strong', 'b']):
                team.passed = True
            
            teams.append(team)
        
        # Метод 2: Парсим нумерованный текстовый список
        # Форматы: "1. Команда – 14,2" или "1. **Команда**" или "1. Команда"
        # Паттерн: номер + точка + название команды (опционально в жирном) + опционально тире + опционально баллы
        text_pattern = r'(\d+)\.\s*(?:\*\*)?([^–\-\n*]+?)(?:\*\*)?\s*(?:[–\-]\s*(\d+[.,]?\d*))?\s*(?:\n|$)'
        
        text_matches = re.findall(text_pattern, text, re.MULTILINE)
        for match in text_matches:
            place_str, team_name, score_str = match
            team_name = team_name.strip()
            
            # Пропускаем если это уже найдено через ссылки
            if any(t.team_name and team_name.lower() in t.team_name.lower() for t in teams):
                continue
            
            # Пропускаем короткие или служебные слова
            if len(team_name) < 2 or team_name.lower() in ('м', 'место', 'команда', 'итого'):
                continue
            
            team = TeamScore()
            team.team_name = team_name
            team.place = int(place_str)
            
            if score_str:
                try:
                    team.total = float(score_str.replace(',', '.'))
                except:
                    pass
            
            # Проверяем выделение жирным в исходном HTML
            # Ищем команду в strong/b тегах
            for bold in soup.find_all(['strong', 'b']):
                if team_name.lower() in bold.get_text().lower():
                    team.passed = True
                    break
            
            teams.append(team)
        
        # Если места не определены - сортируем по баллам
        if teams and all(t.place == 0 for t in teams):
            teams.sort(key=lambda t: t.total, reverse=True)
            for i, team in enumerate(teams):
                team.place = i + 1
        else:
            # Сортируем по месту
            teams.sort(key=lambda t: t.place if t.place > 0 else 999)
        
        return teams
    
    def _find_jury(self, html: str) -> List[str]:
        """Находит список жюри."""
        jury = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем "Жюри:" и извлекаем имена
        match = re.search(r'[Жж]юри:?\s*([^<\n]+)', html)
        if match:
            jury_text = match.group(1)
            # Разделяем по запятым и точкам
            names = re.split(r'[,;.]', jury_text)
            for name in names:
                name = name.strip()
                # Убираем лишние символы
                name = re.sub(r'^[:\s]+|[:\s]+$', '', name)
                if name and len(name) > 2:  # Минимум 3 символа
                    jury.append(name)
        
        # Также ищем ссылки на людей после слова "жюри"
        jury_section = soup.find(string=re.compile(r'[Жж]юри', re.IGNORECASE))
        if jury_section:
            parent = jury_section.find_parent()
            if parent:
                # Ищем ссылки в родительском элементе и следующих элементах
                links = parent.find_all('a', href=re.compile(r'people/'))
                # Также ищем в следующих элементах
                for sibling in parent.find_next_siblings()[:5]:
                    links.extend(sibling.find_all('a', href=re.compile(r'people/')))
                
                for link in links:
                    name = link.get_text(strip=True)
                    if name and name not in jury:
                        jury.append(name)
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_jury = []
        for name in jury:
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique_jury.append(name)
        
        return unique_jury
    
    def _find_host(self, html: str, league: str = "", year: int = 0) -> str:
        """
        Находит ведущего игры.
        
        Если ведущий не указан явно, использует дефолтного ведущего для лиги.
        
        Args:
            html: HTML контент игры
            league: Slug лиги (для дефолтного ведущего)
            year: Год сезона (для проверки периода)
            
        Returns:
            Имя ведущего
        """
        # Ищем разные варианты: "Ведущий:", "Ведущий игры:", "Ведущие:"
        patterns = [
            r'[Вв]едущ(?:ий|ая|ие)\s+игр[ыи]?:?\s*([^<\n,;]+)',
            r'[Вв]едущ(?:ий|ая|ие):?\s*([^<\n,;]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                host = match.group(1).strip()
                # Убираем лишние символы в конце
                host = re.sub(r'[.,;]+$', '', host).strip()
                # Убираем HTML теги если есть
                soup = BeautifulSoup(host, 'html.parser')
                host = soup.get_text(strip=True)
                if host and len(host) > 2:
                    return host
        
        # Если не нашли - используем дефолтного ведущего для лиги
        if league and league in DEFAULT_HOSTS:
            league_config = DEFAULT_HOSTS[league]
            until_year = league_config.get('until_year', 9999)
            if year and year <= until_year:
                return league_config.get('default', '')
        
        return ""
    
    def _detect_passed_teams(self, game: Game, html: str, stage_name: str = "") -> None:
        """
        Определяет прошедшие команды по контексту.
        
        ВАЖНО: Команды помечаются как прошедшие только если:
        1. Они выделены жирным В ТАБЛИЦЕ результатов
        2. Есть явное упоминание "прошли" рядом с командой
        3. НЕ помечаются просто по наличию в любом <strong> теге (может быть просто упоминание в тексте)
        
        В ФИНАЛЕ: Команды, выделенные жирным, помечаются как победители (is_winner=True).
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Определяем, является ли это финалом
        is_final = 'финал' in stage_name.lower() and '/' not in stage_name.lower()
        
        # Ищем таблицу результатов
        table = soup.find('table')
        if table:
            # В таблице - если команда выделена жирным, значит прошла
            for row in table.find_all('tr')[1:]:  # Пропускаем заголовок
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    team_cell = cells[1]  # Вторая колонка обычно команда
                    team_name = team_cell.get_text(strip=True)
                    
                    # Проверяем выделение жирным ТОЛЬКО в ячейке команды
                    if team_cell.find(['strong', 'b']):
                        for team in game.teams:
                            if team.team_name == team_name or team_name in team.team_name or team.team_name in team_name:
                                team.passed = True
                                # В финале выделенные жирным = победители
                                if is_final:
                                    team.is_winner = True
                                break
        
        # Ищем секции "прошли" / "не прошли" в тексте после таблицы
        # Сначала ищем паттерны типа "В четвертьфинал напрямую прошли: «Команда1», «Команда2»"
        html_text = str(soup)
        
        # Расширенные паттерны для "прошли"
        extended_patterns = [
            (r'[Вв]\s+четвертьфинал[аеы]?\s+напрямую\s+прош[её]?л[иа]?\s*:', 'passed'),
            (r'[Вв]\s+полуфинал[аеы]?\s+прош[её]?л[иа]?\s*:', 'passed'),
            (r'[Вв]\s+финал[аеы]?\s+прош[её]?л[иа]?\s*:', 'passed'),
            (r'прош[её]?л[иа]?\s+в\s+четвертьфинал[аеы]?\s*:', 'passed'),
            (r'прош[её]?л[иа]?\s+в\s+полуфинал[аеы]?\s*:', 'passed'),
            (r'прош[её]?л[иа]?\s+в\s+финал[аеы]?\s*:', 'passed'),
            # Паттерны для финалистов: "третьи финалисты", "вторые финалисты", "первые финалисты"
            (r'[Пп]ерв[ыые]?\s+финалист[ыа]?', 'passed'),
            (r'[Вв]тор[ыые]?\s+финалист[ыа]?', 'passed'),
            (r'[Тт]реть[иыые]?\s+финалист[ыа]?', 'passed'),
            (r'[Чч]етв[её]рт[ыые]?\s+финалист[ыа]?', 'passed'),
            (r'[Пп]ят[ыые]?\s+финалист[ыа]?', 'passed'),
            (r'финалист[ыа]?\s+[Вв]ысшей\s+лиг[иы]', 'passed'),
        ]
        
        # Ищем расширенные паттерны
        for pattern, result_type in extended_patterns:
            pattern_matches = re.finditer(pattern, html_text, re.IGNORECASE)
            for pattern_match in pattern_matches:
                # Для паттернов "финалисты" ищем команду ДО паттерна (в той же строке)
                if 'финалист' in pattern.lower():
                    # Ищем команду в кавычках перед паттерном
                    start_pos = max(0, pattern_match.start() - 200)  # 200 символов до паттерна
                    end_pos = pattern_match.end()
                    context = html_text[start_pos:end_pos]
                    
                    # Ищем команду в кавычках «...» в этом контексте
                    quoted_teams = re.findall(r'«([^»]+)»', context)
                    for quoted_name in quoted_teams:
                        quoted_name = quoted_name.strip()
                        # Ищем команду по названию
                        for team in game.teams:
                            if (team.team_name and quoted_name in team.team_name) or \
                               (team.team_name and team.team_name in quoted_name):
                                if result_type == 'passed':
                                    team.passed = True
                                    # Если это финал - помечаем как победителя
                                    if is_final:
                                        team.is_winner = True
                                elif result_type == 'winner':
                                    team.passed = True
                                    team.is_winner = True
                                elif result_type == 'eliminated':
                                    team.passed = False
                                break
                else:
                    # Для остальных паттернов ищем команды ПОСЛЕ паттерна
                    start_pos = pattern_match.end()
                    context = html_text[start_pos:start_pos + 1000]  # 1000 символов после паттерна
                    
                    # Ищем команды в кавычках «...»
                    quoted_teams = re.findall(r'«([^»]+)»', context)
                    for quoted_name in quoted_teams:
                        quoted_name = quoted_name.strip()
                        # Ищем команду по названию
                        for team in game.teams:
                            if (team.team_name and quoted_name in team.team_name) or \
                               (team.team_name and team.team_name in quoted_name):
                                if result_type == 'passed':
                                    team.passed = True
                                    # Если это финал - помечаем как победителя
                                    if is_final:
                                        team.is_winner = True
                                elif result_type == 'winner':
                                    team.passed = True
                                    team.is_winner = True
                                elif result_type == 'eliminated':
                                    team.passed = False
                                break
        
        # Стандартные паттерны
        for pattern, result_type in RESULT_PATTERNS:
            # Ищем паттерн в тексте
            pattern_match = re.search(pattern, html_text, re.IGNORECASE)
            if pattern_match:
                # Ищем команды в кавычках после паттерна
                start_pos = pattern_match.end()
                context = html_text[start_pos:start_pos + 500]  # 500 символов после паттерна
                
                # Ищем команды в кавычках «...»
                quoted_teams = re.findall(r'«([^»]+)»', context)
                for quoted_name in quoted_teams:
                    quoted_name = quoted_name.strip()
                    # Ищем команду по названию
                    for team in game.teams:
                        if (team.team_name and quoted_name in team.team_name) or \
                           (team.team_name and team.team_name in quoted_name):
                            if result_type == 'passed':
                                team.passed = True
                            elif result_type == 'winner':
                                team.passed = True
                                team.is_winner = True
                            elif result_type == 'eliminated':
                                team.passed = False
                            break
                
                # Также ищем команды по ссылкам (старый способ)
                match = soup.find(string=re.compile(pattern, re.IGNORECASE))
                if match:
                    parent = match.find_parent()
                    if parent:
                        links = parent.find_all('a', href=re.compile(r'kvn/teams?/'))
                        for link in links:
                            href = link.get('href', '')
                            slug = href.split('kvn/teams?/')[-1].replace('.html', '').strip('/') if 'kvn/teams' in href else ''
                            link_name = link.get_text(strip=True)
                            
                            for team in game.teams:
                                if team.team_slug == slug or team.team_name == link_name:
                                    if result_type == 'passed':
                                        team.passed = True
                                    elif result_type == 'winner':
                                        team.passed = True
                                        team.is_winner = True
                                    elif result_type == 'eliminated':
                                        team.passed = False


class StageParser:
    """Парсер стадии сезона (1/8, 1/4, и т.д.)."""
    
    def __init__(self, default_year: int = None, team_slug_map: dict = None, league: str = ""):
        self.default_year = default_year
        self.team_slug_map = team_slug_map or {}
        self.league = league
        self.game_parser = GameParser(default_year=default_year, team_slug_map=self.team_slug_map, league=league)
    
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
            # Извлекаем реальный порядковый номер из контента игры
            real_order = self._extract_game_order(game_html) or i
            
            game = self.game_parser.parse(game_html, stage_name, real_order)
            if game and (game.teams or game.notes):
                game.order = real_order
                game.id = f"{stage_name.lower().replace(' ', '-').replace('/', '-')}-{real_order}"
                stage.games.append(game)
        
        # Сортируем игры по порядковому номеру
        stage.games.sort(key=lambda g: g.order)
        
        # Ищем информацию о доборе
        stage.additional_teams, stage.additional_notes = self._find_additional(html_section)
        
        return stage
    
    def _split_into_games(self, html: str) -> List[str]:
        """Разбивает секцию стадии на отдельные игры."""
        soup = BeautifulSoup(html, 'html.parser')
        html_str = str(soup)
        
        # Ищем заголовки игр - используем set для уникальных позиций
        found_positions = {}  # position -> (element, order)
        
        for element in soup.find_all(['strong', 'b', 'h4', 'h3']):
            text = element.get_text()
            
            # Проверяем каждый паттерн для определения номера игры
            for pattern, order in GAME_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    # Находим позицию элемента в HTML
                    elem_str = str(element)
                    pos = html_str.find(elem_str)
                    
                    if pos >= 0 and pos not in found_positions:
                        # Извлекаем реальный номер игры из текста
                        real_order = self._extract_game_order(text) or order
                        found_positions[pos] = (element, real_order, pos)
                    break
        
        if not found_positions:
            # Если нет явных заголовков игр - вся секция это одна игра
            return [html]
        
        # Сортируем по позиции в документе
        game_headers = sorted(found_positions.values(), key=lambda x: x[2])
        
        # Разбиваем HTML по заголовкам
        sections = []
        
        for i, (header, order, pos) in enumerate(game_headers):
            start = pos
            if i < len(game_headers) - 1:
                end = game_headers[i + 1][2]
            else:
                end = len(html_str)
            
            if start >= 0:
                sections.append(html_str[start:end])
        
        return sections if sections else [html]
    
    def _extract_game_order(self, html_or_text: str) -> int:
        """
        Извлекает порядковый номер игры из HTML секции.
        Ищет только в первых элементах (заголовке игры).
        """
        # Если это HTML - ищем в первом strong/b/h* элементе
        if '<' in html_or_text:
            soup = BeautifulSoup(html_or_text, 'html.parser')
            # Берём первый заголовочный элемент
            header = soup.find(['strong', 'b', 'h3', 'h4'])
            if header:
                text = header.get_text().lower()
            else:
                # Берём первые 200 символов текста
                text = soup.get_text()[:200].lower()
        else:
            text = html_or_text.lower()
        
        ordinals = [
            (r'перв', 1),
            (r'втор', 2),
            (r'трет', 3),
            (r'четв[её]рт', 4),
            (r'пят', 5),
            (r'шест', 6),
            (r'седьм', 7),
            (r'восьм', 8),
        ]
        
        for pattern, order in ordinals:
            if re.search(pattern, text):
                return order
        
        # Пробуем найти цифру
        match = re.search(r'игра\s*(\d+)', text)
        if match:
            return int(match.group(1))
        
        return 0
    
    def _find_additional(self, html: str) -> Tuple[List[str], str]:
        """
        Находит информацию о доборе после стадии.
        
        Ищет по словам: "добрали", "добраны", "добор"
        """
        teams = []
        notes = ""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Паттерны для поиска доборов
        dobor_patterns = [
            r'[Дд]обрал[иа]?\s+[^<]+',
            r'[Дд]обраны\s+[^<]+',
            r'[Дд]обор[аы]?\s+[^<]+',
            r'[Дд]обрат[ьи]\s+[^<]+',  # "добрать"
            r'предложил\s+[^<]*[Дд]обрат[ьи]',  # "предложил добрать"
        ]
        
        # Ищем текст с доборами
        found_text = ""
        for pattern in dobor_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                found_text = match.group(0)
                # Извлекаем полное предложение
                start = max(0, match.start() - 50)
                end = min(len(html), match.end() + 200)
                context = html[start:end]
                
                # Ищем команды в этом контексте
                context_soup = BeautifulSoup(context, 'html.parser')
                
                # Ищем ссылки на команды
                links = context_soup.find_all('a', href=re.compile(r'kvn/teams?/'))
                for link in links:
                    href = link.get('href', '')
                    slug = href.split('kvn/teams?/')[-1].replace('.html', '').strip('/')
                    if slug and slug not in teams:
                        teams.append(slug)
                
                # Также ищем названия команд в кавычках «...»
                quoted_teams = re.findall(r'«([^»]+)»', context)
                for team_name in quoted_teams:
                    # Фильтруем - не берем короткие слова или служебные слова
                    team_name = team_name.strip()
                    # Исключаем служебные слова и фразы
                    exclude_words = ['вышки', 'вышка', 'лига', 'сезон', 'добраны', 'добрали', 
                                    'комбинированный', 'биатлон', 'раунд', 'стадия', 'игра']
                    if (len(team_name) > 2 and 
                        team_name.lower() not in exclude_words and
                        not any(word in team_name.lower() for word in exclude_words)):
                        # Нормализуем падеж: "Сборную Пермского края" -> "Сборная Пермского края"
                        normalized_name = normalize_case(team_name)
                        if normalized_name not in teams:
                            teams.append(normalized_name)
                
                # Сохраняем текст добора
                if not notes:
                    # Извлекаем чистое предложение
                    sentence_match = re.search(r'[^.!?]*' + re.escape(found_text) + r'[^.!?]*[.!?]', context)
                    if sentence_match:
                        notes = sentence_match.group(0).strip()
                    else:
                        notes = found_text.strip()
                    
                    # Капитализируем первое предложение (начинаем с большой буквы)
                    if notes:
                        notes = notes[0].upper() + notes[1:] if len(notes) > 1 else notes.upper()
                
                break  # Берем первый найденный добор
        
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
    
    def parse(self, html: str, league: str = "", year: int = 0, modules: List[Dict] = None) -> SeasonData:
        """
        Парсит контент страницы сезона.
        
        Args:
            html: HTML контент страницы (весь контент или только результаты)
            league: Slug лиги
            year: Год сезона
            modules: Список модулей из MongoDB (для расширенного парсинга)
            
        Returns:
            SeasonData с полной информацией о сезоне
        """
        season = SeasonData(league_slug=league, year=year)
        
        # Строим карту slug'ов команд из всего HTML
        team_slug_map = self._build_team_slug_map(html)
        
        # Инициализируем stage_parser с годом сезона, картой slug'ов и лигой
        self.stage_parser = StageParser(default_year=year, team_slug_map=team_slug_map, league=league)
        
        # Если есть модули - парсим из них
        if modules:
            self._parse_from_modules(modules, season)
        else:
            # Парсим из сырого HTML
            self._parse_metadata(html, season)
        
        # Определяем HTML с результатами
        # Собираем контент из всех текстовых модулей с результатами
        results_parts = []
        if modules:
            for m in modules:
                if m.get('type') == 'text_block':
                    title = m.get('title', '')
                    title_lower = title.lower()
                    content = m.get('data', {}).get('content', '')
                    
                    # Ищем модули с результатами, стадиями или Кубком мэра
                    is_results = ('результат' in title_lower or
                                 'кубок мэра' in title_lower or  # Кубок мэра может содержать 1/2 и финал!
                                 'утешительн' in title_lower or
                                 '1/8' in content or '1/4' in content or '1/2' in content or
                                 re.search(r'(?<!/)\bфинал', content, re.IGNORECASE))
                    
                    if is_results:
                        # Если название модуля содержит название стадии - добавляем как заголовок
                        # (чтобы парсер стадий мог его найти)
                        if 'кубок мэра' in title_lower:
                            # Добавляем заголовок перед контентом
                            results_parts.append(f'<h3>{title}</h3>')
                        results_parts.append(content)
        
        results_html = '\n'.join(results_parts) if results_parts else html
        
        # Находим и парсим стадии
        stages = self._split_into_stages(results_html)
        for stage_name, stage_order, stage_html in stages:
            # Для кубка мэра сначала убираем таблицы из HTML перед парсингом
            if 'кубок' in stage_name.lower():
                soup = BeautifulSoup(stage_html, 'html.parser')
                # Убираем все таблицы - оставляем только текст до них
                tables = soup.find_all('table')
                for table in tables:
                    # Удаляем таблицу и всё после неё в том же родительском элементе
                    parent = table.parent
                    if parent:
                        # Удаляем таблицу и все последующие элементы
                        for sibling in list(table.next_siblings):
                            if hasattr(sibling, 'extract'):
                                sibling.extract()
                    table.decompose()
                # Обновляем stage_html без таблиц
                stage_html = str(soup)
            
            stage = self.stage_parser.parse(stage_html, stage_name, stage_order)
            
            # Для особых стадий (Кубок мэра и т.п.) обрабатываем победителей
            if 'кубок' in stage_name.lower():
                soup = BeautifulSoup(stage_html, 'html.parser')
                # Убираем заголовок стадии
                for h in soup.find_all(['h2', 'h3', 'h4']):
                    if 'кубок' in h.get_text().lower():
                        h.decompose()
                        break
                
                # Ищем текст про финал высшей лиги в кубке мэра
                html_text = str(soup)
                
                # Паттерн 1: "Победителями Кубка мэра признана команда «Юра»"
                winner_pattern1 = r'[Пп]обедител[ьямии]?\s+[Кк]убка\s+мэра[^<]*признан[аы]?\s+[^<]*команд[аы]?\s*«([^»]+)»'
                winner_matches1 = re.finditer(winner_pattern1, html_text, re.IGNORECASE)
                for match in winner_matches1:
                    team_name = match.group(1).strip()
                    # Ищем эту команду в сезоне и помечаем как победителя
                    for s in season.stages:
                        for g in s.games:
                            for t in g.teams:
                                if team_name in t.team_name or t.team_name in team_name:
                                    t.is_winner = True
                                    t.passed = True
                
                # Паттерн 2: "в финал Высшей лиги ... пригласили «Команда1», «Команда2»"
                final_pattern = r'в\s+финал[аеы]?\s+[Вв]ысшей\s+лиг[иы]\s+\d{4}\s+года[^<]*пригласил[иа]?\s*[^<]*«([^»]+)»'
                final_matches = re.finditer(final_pattern, html_text, re.IGNORECASE)
                
                # Если нашли команды, приглашенные в финал - это победители
                for match in final_matches:
                    team_name = match.group(1).strip()
                    # Ищем эту команду в сезоне и помечаем как победителя
                    for s in season.stages:
                        for g in s.games:
                            for t in g.teams:
                                if team_name in t.team_name or t.team_name in team_name:
                                    t.is_winner = True
                                    t.passed = True
                
                # Также ищем все команды в кавычках после "пригласили"
                invite_pattern = r'пригласил[иа]?\s*[^<]*?«([^»]+)»'
                invite_matches = re.finditer(invite_pattern, html_text, re.IGNORECASE)
                for match in invite_matches:
                    team_name = match.group(1).strip()
                    # Ищем эту команду в сезоне и помечаем как победителя
                    for s in season.stages:
                        for g in s.games:
                            for t in g.teams:
                                if team_name in t.team_name or t.team_name in team_name:
                                    t.is_winner = True
                                    t.passed = True
                
                # Для кубка мэра всегда сохраняем текст до таблицы в notes
                # (даже если есть игры, текст до таблицы должен быть сохранен)
                if 'кубок' in stage_name.lower():
                    # Сохраняем очищенный HTML (без таблиц) в notes
                    stage.notes = str(soup)
                elif not stage.games:
                    # Для других стадий сохраняем HTML как notes только если нет игр
                    stage.notes = str(soup)
            
            if stage.games or stage.notes:
                season.stages.append(stage)
        
        # Сортируем стадии по order (чтобы Кубок мэра был между 1/4 и 1/2)
        season.stages.sort(key=lambda s: s.order)
        
        # Связываем команды из доборов с играми следующей стадии
        self._link_additional_teams(season)
        
        # Собираем жюри из всех источников
        all_html = html
        if modules:
            all_html = '\n'.join(
                m.get('data', {}).get('content', '')
                for m in modules
                if m.get('type') == 'text_block'
            )
        
        # Находим команды, присоединившиеся позже
        season.late_joined_teams = self._find_late_joined_teams(all_html, season)
        
        # Собираем всех команд (включая присоединившихся позже)
        season.all_teams = self._collect_all_teams(season)
        
        # Добавляем команды, присоединившиеся позже, в all_teams (если их там ещё нет)
        for late_team in season.late_joined_teams:
            team_name = late_team.get('name', '')
            if team_name and not any(t.get('name') == team_name for t in season.all_teams):
                season.all_teams.append({"slug": "", "name": team_name})
        
        # Определяем победителей (если не найдены в метаданных)
        if not season.winners:
            season.winners = self._find_winners(season)
        
        season.jury = self._collect_jury(all_html, season)
        
        # Ссылки на соседние сезоны
        season.prev_season, season.next_season = self._find_adjacent_seasons(all_html, "")
        
        return season
    
    def _build_team_slug_map(self, html: str) -> dict:
        """Строит карту названий команд -> slug из всех ссылок в HTML."""
        team_slug_map = {}
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=re.compile(r'kvn/teams?/'))
        for link in links:
            href = link.get('href', '')
            name = link.get_text(strip=True)
            # Очищаем название от скобок с городом
            name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
            
            # Извлекаем slug
            if 'kvn/teams/' in href:
                slug = href.split('kvn/teams/')[-1].replace('.html', '').strip('/')
            elif 'kvn/team/' in href:
                slug = href.split('kvn/team/')[-1].replace('.html', '').strip('/')
            else:
                continue
            
            if name and slug:
                # Сохраняем в карту (может быть несколько вариантов названия)
                name_lower = name.lower()
                if name_lower not in team_slug_map:
                    team_slug_map[name_lower] = slug
        
        return team_slug_map
    
    def _link_additional_teams(self, season: SeasonData) -> None:
        """
        Связывает команды из доборов с играми ТЕКУЩЕЙ стадии.
        
        ВАЖНО: Команды из доборов должны быть помечены желтым в той стадии,
        где они играли (и были добранными), а не в следующей стадии.
        
        Например: после 1/8 финала добрали "Юра" → "Юра" должна быть желтой в 1/8 финала.
        """
        for stage in season.stages:
            if not stage.additional_teams:
                continue
            
            # Ищем команды из доборов в играх ТЕКУЩЕЙ стадии
            # (где они играли и были добранными)
            for additional_identifier in stage.additional_teams:
                found = False
                for game in stage.games:
                    for team in game.teams:
                        # Сравниваем по slug или по названию
                        # additional_identifier может быть slug или название команды
                        identifier_lower = additional_identifier.lower().strip()
                        team_name_lower = (team.team_name or '').lower().strip()
                        team_slug_lower = (team.team_slug or '').lower().strip()
                        
                        # Точное совпадение или вхождение (но не слишком короткое)
                        if (team_slug_lower == identifier_lower or
                            team_name_lower == identifier_lower or
                            (len(identifier_lower) > 3 and identifier_lower in team_name_lower) or
                            (len(team_name_lower) > 3 and team_name_lower in identifier_lower)):
                            team.is_additional = True
                            team.passed = True  # Добор = прошла
                            found = True
                            break
                    if found:
                        break
    
    def _parse_from_modules(self, modules: List[Dict], season: SeasonData) -> None:
        """
        Парсит данные из модулей MongoDB.
        
        Обрабатывает:
        - facts_table - метаданные сезона
        - text_block - описание и дополнительные секции
        
        ВАЖНО: Модули обрабатываются в порядке их поля 'order', чтобы правильно собрать intro_html
        """
        # Сортируем модули по order для правильной обработки
        sorted_modules = sorted(modules, key=lambda m: m.get('order', 0))
        
        for module in sorted_modules:
            module_type = module.get('type', '')
            
            if module_type == 'facts_table':
                # Парсим таблицу фактов
                # Формат: facts = {"Сезон": "37", "Ведущие": "<html>..."}
                facts = module.get('data', {}).get('facts', {})
                if isinstance(facts, dict):
                    facts_items = facts.items()
                elif isinstance(facts, list):
                    facts_items = [(f.get('label', ''), f.get('value', '')) for f in facts]
                else:
                    facts_items = []
                
                for label, value in facts_items:
                    label = label.lower()
                    
                    if label == 'сезон' or (label.startswith('сезон') and 'номер' not in label):
                        try:
                            season.season_number = int(re.search(r'\d+', str(value)).group())
                        except:
                            pass
                    elif 'ведущ' in label:
                        # Парсим ведущих (могут быть со ссылками и без)
                        hosts = self._parse_people_list(value)
                        if hosts:
                            season.hosts = hosts
                            season.host = ', '.join(hosts)
                    elif 'редактор' in label:
                        editors = self._parse_people_list(value)
                        if editors:
                            season.editors = editors
                    elif 'чемпион' in label or 'победител' in label:
                        # Парсим команды-чемпионы (названия команд, а не slug'и)
                        winners = self._parse_team_names_list(value)
                        if winners:
                            season.winners = winners
                    
                    # Сохраняем все метаданные
                    season.metadata[label] = value
            
            elif module_type == 'text_block':
                title = module.get('title', '')
                content = module.get('data', {}).get('content', '')
                
                # Определяем тип контента
                title_lower = title.lower()
                
                # Проверяем, является ли это модулем с результатами/стадиями
                is_results_module = ('результат' in title_lower or
                                    'кубок мэра' in title_lower or
                                    'утешительн' in title_lower or
                                    '1/8' in content or '1/4' in content or '1/2' in content or
                                    re.search(r'(?<!/)\bфинал', content, re.IGNORECASE))
                
                # Проверяем, является ли это списком команд
                soup = BeautifulSoup(content, 'html.parser')
                team_links = soup.find_all('a', href=re.compile(r'kvn/teams?/'))
                text_content = soup.get_text(strip=True)
                is_teams_list = (('команд' in title_lower and 'участн' in title_lower) or
                                ('участник' in title_lower and 'команд' in title_lower) or
                                (len(team_links) > 5) or
                                (len(team_links) > 3 and len(text_content) < 500))
                
                # Если это результаты - останавливаем сбор intro_html
                if is_results_module:
                    # Это результаты/стадии - пропускаем для intro_html
                    pass
                elif is_teams_list:
                    # Это список команд - пропускаем для intro_html
                    pass
                else:
                    # Это обычный текстовый блок - добавляем в intro_html
                    # Собираем ВСЕ текстовые блоки до первого блока с результатами
                    if content.strip():
                        if season.intro_html:
                            # Добавляем к существующему intro_html с разделителем
                            season.intro_html += f'\n\n{content}'
                        else:
                            # Первый блок - начинаем intro_html
                            season.intro_html = content
                            # Извлекаем текстовое описание
                            season.description = text_content
    
    def _parse_people_list(self, html_or_text: str) -> List[str]:
        """Извлекает список людей из HTML или текста."""
        soup = BeautifulSoup(html_or_text, 'html.parser')
        people = []
        
        # Сначала ищем ссылки на people
        links = soup.find_all('a', href=re.compile(r'people/'))
        for link in links:
            name = link.get_text(strip=True)
            if name:
                people.append(name)
        
        # Если ссылок нет - парсим текст
        if not people:
            text = soup.get_text()
            # Разделяем по запятым, переносам строк, точке с запятой
            names = re.split(r'[,;\n]', text)
            for name in names:
                name = name.strip()
                # Очищаем от скобок с комментариями
                name = re.sub(r'\([^)]*\)', '', name).strip()
                if name and len(name) > 2:
                    people.append(name)
        
        return people
    
    def _parse_teams_list(self, html_or_text: str) -> List[str]:
        """Извлекает список команд (slug'ов) из HTML."""
        soup = BeautifulSoup(html_or_text, 'html.parser')
        teams = []
        
        # Ищем ссылки на teams (kvn/team/* или kvn/teams/*)
        links = soup.find_all('a', href=re.compile(r'kvn/teams?/'))
        for link in links:
            href = link.get('href', '')
            # Извлекаем slug
            slug = href.split('/')[-1].replace('.html', '').strip()
            if slug and slug not in teams:
                teams.append(slug)
        
        return teams
    
    def _parse_team_names_list(self, html_or_text: str) -> List[str]:
        """Извлекает список названий команд из HTML (для победителей)."""
        soup = BeautifulSoup(html_or_text, 'html.parser')
        team_names = []
        
        # Ищем ссылки на teams и извлекаем текст (название команды)
        links = soup.find_all('a', href=re.compile(r'kvn/teams?/'))
        for link in links:
            name = link.get_text(strip=True)
            # Очищаем от скобок с городом
            name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()
            if name and name not in team_names:
                team_names.append(name)
        
        # Если ссылок нет - пытаемся извлечь из текста (команды в кавычках)
        if not team_names:
            text = soup.get_text()
            # Ищем команды в кавычках «...»
            quoted_teams = re.findall(r'«([^»]+)»', text)
            for team_name in quoted_teams:
                team_name = team_name.strip()
                # Очищаем от скобок с городом
                team_name = re.sub(r'\s*\([^)]*\)\s*$', '', team_name).strip()
                if team_name and team_name not in team_names:
                    team_names.append(team_name)
        
        return team_names
    
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
        
        # Корректируем порядок "Кубок мэра" на основе позиции в документе
        # Если он идет после полуфиналов - ставим order 3.5, если после 1/4 - 2.5
        for i, (header, name, order) in enumerate(stage_headers):
            if name == 'Кубок мэра':
                # Проверяем, какие стадии идут до и после
                prev_stage = stage_headers[i - 1][1] if i > 0 else None
                next_stage = stage_headers[i + 1][1] if i < len(stage_headers) - 1 else None
                
                # Если перед Кубком мэра идет 1/2 финала - значит он после полуфиналов
                if prev_stage and '1/2' in prev_stage or 'полу' in prev_stage.lower():
                    order = 3.5  # После полуфиналов
                # Если перед Кубком мэра идет 1/4 финала - значит он после четвертьфиналов
                elif prev_stage and ('1/4' in prev_stage or 'четверть' in prev_stage.lower()):
                    order = 2.5  # После четвертьфиналов
                # Если после Кубка мэра идет 1/2 финала - значит он перед полуфиналами
                elif next_stage and ('1/2' in next_stage or 'полу' in next_stage.lower()):
                    order = 2.5  # Перед полуфиналами
                # Иначе оставляем дефолтный порядок
                
                # Обновляем order в списке
                stage_headers[i] = (header, name, order)
        
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
    
    def _find_late_joined_teams(self, html: str, season: SeasonData) -> List[Dict[str, str]]:
        """
        Находит команды, присоединившиеся к сезону позже (не с первой стадии).
        
        Такие команды обычно:
        - Вылетели из высшей лиги и присоединились к более низкой
        - Заняли место команд, покинувших сезон
        
        Returns:
            Список словарей: [{"name": "Команда", "stage": "1/8 финала", "note": "вылетели из Высшей лиги"}]
        """
        late_teams = []
        
        # Ищем по паттернам
        for pattern in LATE_JOIN_PATTERNS:
            matches = re.finditer(pattern, html, re.IGNORECASE | re.DOTALL)
            for match in matches:
                context = match.group(0)
                
                # Определяем стадию присоединения (ищем в контексте)
                stage = ""
                if '1/8' in context:
                    stage = "1/8 финала"
                elif '1/4' in context or 'четвертьфинал' in context.lower():
                    stage = "1/4 финала"
                elif '1/2' in context or 'полуфинал' in context.lower():
                    stage = "1/2 финала"
                elif 'финал' in context.lower():
                    stage = "Финал"
                
                # Извлекаем команды из контекста
                quoted_teams = re.findall(r'«([^»]+)»', context)
                for team_name in quoted_teams:
                    team_name = team_name.strip()
                    # Нормализуем падеж
                    team_name = normalize_case(team_name)
                    
                    # Пропускаем служебные слова
                    exclude_words = ['вышка', 'сезон', 'лига', 'фестиваль']
                    if (len(team_name) > 2 and 
                        team_name.lower() not in exclude_words and
                        not any(word in team_name.lower() for word in exclude_words)):
                        
                        # Определяем причину
                        note = ""
                        if 'вылет' in context.lower():
                            note = "вылетели из Высшей лиги"
                        elif 'зняли' in context.lower() or 'место' in context.lower():
                            note = "заменили выбывшую команду"
                        elif 'финалист' in context.lower():
                            note = "финалисты прошлого сезона"
                        
                        # Проверяем, не добавлена ли уже эта команда
                        if not any(t['name'] == team_name for t in late_teams):
                            late_teams.append({
                                "name": team_name,
                                "stage": stage,
                                "note": note
                            })
        
        return late_teams
    
    def _collect_all_teams(self, season: SeasonData) -> List[Dict[str, str]]:
        """
        Собирает список всех команд-участниц сезона.
        
        ВАЖНО: Собирает только команды из ПЕРВОЙ стадии (1/8 финала или первой стадии, если 1/8 нет).
        Это команды-участницы сезона, которые начали играть с самого начала.
        
        Returns:
            Список словарей: [{"slug": "...", "name": "..."}]
        """
        teams_dict = {}  # slug -> name (или name -> name если нет slug)
        teams_by_name = {}  # name -> slug (для команд без slug)
        
        # Находим первую стадию (с минимальным order)
        if not season.stages:
            return []
        
        first_stage = min(season.stages, key=lambda s: s.order)
        
        # Собираем команды только из первой стадии
        for game in first_stage.games:
            for team in game.teams:
                team_name = team.team_name or ''
                team_slug = team.team_slug or ''
                
                if team_slug:
                    # Сохраняем slug и название
                    if team_slug not in teams_dict:
                        teams_dict[team_slug] = team_name or team_slug
                elif team_name:
                    # Если нет slug, но есть название - используем название как ключ
                    if team_name not in teams_by_name:
                        teams_by_name[team_name] = team_name
        
        # Преобразуем в список словарей
        result = []
        # Сначала команды со slug
        for slug, name in teams_dict.items():
            result.append({"slug": slug, "name": name})
        # Затем команды без slug (только по названию)
        for name, slug in teams_by_name.items():
            # Проверяем, не добавлена ли уже команда с таким названием
            if not any(t.get('name') == name for t in result):
                result.append({"slug": slug, "name": name})
        
        return result
    
    def _find_winners(self, season: SeasonData) -> List[str]:
        """
        Находит победителей сезона.
        
        ВАЖНО: Ищет только команды с флагом is_winner=True в финале.
        Это команды, которые получили бейдж "Победитель" в финале.
        
        Возвращает список НАЗВАНИЙ команд (не slug'ов).
        """
        winners = []
        
        # Ищем в финале
        finals = [s for s in season.stages if s.order == 4 or 'финал' in s.name.lower()]
        for final in finals:
            for game in final.games:
                for team in game.teams:
                    # Только команды с флагом is_winner=True (бейдж "Победитель")
                    if team.is_winner:
                        # Используем название команды, если есть, иначе slug
                        team_name = team.team_name or team.team_slug
                        if team_name and team_name not in winners:
                            winners.append(team_name)
        
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
    
    def _find_adjacent_seasons(self, html: str, current_path: str = "") -> Tuple[str, str]:
        """
        Находит ссылки на соседние сезоны.
        
        Возвращает slug'и соседних сезонов (например: "2022", "2024", "pl-2022").
        """
        prev_season = ""
        next_season = ""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем ссылки с "< сезон" или "сезон >"
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text().strip()
            
            if not href:
                continue
            
            # Извлекаем slug из href (последний элемент пути без .html)
            slug = href.rstrip('/').split('/')[-1].replace('.html', '')
            
            # Проверяем что это ссылка на сезон (содержит год)
            if not re.search(r'\d{4}', slug):
                continue
            
            # Проверяем направление по тексту ссылки
            if '<' in text:
                if not prev_season:
                    prev_season = slug
            elif '>' in text:
                if not next_season:
                    next_season = slug
        
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
            'hosts': season.hosts,
            'host': season.host,  # Deprecated
            'description': season.description,
            'intro_html': season.intro_html,
            'extra_sections': season.extra_sections,
            'metadata': season.metadata,
            'prev_season': season.prev_season,
            'next_season': season.next_season,
            'late_joined_teams': season.late_joined_teams,  # Команды, присоединившиеся позже
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
                                    'is_additional': t.is_additional,
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

