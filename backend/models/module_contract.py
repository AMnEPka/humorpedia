"""Реестр модулей; JSON также поставляется во frontend и проверяется в CI."""
import json
from pathlib import Path

MODULE_CONTRACT = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
