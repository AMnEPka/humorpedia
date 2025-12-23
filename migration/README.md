# Скрипты миграции Humorpedia

## Описание

Набор скриптов для импорта данных из MODX SQL-дампа в MongoDB.

## Структура

```
/app/migration/
├── README.md              # Этот файл
├── import_people.py       # Импорт персон
├── extract_from_sql.py    # Извлечение данных из SQL через grep
├── import_images.py       # Импорт изображений
└── utils.py               # Общие утилиты
```

## Формат данных

### Персона (Person)
```json
{
    "_id": "uuid-string",
    "content_type": "person",
    "title": "Фамилия Имя",
    "slug": "slug-in-latin",
    "full_name": "Полное имя с отчеством",
    "status": "published",
    "tags": ["тег1", "тег2"],
    "bio": {
        "birth_date": "YYYY-MM-DD",
        "birth_place": "Город",
        "occupation": ["профессия1", "профессия2"],
        "achievements": ["достижение1"]
    },
    "social_links": {
        "vk": "url",
        "telegram": "url",
        "instagram": "url",
        "youtube": "url"
    },
    "modules": [
        {
            "id": "uuid",
            "type": "text_block",
            "order": 1,
            "visible": true,
            "data": {
                "title": "Биография",
                "content": "<p>HTML контент</p>"
            }
        },
        {
            "id": "uuid",
            "type": "timeline",
            "order": 2,
            "visible": true,
            "data": {
                "title": "Хронология",
                "events": [
                    {
                        "year": "2010-2013",
                        "title": "Заголовок события",
                        "description": "Описание"
                    }
                ]
            }
        }
    ],
    "rating": {
        "average": 4.5,
        "count": 10
    }
}
```

## Использование

### 1. Извлечение ID и рейтингов из SQL
```bash
# Найти ID персоны по имени
grep -o "([0-9]*,'document','text/html','Фамилия Имя" modx_new.sql

# Найти рейтинги для ID=148
grep -oE "\([0-9]+,148,[0-9]+,[0-9]+\)" modx_new.sql
```

### 2. Импорт персоны
```bash
cd /app/migration
python3 import_people.py --slug irina-chesnokova
```

### 3. Импорт изображений
```bash
python3 import_images.py --source ./images/ --dest /app/frontend/public/media/
```

## Требования

- Python 3.11+
- pymongo
- MongoDB доступен по MONGO_URL
