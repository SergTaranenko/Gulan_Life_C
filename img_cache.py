# -*- coding: utf-8 -*-
"""
img_cache.py — кэш картинок GigaChat.
Каждый второй запрос отдаёт случайную картинку из папки вместо генерации.
Использование в core: заменить `gigachat.generate_image(prompt)`
на `cached_image(gigachat, prompt)`.
"""
import random
import time
from pathlib import Path

IMG_DIR = Path("/app/data/img")
MAX_FILES = 300
_counter = {"n": 0}

def _saved():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(IMG_DIR.glob("*.jpg"))

async def cached_image(gigachat, prompt: str):
    _counter["n"] += 1
    files = _saved()
    # чётный вызов — дубль из папки, если есть что показать
    if _counter["n"] % 2 == 0 and files:
        try:
            return random.choice(files).read_bytes()
        except Exception:
            pass
    img = await gigachat.generate_image(prompt)
    if img:
        try:
            (IMG_DIR / f"{int(time.time())}_{random.randint(100, 999)}.jpg").write_bytes(img)
            files = _saved()
            for old in files[:-MAX_FILES]:
                old.unlink(missing_ok=True)
        except Exception:
            pass
        return img
    # генерация не удалась — отдать любую сохранённую
    return random.choice(files).read_bytes() if files else None
