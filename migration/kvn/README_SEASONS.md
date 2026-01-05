# Парсер сезонов КВН

## Обзор

Модуль `parsers/kvn_season.py` предназначен для автоматического парсинга HTML-контента страниц сезонов КВН и извлечения структурированной информации:

- Стадии сезона (1/8, 1/4, 1/2, финал)
- Игры внутри каждой стадии
- Команды-участники и их результаты
- Баллы по конкурсам
- Жюри и ведущих
- Даты игр

## Быстрый старт

```python
from parsers.kvn_season import KVNSeasonParser

parser = KVNSeasonParser()
html = "<div>...</div>"  # HTML контент сезона

result = parser.parse(html, league="premier-liga", year=2023)
print(f"Стадий: {len(result.stages)}")
print(f"Победители: {result.winners}")
```

## Архитектура модуля

```
KVNSeasonParser          - Главный класс парсера сезона
├── _parse_metadata()    - Парсит общую информацию (редакторы, ведущие)
├── _split_into_stages() - Разбивает HTML на стадии
└── to_dict()           - Конвертирует результат в словарь

StageParser             - Парсер одной стадии
├── parse()             - Парсит стадию
├── _split_into_games() - Разбивает стадию на игры
└── _find_additional()  - Находит добор

GameParser              - Парсер одной игры
├── parse()             - Парсит игру
├── _find_game_header() - Находит заголовок и дату
├── _parse_date()       - Парсит дату в ISO формат
├── _parse_text_results() - Парсит результаты из текста (если нет таблицы)
├── _find_jury()        - Находит жюри
├── _find_host()        - Находит ведущего
└── _detect_passed_teams() - Определяет прошедшие команды

TableParser             - Парсер таблиц результатов
└── parse()             - Парсит HTML-таблицу
```

## Модели данных

### SeasonData
Полная информация о сезоне:
```python
@dataclass
class SeasonData:
    league_slug: str       # Slug лиги (например, "premier-liga")
    league_name: str       # Название лиги
    year: int             # Год сезона
    all_teams: List[str]  # Все команды-участники (slug)
    stages: List[Stage]   # Стадии сезона
    winners: List[str]    # Победители (slug)
    jury: List[str]       # Члены жюри
    editors: List[str]    # Редакторы
    host: str             # Ведущий
```

### Stage
Стадия сезона:
```python
@dataclass
class Stage:
    name: str             # "1/8 финала", "1/4 финала", итд
    order: int            # 1, 2, 3, 4 (1/8, 1/4, 1/2, финал)
    games: List[Game]     # Игры стадии
    additional_teams: List[str]  # Команды, прошедшие добором
    additional_notes: str  # Комментарий к добору
```

### Game
Одна игра:
```python
@dataclass
class Game:
    id: str               # Уникальный ID
    name: str             # "Первая 1/8 финала"
    order: int            # Номер игры в стадии
    date: str             # ISO дата (2023-03-27)
    date_raw: str         # Оригинальная дата из HTML
    teams: List[TeamScore]  # Результаты команд
    contests: List[str]   # Названия конкурсов
    jury: List[str]       # Жюри этой игры
    host: str             # Ведущий игры
    notes: str            # Доп. информация
    is_cancelled: bool    # Отменена ли игра
```

### TeamScore
Результаты команды:
```python
@dataclass
class TeamScore:
    team_slug: str        # Slug команды
    team_name: str        # Название
    team_link: str        # Ссылка на страницу
    place: int            # Место в игре
    scores: Dict[str, float]  # Баллы по конкурсам
    total: float          # Итоговый балл
    passed: bool          # Прошла в следующий этап
    is_winner: bool       # Победитель (только для финала)
    city: str             # Город
```

## Паттерны парсинга

### Добавление нового паттерна стадии

Паттерны стадий определены в `STAGE_PATTERNS`:

```python
STAGE_PATTERNS = [
    (r'\b1/8\s*финал[аеы]?\b', '1/8 финала', 1),
    (r'\b1/4\s*финал[аеы]?\b', '1/4 финала', 2),
    # ...
]
```

Формат: `(regex_pattern, stage_name, stage_order)`

**Чтобы добавить новую стадию:**

1. Откройте `parsers/kvn_season.py`
2. Найдите `STAGE_PATTERNS`
3. Добавьте новый паттерн в нужное место (более специфичные сначала!)

```python
# Пример: добавление "Музыкального фестиваля"
STAGE_PATTERNS = [
    # ... существующие паттерны ...
    (r'\bМузыкальн\w+\s+фестивал[ья]?\b', 'Музыкальный фестиваль', 7),
]
```

### Добавление нового паттерна игры

Паттерны игр в `GAME_PATTERNS`:

```python
GAME_PATTERNS = [
    (r'(Перв(?:ая|ый|ое))\s*(?:игра\s+)?...', 1),
    (r'(Втор(?:ая|ой|ое))\s*(?:игра\s+)?...', 2),
    # ...
]
```

### Добавление нового формата даты

Паттерны дат в `DATE_PATTERNS`:

```python
DATE_PATTERNS = [
    r'(\d{1,2})\s*(январ[яьи]|...|декабр[яьи])\s*(\d{4})?',  # 27 марта 2023
    r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # 27.03.2023
    r'(\d{1,2})/(\d{1,2})/(\d{4})',    # 27/03/2023
]
```

**Чтобы добавить новый формат:**

```python
DATE_PATTERNS = [
    # ... существующие ...
    r'(\d{4})-(\d{2})-(\d{2})',  # ISO формат: 2023-03-27
]
```

И обновите метод `_parse_date()` в `GameParser`.

### Добавление нового паттерна результата

Паттерны результатов (прошли/выбыли):

```python
RESULT_PATTERNS = [
    (r'прош[её]?л[иа]?', 'passed'),
    (r'выш[её]?л[иа]?', 'passed'),
    (r'не\s*прош[её]?л[иа]?', 'eliminated'),
    (r'победител[ьяи]', 'winner'),
]
```

## Обработка особых случаев

### Сезоны без стадий (одна игра)

Если в HTML нет заголовков стадий, парсер создаст одну стадию "Основная игра" и попытается распарсить результаты.

Пример: `kvn/1l-kvn/1l-1993`

### Отменённые игры (COVID)

Если стадия отменена, добавьте обработку в `_parse_special_cases()`:

```python
def _parse_special_cases(self, html: str, stage: Stage) -> None:
    if 'отменен' in html.lower() or 'пандем' in html.lower():
        stage.notes = "Стадия отменена"
        for game in stage.games:
            game.is_cancelled = True
```

### Несколько победителей

Если в финале несколько победителей (как в 2020), все команды с `is_winner=True` попадут в `winners`.

### Добор

Информация о доборе автоматически извлекается после каждой стадии. Команды, прошедшие добором, записываются в `stage.additional_teams`.

## CLI для тестирования

```bash
# Тестирование на конкретном сезоне
python parsers/kvn_season.py kvn/premier-liga/2023

# Результат сохраняется в JSON
# season_premier-liga_2023.json
```

## Интеграция с universal_importer.py

Для использования в процессе импорта:

```python
from parsers.kvn_season import KVNSeasonParser

def process_season(season_doc):
    """Обрабатывает документ сезона из MongoDB."""
    # Получаем HTML из текстовых модулей
    text_modules = [m for m in season_doc.get('modules', []) 
                    if m.get('type') == 'text_block']
    
    html = ""
    for m in text_modules:
        html += m.get('data', {}).get('content', '') + "\n"
    
    # Парсим
    parser = KVNSeasonParser()
    
    # Извлекаем лигу и год из пути
    path = season_doc.get('full_path', '')
    path_parts = path.split('/')
    league = path_parts[1] if len(path_parts) > 1 else ''
    year = extract_year(path_parts[-1])
    
    result = parser.parse(html, league=league, year=year)
    
    # Обновляем документ структурированными данными
    season_doc['season_data'] = parser.to_dict(result)
    
    return season_doc
```

## Расширение модуля

### Добавление нового типа элемента

1. Создайте новую модель данных (dataclass)
2. Добавьте парсер для этого элемента
3. Интегрируйте в основной парсер

### Добавление валидации

```python
class KVNSeasonParser:
    def validate(self, result: SeasonData) -> List[str]:
        """Валидирует результат парсинга."""
        errors = []
        
        if not result.stages:
            errors.append("Не найдено ни одной стадии")
        
        for stage in result.stages:
            if not stage.games:
                errors.append(f"Стадия '{stage.name}' не содержит игр")
            
            for game in stage.games:
                if not game.teams:
                    errors.append(f"Игра '{game.name}' не содержит команд")
        
        return errors
```

## Известные ограничения

1. **Разные форматы HTML** - старые сезоны могут иметь нестандартную разметку
2. **Отсутствие ссылок на команды** - если команды указаны без ссылок, slug не определится
3. **Неполные данные** - некоторые сезоны содержат только частичную информацию
4. **Кодировка** - убедитесь, что HTML корректно декодирован в UTF-8

## FAQ

**Q: Парсер не находит стадии**
A: Проверьте, в каких тегах указаны названия стадий. Добавьте нужные теги в поиск в `_split_into_stages()`.

**Q: Не определяются прошедшие команды**
A: Команды могут быть выделены другим способом (цвет, стиль). Добавьте обработку в `_detect_passed_teams()`.

**Q: Не парсятся даты**
A: Добавьте паттерн для нового формата даты в `DATE_PATTERNS` и обновите `_parse_date()`.

