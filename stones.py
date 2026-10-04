# -*- coding: utf-8 -*-
"""
stones.py — камни, слоты, гимн, шмотка, сцены для ранга 8+.
Чистые функции: получают data/rank, меняют счётчики, возвращают текст.
Ядро только вызывает их в нужных местах.
"""
import random

STONE_KEYS = {
    "stones_total": 0,        # камней за весь путь
    "stones_rank": 0,         # камней за текущий ранг
    "stones_today": 0,
    "stones_in_deed": 0,      # камней в текущей кладке (0..5)
    "stones_slots": {"morning": 0, "day": 0, "evening": 0},   # за ранг
}

def ensure_keys(data: dict):
    for k, v in STONE_KEYS.items():
        if k not in data:
            data[k] = v if not isinstance(v, dict) else dict(v)

def slot_of(hour: int, rank: dict) -> str:
    s = rank.get("slots", {"morning_until": 10, "evening_from": 17})
    if hour < s["morning_until"]:
        return "morning"
    if hour >= s["evening_from"]:
        return "evening"
    return "day"

def bricks(n: int, total: int = 5) -> str:
    n = max(0, min(n, total))
    return "▮" * n + "▯" * (total - n)

def wall_bar(deeds: int, needed: int, icon: str = "🧱") -> str:
    """Стена ранга: каждая кладка — кирпич. PATCH-9: значок из ранга."""
    needed = max(needed, 1)
    return icon * min(deeds, needed) + "▫️" * max(0, needed - deeds)

def add_stone(data: dict, rank: dict, hour: int, deeds: int, needed: int) -> str:
    ensure_keys(data)
    data["stones_total"] += 1
    data["stones_rank"] += 1
    data["stones_today"] += 1
    data["stones_in_deed"] = min(5, data["stones_in_deed"] + 1)
    data["stones_slots"][slot_of(hour, rank)] += 1
    phrase = random.choice(rank.get("step_phrases", ["Шаг сделан."]))
    inb = data["stones_in_deed"]
    w = rank.get("words", {})                                   # PATCH-9: словарь ранга
    step_w, group_w, wall_w = w.get("step", "Камень"), w.get("group", "Кладка"), w.get("wall", "Стена ранга")
    icon, five = w.get("icon", "🧱"), w.get("five", "Пять камней легли — нажми «⚒️ Сделано», чтобы закрыть кладку.")
    msg = (
        f"{icon} {phrase}\n\n"
        f"{step_w} {data['stones_rank']} · сегодня {data['stones_today']}\n"
        f"{group_w}: {bricks(inb)} {inb}/5"
    )
    if inb >= 5:
        msg += f"\n✅ {five}"
    msg += f"\n\n{wall_w}: {wall_bar(deeds, needed, w.get('wall_icon', '🧱'))} {deeds}/{needed}"
    return msg

def on_done(data: dict):
    ensure_keys(data)
    data["stones_in_deed"] = 0

def on_day_reset(data: dict):
    ensure_keys(data)
    data["stones_today"] = 0

def on_rank_change(data: dict):
    ensure_keys(data)
    data["stones_rank"] = 0
    data["stones_in_deed"] = 0
    data["stones_slots"] = {"morning": 0, "day": 0, "evening": 0}

def evening_line(data: dict, rank: dict, deeds: int, needed: int) -> str:
    ensure_keys(data)
    s = data["stones_slots"]
    w = rank.get("words", {})                                   # PATCH-9
    return (
        f"{w.get('icon', '🧱')} {rank['name']} — {w.get('plural', 'камни ранга')}\n"
        f"🌅 утро {s['morning']} · ☀️ день {s['day']} · 🌙 вечер {s['evening']}\n"
        f"Всего за ранг: {data['stones_rank']} · сегодня: {data['stones_today']}\n"
        f"{w.get('wall_short', 'Стена')}: {wall_bar(deeds, needed, w.get('wall_icon', '🧱'))} {deeds}/{needed}"
    )

def hymn(rank: dict) -> str:
    return random.choice(rank.get("hymn_lines", ["🎵 Включи мотивацию на телефоне."]))

def shmotka(rank: dict):
    lst = rank.get("shmotka")
    return random.choice(lst) if lst else None

def scene(rank: dict):
    scenes = rank.get("scenes")
    if scenes:
        return random.choice(scenes)
    return None, None
