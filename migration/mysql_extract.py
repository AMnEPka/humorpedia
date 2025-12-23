#!/usr/bin/env python3
"""
Прямой парсинг MySQL INSERT statements для извлечения человека
"""
import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Function
from sqlparse.tokens import Keyword, DML

# Use mysql client directly
import subprocess
import json

def extract_using_mysql():
    """Use MySQL directly to parse the dump"""
    
    # Create temporary MySQL database
    print("Создаём временную MySQL базу...")
    
    commands = [
        "mysql -e 'DROP DATABASE IF EXISTS temp_modx'",
        "mysql -e 'CREATE DATABASE temp_modx CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'",
        "mysql temp_modx < /app/modx_dump.sql 2>&1 | head -20"
    ]
    
    for cmd in commands:
        print(f"Выполняем: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0 and "CREATE DATABASE" not in cmd:
            print(f"Ошибка: {result.stderr[:200]}")
    
    print("\n✅ База создана")
    
    # Query person
    print("\nЗапрашиваем человека ID=350...")
    
    query = """
    SELECT 
        id, pagetitle, alias, introtext, content, 
        published, template, uri, createdon, editedon
    FROM modx_site_content 
    WHERE id=350
    """
    
    result = subprocess.run(
        f"mysql -e '{query}' temp_modx",
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("Результат:")
        print(result.stdout)
    else:
        print(f"Ошибка: {result.stderr}")
    
    # Query TV values
    print("\nЗапрашиваем TV values...")
    
    query_tv = """
    SELECT tmplvarid, value
    FROM modx_site_tmplvar_contentvalues
    WHERE contentid=350
    """
    
    result_tv = subprocess.run(
        f"mysql -e '{query_tv}' temp_modx",
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result_tv.returncode == 0:
        print("TV Values:")
        print(result_tv.stdout)

if __name__ == "__main__":
    extract_using_mysql()
