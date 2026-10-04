# -*- coding: utf-8 -*-
"""
sower.py — PATCH-9: житница, семена, «заболел», сериал роликов.
Чистые функции над data/rank, как stones.py. Ядро только вызывает их.

Ключи в path_data.json (добавляются сами, старые не трогаются):
  granary          — житница, руб. (старт 90 000, +3 000 за поле)
  granary_fields   — сколько полей оплачено
  seeds            — сумка семян: [{"d": "2026-10-05", "t": "ТО-3 у дилера 38 тыс"}]
  seeds_rank       — семян за текущий ранг
  waiting_for_seed — ждём текст семени после кнопки
  sick_date        — дата больничного (строка) или None
  video_idx        — {"8": 2} — сколько серий уже показано в ранге (ключ = rank_index)
  video_file_ids   — {"r09_4.mp4": "BAACAg..."} — file_id Telegram после первой отправки
"""
import random
from datetime import timedelta
from pathlib import Path

MEDIA_DIR = Path("/app/data/media")   # в volume рядом с img/ — переживает редеплой

GRANARY_START = 90000
FIELD_BONUS   = 3000

KEYS = {
    "granary": GRANARY_START,
    "granary_fields": 0,
    "seeds": [],
    "seeds_rank": 0,
    "waiting_for_seed": False,
    "sick_date": None,
    "video_idx": {},
    "video_file_ids": {},
}

def ensure_keys(data: dict):
    for k, v in KEYS.items():
        if k not in data:
            data[k] = v if not isinstance(v, (dict, list)) else type(v)(v)

def fmt(n) -> str:
    return f"{int(n):,}".replace(",", " ")

# ── Житница ────────────────────────────────────────────────────────────────
def on_done(data: dict, rank: dict):
    """Поле засеяно → +взнос в житницу. Возвращает текст или None (ранг без житницы)."""
    ensure_keys(data)
    bonus = rank.get("field_bonus")
    if not bonus:
        return None
    data["granary"] += bonus
    data["granary_fields"] += 1
    line = random.choice(rank.get("granary_lines", ["🌾 +{bonus} ₽ в житницу → {total} ₽. Переведи сейчас."]))
    return line.format(bonus=fmt(bonus), total=fmt(data["granary"]), fields=data["granary_fields"])

def granary_text(data: dict, rank: dict) -> str:
    ensure_keys(data)
    bonus = rank.get("field_bonus", FIELD_BONUS)
    return (
        f"🌾 ЖИТНИЦА\n\n"
        f"В закромах: {fmt(data['granary'])} ₽\n"
        f"Оплачено полей: {data['granary_fields']} × {fmt(bonus)} ₽\n"
        f"Семян в сумке: {len(data['seeds'])} (за ранг {data['seeds_rank']})\n\n"
        f"Поправить вручную: /granary 95000"
    )

def set_granary(data: dict, amount: int) -> str:
    ensure_keys(data)
    old = data["granary"]
    data["granary"] = int(amount)
    return f"🌾 Житница: {fmt(old)} → {fmt(amount)} ₽."

def status_line(data: dict, rank: dict):
    ensure_keys(data)
    if not rank.get("field_bonus"):
        return None
    return f"🌾 Житница: {fmt(data['granary'])} ₽ · семян {data['seeds_rank']}"

# ── Семена ─────────────────────────────────────────────────────────────────
def seed_prompt(rank: dict):
    cats = rank.get("seed_categories")
    if not cats:
        return None
    return f"🌱 Семя: {random.choice(cats)}\n{rank.get('seed_rule', '15 минут · вопрос с числом · строка в сумку: /seed …')}"

def add_seed(data: dict, text: str, today: str) -> str:
    ensure_keys(data)
    text = text.strip()[:200]
    data["seeds"].append({"d": today, "t": text})
    data["seeds_rank"] += 1
    data["waiting_for_seed"] = False
    return f"🌱 В сумку: «{text}»\nСемян за ранг: {data['seeds_rank']} · всего {len(data['seeds'])}"

def bag_text(data: dict, n: int = 10) -> str:
    ensure_keys(data)
    seeds = data["seeds"]
    if not seeds:
        return "🎒 Сумка пуста. Борозда → 15 минут → /seed вопрос и число."
    lines = [f"🎒 СУМКА СЕМЯН — {len(seeds)} шт., последние {min(n, len(seeds))}:\n"]
    for s in seeds[-n:]:
        lines.append(f"• {s['d'][5:]} — {s['t']}")
    return "\n".join(lines)

def on_rank_change(data: dict):
    ensure_keys(data)
    data["seeds_rank"] = 0

# ── Заболел ────────────────────────────────────────────────────────────────
def mark_sick(data: dict, rank: dict, now, last_deed_time_iso: str, tz) -> tuple:
    """Больничный на сегодня: голод молчит, серия не сбрасывается. Возвращает (текст, новый last_deed_time)."""
    ensure_keys(data)
    from datetime import datetime
    data["sick_date"] = now.date().isoformat()
    data["hunger_notified"] = False
    last = datetime.fromisoformat(last_deed_time_iso) if last_deed_time_iso else now
    if last.tzinfo is None:
        last = tz.localize(last)
    new_last = (max(last, now) + timedelta(hours=24)).isoformat()
    text = rank.get("sick_text", "🤒 Заболел. Сегодня племя тебя не трогает: голод спит, серия цела. Лечись.")
    return text, new_last

def is_sick(data: dict, today: str) -> bool:
    return data.get("sick_date") == today

# ── Сериал роликов ─────────────────────────────────────────────────────────
def next_video(data: dict, rank: dict, rank_index: int):
    """Каждое N-е дело ранга → следующая серия по сюжету. После последней — повтор с пометкой.
    Возвращает (Path, caption) или None."""
    ensure_keys(data)
    videos = rank.get("videos")
    if not videos:
        return None
    every = rank.get("video_every", 2)
    deeds = data.get("rank_deeds", 0)
    if deeds <= 0 or deeds % every != 0:
        return None
    key = str(rank_index)
    i = data["video_idx"].get(key, 0)
    if i < len(videos):
        fname, cap = videos[i]
        data["video_idx"][key] = i + 1
        caption = f"🎬 Серия {i+1}/{len(videos)} · {cap}"
    else:
        fname, cap = random.choice(videos)
        caption = f"🎬 Путь до сих пор · {cap}"
    return MEDIA_DIR / fname, caption

def rollback_video(data: dict, rank_index: int):
    """Ролик не ушёл — серию не считаем показанной."""
    key = str(rank_index)
    if data.get("video_idx", {}).get(key, 0) > 0:
        data["video_idx"][key] -= 1

async def send_video(bot, chat_id: int, data: dict, path: Path, caption: str) -> bool:
    """Шлёт ролик: сначала по file_id (мгновенно), иначе файлом с диска и запоминает file_id."""
    ensure_keys(data)
    fid = data["video_file_ids"].get(path.name)
    try:
        if fid:
            await bot.send_video(chat_id=chat_id, video=fid, caption=caption)
            return True
    except Exception:
        pass
    if not path.exists():
        return False
    try:
        with open(path, "rb") as f:
            msg = await bot.send_video(chat_id=chat_id, video=f, caption=caption,
                                       supports_streaming=True, read_timeout=120, write_timeout=120)
        if msg and msg.video:
            data["video_file_ids"][path.name] = msg.video.file_id
        return True
    except Exception:
        return False
