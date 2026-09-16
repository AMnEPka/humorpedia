import sys
from pathlib import Path

# Тесты запускаются из каталога backend (как и сервер): pytest tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
