#!/usr/bin/env python3
"""
Скрипт для миграции изображений из frontend/public/media/imported/images 
в Docker volume imported_images_volume.

Использование:
    python scripts/migrate_images_to_volume.py

Требования:
    - Docker должен быть запущен
    - Контейнер humorpedia-backend должен быть запущен
    - Исходная директория frontend/public/media/imported/images должна существовать
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Tuple

# Константы
CONTAINER_NAME = "humorpedia-backend"
SOURCE_DIR = Path("frontend/public/media/imported/images")
VOLUME_MOUNT_PATH = "/app/frontend/public/media/imported/images"


def run_command(cmd: list, check: bool = True) -> Tuple[int, str, str]:
    """Выполнить команду и вернуть код возврата, stdout и stderr"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def check_docker_running() -> bool:
    """Проверить, запущен ли Docker"""
    code, _, _ = run_command(["docker", "info"], check=False)
    return code == 0


def check_container_running() -> bool:
    """Проверить, запущен ли контейнер backend"""
    code, stdout, _ = run_command(
        ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
        check=False
    )
    return code == 0 and CONTAINER_NAME in stdout


def check_source_directory() -> bool:
    """Проверить существование исходной директории"""
    return SOURCE_DIR.exists() and SOURCE_DIR.is_dir()


def count_files(directory: Path) -> int:
    """Подсчитать количество файлов в директории рекурсивно"""
    count = 0
    for root, dirs, files in os.walk(directory):
        count += len(files)
    return count


def migrate_files() -> bool:
    """Выполнить миграцию файлов в volume"""
    print(f"\n{'='*60}")
    print("Начало миграции изображений в Docker volume")
    print(f"{'='*60}\n")
    
    # Проверки
    print("1. Проверка Docker...")
    if not check_docker_running():
        print("   ❌ Ошибка: Docker не запущен или недоступен")
        return False
    print("   ✓ Docker запущен")
    
    print("\n2. Проверка контейнера backend...")
    if not check_container_running():
        print(f"   ❌ Ошибка: Контейнер {CONTAINER_NAME} не запущен")
        print(f"   💡 Запустите контейнер: docker-compose up -d backend")
        return False
    print(f"   ✓ Контейнер {CONTAINER_NAME} запущен")
    
    print("\n3. Проверка исходной директории...")
    if not check_source_directory():
        print(f"   ❌ Ошибка: Исходная директория не найдена: {SOURCE_DIR}")
        print(f"   💡 Убедитесь, что путь правильный относительно корня проекта")
        return False
    
    file_count = count_files(SOURCE_DIR)
    print(f"   ✓ Исходная директория найдена: {SOURCE_DIR.absolute()}")
    print(f"   ✓ Найдено файлов: {file_count}")
    
    if file_count == 0:
        print("   ⚠️  Предупреждение: Исходная директория пуста")
        response = input("   Продолжить миграцию? (y/n): ")
        if response.lower() != 'y':
            return False
    
    # Проверка целевой директории в контейнере
    print("\n4. Проверка целевой директории в контейнере...")
    code, stdout, stderr = run_command(
        ["docker", "exec", CONTAINER_NAME, "test", "-d", VOLUME_MOUNT_PATH],
        check=False
    )
    
    if code != 0:
        print(f"   ⚠️  Целевая директория не существует, создаем...")
        code, _, _ = run_command(
            ["docker", "exec", CONTAINER_NAME, "mkdir", "-p", VOLUME_MOUNT_PATH],
            check=False
        )
        if code != 0:
            print(f"   ❌ Ошибка: Не удалось создать целевую директорию")
            return False
        print(f"   ✓ Целевая директория создана")
    else:
        # Проверяем, не пуста ли целевая директория
        code, stdout, _ = run_command(
            ["docker", "exec", CONTAINER_NAME, "sh", "-c", f"find {VOLUME_MOUNT_PATH} -type f | wc -l"],
            check=False
        )
        if code == 0:
            existing_count = int(stdout.strip()) if stdout.strip().isdigit() else 0
            if existing_count > 0:
                print(f"   ⚠️  В целевой директории уже есть {existing_count} файлов")
                response = input("   Продолжить миграцию? Существующие файлы будут перезаписаны (y/n): ")
                if response.lower() != 'y':
                    return False
    
    # Копирование файлов
    print("\n5. Копирование файлов в volume...")
    print(f"   Источник: {SOURCE_DIR.absolute()}")
    print(f"   Назначение: {CONTAINER_NAME}:{VOLUME_MOUNT_PATH}")
    print("   Это может занять некоторое время...\n")
    
    source_abs = SOURCE_DIR.absolute()
    
    try:
        # Используем tar для более эффективного копирования
        print("   Используем tar для копирования...")
        
        # Создаем tar архив из содержимого исходной директории
        # Копируем содержимое директории images, а не саму директорию
        tar_cmd = ["tar", "-czf", "-", "-C", str(source_abs), "."]
        tar_process = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Передаем tar в контейнер и распаковываем прямо в VOLUME_MOUNT_PATH
        docker_cmd = [
            "docker", "exec", "-i", CONTAINER_NAME,
            "sh", "-c", f"cd {VOLUME_MOUNT_PATH} && tar -xzf -"
        ]
        docker_process = subprocess.Popen(
            docker_cmd,
            stdin=tar_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        tar_process.stdout.close()
        
        stdout, stderr = docker_process.communicate()
        
        if docker_process.returncode != 0:
            print(f"   ❌ Ошибка при копировании файлов:")
            print(f"   {stderr.decode('utf-8', errors='ignore')}")
            if tar_process.returncode != 0:
                _, tar_stderr = tar_process.communicate()
                print(f"   Ошибка создания tar: {tar_stderr.decode('utf-8', errors='ignore')}")
            return False
        
        print("   ✓ Файлы успешно скопированы")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Проверка результата
    print("\n6. Проверка результата миграции...")
    code, stdout, _ = run_command(
        ["docker", "exec", CONTAINER_NAME, "sh", "-c", f"find {VOLUME_MOUNT_PATH} -type f | wc -l"],
        check=False
    )
    
    if code == 0:
        migrated_count = int(stdout.strip()) if stdout.strip().isdigit() else 0
        print(f"   ✓ Файлов в volume: {migrated_count}")
        
        if migrated_count < file_count:
            print(f"   ⚠️  Предупреждение: Скопировано меньше файлов, чем было в исходной директории")
            print(f"   Исходных: {file_count}, Скопировано: {migrated_count}")
        else:
            print(f"   ✓ Миграция завершена успешно!")
    else:
        print("   ⚠️  Не удалось проверить количество файлов в volume")
    
    return True


def main():
    """Главная функция"""
    # Определяем корень проекта (на уровень выше scripts)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    # Переходим в корень проекта
    os.chdir(project_root)
    
    print(f"Рабочая директория: {os.getcwd()}")
    
    success = migrate_files()
    
    if success:
        print(f"\n{'='*60}")
        print("✅ Миграция завершена успешно!")
        print(f"{'='*60}")
        print("\nСледующие шаги:")
        print("1. Проверьте доступность изображений через /media/imported/images/*")
        print("2. Протестируйте загрузку новых файлов через веб-интерфейс")
        print("3. После проверки можно удалить старую директорию:")
        print(f"   {SOURCE_DIR.absolute()}")
        return 0
    else:
        print(f"\n{'='*60}")
        print("❌ Миграция не завершена")
        print(f"{'='*60}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
