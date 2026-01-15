# Настройка Docker Volume для изображений сайта

## Описание

В медиабиблиотеке админки теперь можно просматривать файлы из Docker volume, который содержит изображения сайта (например, `/images/kvn-team/maximum.jpg`).

## Настройка на продакшене

### 1. Подключение существующего volume

Если у вас уже есть volume с изображениями, подключите его к контейнеру backend:

```yaml
# В docker-compose.yml или docker-compose.prod.yml
services:
  backend:
    volumes:
      - images_volume:/app/images:ro
```

И создайте volume, если его еще нет:

```bash
docker volume create images_volume
```

### 2. Копирование файлов в volume

Если файлы находятся на хосте, скопируйте их в volume:

```bash
# Найти путь к volume
docker volume inspect images_volume

# Скопировать файлы (пример)
docker run --rm -v images_volume:/data -v /path/to/your/images:/source alpine \
  sh -c "cp -r /source/* /data/"
```

Или подключите директорию напрямую:

```yaml
services:
  backend:
    volumes:
      - /path/to/your/images:/app/images:ro
```

### 3. Проверка

После перезапуска контейнеров:

1. Откройте админку: http://127.0.0.1:3000/admin/media
2. Перейдите на вкладку "Изображения сайта"
3. Вы должны увидеть файлы из volume

## Структура директорий

Файлы должны быть организованы в папках, например:
```
/app/images/
  ├── kvn-team/
  │   ├── maximum.jpg
  │   └── ...
  ├── people/
  │   └── ...
  └── ...
```

## Доступ к файлам

После настройки файлы будут доступны по URL:
- `https://humorpedia.ru/images/kvn-team/maximum.jpg`
- `https://humorpedia.ru/images/people/...`

## Примечания

- Volume монтируется в режиме read-only (`:ro`) для безопасности
- Backend автоматически раздает файлы из `/app/images` по пути `/images/*`
- В медиабиблиотеке можно навигироваться по папкам и искать файлы
