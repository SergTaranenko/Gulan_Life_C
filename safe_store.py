# -*- coding: utf-8 -*-
"""
safe_store.py — PATCH-10: защита файлов прогресса от обнуления.

Что было 16.10.2026: бот лёг 15.10 ~14:00 и поднялся 16.10 ~09:20 с пустым файлом;
старый load_data молча вернул «нулевой» прогресс, следующий save_data затёр файл,
а переходы рангов начислили долг 126 (6×17 + 2×12).

Что делает модуль:
  1. atomic_write_json — сначала json в строку (если не сериализуется — файл не трогаем),
     потом запись во временный файл и подмена одним шагом. Обрыв на середине записи
     больше не оставляет обрезанный файл.
  2. daily_backup — раз в день копия в data/backups/<имя>_<дата>.json, хранится 30 копий.
  3. safe_load — если файл испорчен: кладёт его рядом как .broken-<время> (не удаляет!),
     берёт свежую исправную копию из backups/ или недописанный .tmp. Если файла нет —
     тоже пробует копию. О каждом таком случае копит событие для сообщения в чат.
  4. guarded_save — не даёт записать прогресс «назад»: если в новом состоянии
     total_deeds / rank_index (или rev у привычек) меньше, чем в файле, запись отклоняется,
     отклонённое состояние сохраняется рядом как .rejected-<время>, в чат идёт предупреждение.
     Сознательный откат — только force=True (команда восстановления).
  5. bundle / parse_restore — копия файлов в Telegram и восстановление из присланного файла.
"""

import json
import os
import shutil
import time
import logging
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)

KEEP_BACKUPS = 30
_events: list = []          # сообщения для пользователя, ядро забирает через pop_events()


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _event(text: str):
    logger.error("[SAFE] " + text)
    _events.append(text)


def pop_events() -> list:
    out = list(_events)
    _events.clear()
    return out


def _read(p: Path):
    """dict или None, без исключений."""
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def backup_dir(path: Path) -> Path:
    return Path(path).parent / "backups"


def atomic_write_json(path, obj) -> bool:
    path = Path(path)
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception as e:
        _event(f"⚠️ Не смог сохранить {path.name}: данные не превращаются в JSON ({e}). Файл не тронут.")
        return False
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except Exception as e:
        logger.error(f"[SAFE] write {path}: {e}")
        global _last_write_fail
        if time.time() - _last_write_fail > 3600:          # в чат — не чаще раза в час
            _last_write_fail = time.time()
            _event(f"⚠️ Не могу записать {path.name}: {e}. Старый файл цел. "
                   f"Если ошибка про место (No space left) — на сервере кончился диск.")
        return False


_last_write_fail = 0.0


def disk_free_mb(path) -> int:
    try:
        return int(shutil.disk_usage(Path(path)).free / 1024 / 1024)
    except Exception:
        return -1


def daily_backup(path, today: date = None) -> bool:
    """Копия раз в день. Возвращает True, если копия сделана сейчас."""
    path = Path(path)
    today = today or date.today()
    target = backup_dir(path) / f"{path.stem}_{today.isoformat()}.json"
    if target.exists():                      # сегодняшняя копия уже есть — файл не читаем
        return False
    if not path.exists() or _read(path) is None:
        return False
    backup_dir(path).mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    olds = sorted(bdir.glob(f"{path.stem}_????-??-??.json"))
    for old in olds[:-KEEP_BACKUPS]:
        try:
            old.unlink()
        except Exception:
            pass
    return True


def latest_backup(path):
    """(путь, dict) самой свежей исправной копии или (None, None)."""
    path = Path(path)
    bdir = backup_dir(path)
    if not bdir.exists():
        return None, None
    for p in sorted(bdir.glob(f"{path.stem}_????-??-??.json"), reverse=True):
        d = _read(p)
        if d is not None:
            return p, d
    return None, None


def safe_load(path, default_factory):
    """
    Возвращает (data, status):
      ok        — файл прочитан;
      tmp       — файл испорчен/пропал, взят недописанный .tmp;
      backup    — взята копия из backups/ (имя копии в событии);
      new       — файла и копий нет (первый запуск);
      lost      — файл был испорчен, копий нет: стартуем с нуля, испорченный лежит рядом.
    """
    path = Path(path)
    existed = path.exists()
    if existed:
        d = _read(path)
        if d is not None:
            return d, "ok"
        broken = path.with_name(f"{path.stem}.broken-{_now_tag()}{path.suffix}")
        try:
            shutil.move(str(path), str(broken))
        except Exception:
            pass
        _event(f"⚠️ Файл {path.name} испорчен. Сохранил его как {broken.name}.")

    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        d = _read(tmp)
        if d is not None:
            atomic_write_json(path, d)
            _event(f"♻️ {path.name} восстановлен из недописанной записи.")
            return d, "tmp"

    bpath, d = latest_backup(path)
    if d is not None:
        atomic_write_json(path, d)
        _event(f"♻️ {path.name} восстановлен из копии {bpath.name}. "
               f"Дела после этой копии, если были, нужно отметить заново.")
        return d, "backup"

    if existed:
        _event(f"🚨 {path.name} испорчен, а копий нет. Начинаю с нуля; испорченный файл лежит рядом — "
               f"пришлите его в чат по сборке, достану, что уцелело.")
        return default_factory(), "lost"
    return default_factory(), "new"


def _regressed(old: dict, new: dict, keys) -> list:
    bad = []
    for k in keys:
        a, b = old.get(k), new.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b < a:
            bad.append(f"{k}: {a} → {b}")
    return bad


def guarded_save(path, obj, guard_keys=("total_deeds", "rank_index"), force=False) -> bool:
    path = Path(path)
    if not force and path.exists():
        old = _read(path)
        if old is not None:
            bad = _regressed(old, obj, guard_keys)
            if bad:
                big = any((isinstance(obj.get(k), (int, float)) and obj.get(k) == 0 and old.get(k)) or
                          (isinstance(obj.get(k), (int, float)) and isinstance(old.get(k), (int, float))
                           and old[k] - obj[k] > 3)
                          for k in guard_keys)
                if big:
                    # крупный откат (обнуление) — сохраняем попытку рядом и пишем в чат
                    rej = path.with_name(f"{path.stem}.rejected-{_now_tag()}{path.suffix}")
                    atomic_write_json(rej, obj)
                    _event("🛑 Не дал записать прогресс назад (" + "; ".join(bad) +
                           f"). Файл не тронут, попытка лежит в {rej.name}.")
                else:
                    # мелкий откат — устаревшая копия от двух нажатий подряд; молча не пускаем
                    logger.warning("[SAFE] stale save skipped: " + "; ".join(bad))
                return False
    return atomic_write_json(path, obj)


# ── Копия в Telegram и восстановление из файла ────────────────────────────────
def bundle(paths) -> list:
    """[(имя, bytes)] для отправки документами. Пропускает отсутствующие и испорченные."""
    out = []
    for p in map(Path, paths):
        if p.exists() and _read(p) is not None:
            out.append((p.name, p.read_bytes()))
    return out


def parse_restore(filename: str, raw: bytes, allowed: dict):
    """
    allowed: {имя_файла: Path}. Возвращает (Path, dict) или бросает ValueError с понятным текстом.
    Имя принимается и с датой копии: path_data_2026-10-15.json → path_data.json.
    """
    name = Path(filename).name
    target = allowed.get(name)
    if target is None:
        for key, p in allowed.items():
            stem = Path(key).stem
            if name.startswith(stem + "_") and name.endswith(".json"):
                target = p
                break
    if target is None:
        raise ValueError("не знаю такой файл: " + name + ". Жду " + ", ".join(allowed))
    try:
        d = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"файл не читается как JSON ({e})")
    if not isinstance(d, dict):
        raise ValueError("внутри не тот формат")
    return target, d
