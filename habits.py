# -*- coding: utf-8 -*-
"""
habits.py — PATCH-10: привычки по одной, утренний диалог, воскресный вопрос, копилка идей.
ТЗ: claude/TZ_bot_privychki.md (сессия 8, 16.10.2026).

Своё хранилище: /app/data/habits_data.json — отдельно от path_data.json, через safe_store
(атомарная запись, ежедневная копия, защита от отката по счётчику rev).

Модуль ничего не отправляет сам: функции возвращают список сообщений
[{"text": ..., "buttons": [(подпись, callback_data), ...] | None}], ядро их шлёт.
Все функции принимают today/now параметром — так их можно прогнать на моках.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

import safe_store

DATA_DIR = Path("/app/data")
HABITS_FILE = DATA_DIR / "habits_data.json"

FIRST_START = date(2026, 10, 17)                     # зубы — решение 16.10
NO_NEW_HABIT = [(date(2026, 10, 27), date(2026, 11, 22))]   # держим зубы до 3.11 + отпуск 4–22.11
SUNDAY_HOUR, SUNDAY_MINUTE = 20, 0

DAY_QUESTION = "Как прошёл вчерашний день? Было что-нибудь хорошее?"

SUNDAY_TEXT = (
    "Неделя закрыта. Были случаи?\n"
    "1 Паника. 2 Толчок (челюсть). 3 Спор. 4 Страх поверить. 5 Плохая догадка. "
    "6 Слово «отыграюсь». 7 Шёпот (ранний знак перегруза).\n"
    "Ответь номерами и одним словом: сработало или нет. "
    "Пример: «3 сработало, 2 нет, остальных не было».\n\n"
    "Одна победа недели — в «52 победы»."
)


def _h(key, name, norm, q, q_date, kind="yesno", about="yesterday", draft=False):
    return dict(key=key, name=name, norm=norm, q=q, q_date=q_date,
                kind=kind, about=about, draft=draft)


HABITS = [
    _h("teeth", "Зубы", 10,
       "Вчера почистил зубы две минуты по таймеру?",
       "{date}: почистил зубы две минуты по таймеру?"),
    _h("sleep", "Сон", 21,
       "Вчера экраны погасли в 23:00, свет в 23:30, телефон не у кровати?",
       "{date}: экраны погасли в 23:00, свет в 23:30, телефон не у кровати?"),
    _h("close_day", "Закрытие дня", 21,
       "Вчера закрыл день: стол пуст, посудомойка запущена, семёрка на сегодня записана, "
       "одно дело помечено лягушкой?",
       "{date}: закрыл день — стол пуст, посудомойка запущена, семёрка на следующий день записана, "
       "одно дело помечено лягушкой?"),
    _h("finance", "Финансовый день закрыт", 21,
       "Вчерашние траты внесены в КоинКипер?",
       "Траты за {date} внесены в КоинКипер?"),
    _h("coffee", "Кофе", 21,
       "Вчера не больше двух чашек кофе и последняя до 15:00?",
       "{date}: не больше двух чашек кофе и последняя до 15:00?"),
    _h("morning", "Утро", 21,
       "Вчера утром ответил на вопрос про день, а если не выспался — сказал Насе «сил сегодня мало»?",
       "{date}: утром ответил на вопрос про день, а если не выспался — сказал Насе «сил сегодня мало»?"),
    _h("news", "Новости 2 + 2", 21,
       "Вчера новости только из двух выпусков и двух нажатий, каналы напрямую не открывал?",
       "{date}: новости только из двух выпусков и двух нажатий, каналы напрямую не открывал?"),
    _h("fruit", "Фрукт вместо шоколадки", 21,
       "Вчера, когда тянуло к сладкому, был фрукт, а не шоколадка?",
       "{date}: когда тянуло к сладкому, был фрукт, а не шоколадка?"),
    _h("back", "Спина", 21,
       "Вчера после каждого блока работы вставал на две минуты?",
       "{date}: после каждого блока работы вставал на две минуты?"),
    _h("frog", "Лягушка первой", 21,
       "Вчера лягушка из семёрки сделана в первый свободный слот, 25 минут?",
       "{date}: лягушка из семёрки сделана в первый свободный слот, 25 минут?"),
    _h("tiberius", "Таран, Таракан или Тиберий", 21,
       "Кто вчера сидел за работой: Таран, Таракан или Тиберий?",
       "Кто {date} сидел за работой: Таран, Таракан или Тиберий?",
       kind="tiberius"),
    _h("move", "Движение", 21,
       "За последние три дня был бассейн или зал?",
       "За три дня по {date} был бассейн или зал?",
       draft=True),     # механику решить, когда подойдёт срок (решение 16.10)
    _h("clothes", "Одежда", 21,
       "Вчера вечером одежда на сегодня была приготовлена?",
       "{date}: вечером одежда на следующий день была приготовлена?"),
    _h("water", "Вода и зарядка", 21,
       "Сегодня день начался со стакана воды и зарядки?",
       "{date}: день начался со стакана воды и зарядки?",
       about="today"),
]

COMMANDMENTS = [
    "Цени своё время, делегируй всё, что можешь.",
    "Цени свои деньги, плати сначала себе, придерживайся финплана и не залезай в долги, "
    "помни о ключах к богатству, имей страховку.",
    "Помни о 20 лицах, которые тебя определяют, выбирай окружение, создавай мозговой центр, "
    "ищи покровителя и наставника.",
    "На тебя смотрит твой малыш: будь лидером, правильно общайся, создавай позитивный имидж; "
    "будь добрым, но гордость отдавай ангелу.",
    "Люби свою музу и заботься о ней, но помни секрет секс-ссоры.",
    "Помни о ЗОЖ: питание, спорт, зарядка, баланс сна, отдыха и работы, принципы работы мозга.",
    "Порядок и гигиена дома, во внешнем виде, мыслях, отношении; позитивный настрой; "
    "маркируй своё состояние и будь осознанным.",
    "Запрограммируй подсознание и получай ренту, убери страх и закрепи позитивными привычками.",
    "Набери компетенций, радуйся опыту, принимай кручёные мячи и бери ответственность.",
    "Помни о компасе: три крупные мечты, квартальные цели перед глазами, еженедельное планирование, "
    "по воскресеньям отдых.",
    "Три шага к целям каждый день, начиная с лягушки; ритуалы для действия; концентрируйся на одном шаге.",
    "Веди дневник эмоций и рангокнигу, закрепляй привычками, избегай искушений, "
    "помни о предназначении и герое.",
]
for _n, _t in enumerate(COMMANDMENTS, 1):
    HABITS.append(_h(f"cmd{_n}", f"Заповедь {_n}", 21,
                     f"Вчера соблюдал заповедь {_n}: «{_t}»?",
                     f"{{date}}: соблюдал заповедь {_n}: «{_t}»?"))

TIBERIUS_OPTIONS = ["Таран", "Таракан", "Тиберий"]


# ── Хранилище ────────────────────────────────────────────────────────────────
def default_state() -> dict:
    return {
        "rev": 0,
        "idx": 0,                      # номер текущей привычки в HABITS
        "count": 0,                    # дней подряд
        "start": FIRST_START.isoformat(),   # с какого дня считается текущая привычка
        "last_for": None,              # последний день, за который получен ответ
        "asking_for": None,            # за какой день сейчас задан вопрос
        "closed": [],                  # закреплённые: {idx, name, on}
        "log": [],                     # все ответы: {for, habit, answer, at}
        "diary": {},                   # дата → «как прошёл день»
        "sick": [],                    # даты «заболел»
        "sunday": {},                  # дата воскресенья → ответ
        "sunday_sent": None,
        "waiting_sunday": False,
        "ideas": [],                   # {at, text}
        "waiting_idea": False,
        "morning": {"date": None, "step": None},   # step: day | habit | None
    }


def load() -> dict:
    st, _ = safe_store.safe_load(HABITS_FILE, default_state)
    base = default_state()
    for k, v in base.items():
        st.setdefault(k, v)
    return st


def save(st: dict):
    st["rev"] = st.get("rev", 0) + 1
    safe_store.guarded_save(HABITS_FILE, st, guard_keys=("rev",))


# ── Даты ─────────────────────────────────────────────────────────────────────
def _d(s):
    return date.fromisoformat(s) if s else None


def _ddmm(d: date) -> str:
    return d.strftime("%d.%m")


def _first_free_day(d: date) -> date:
    moved = True
    while moved:
        moved = False
        for a, b in NO_NEW_HABIT:
            if a <= d <= b:
                d = b + timedelta(days=1)
                moved = True
    return d


def current(st: dict):
    i = st.get("idx", 0)
    return HABITS[i] if 0 <= i < len(HABITS) else None


def _last_askable(h: dict, today: date) -> date:
    return today if h["about"] == "today" else today - timedelta(days=1)


def pending_dates(st: dict, today: date) -> list:
    h = current(st)
    if not h:
        return []
    start = _d(st["start"])
    last = _d(st.get("last_for"))
    first = max(start, last + timedelta(days=1)) if last else start
    end = _last_askable(h, today)
    if first > end:
        return []
    return [first + timedelta(days=i) for i in range((end - first).days + 1)]


# ── Вопрос и ответ ───────────────────────────────────────────────────────────
def _question(st: dict, d: date, today: date) -> dict:
    h = current(st)
    default_day = _last_askable(h, today)
    q = h["q"] if d == default_day else h["q_date"].format(date=_ddmm(d))
    head = f"🌱 Привычка «{h['name']}» · в счёте {st['count']} из {h['norm']}"
    if h["draft"]:
        head += "\n(механику этой привычки уточнить — вопрос пока черновой)"
    if h["kind"] == "tiberius":
        buttons = [(o, f"hab|{o}|{d.isoformat()}") for o in TIBERIUS_OPTIONS]
    else:
        buttons = [("Да", f"hab|да|{d.isoformat()}"), ("Нет", f"hab|нет|{d.isoformat()}")]
    return {"text": f"{head}\n\n{q}", "buttons": buttons}


MAX_BACK_DAYS = 3      # спрашиваем максимум за 3 последних дня; раньше — без ответа = пропуск


def ask_next(st: dict, today: date) -> list:
    p = pending_dates(st, today)
    if not p:
        st["asking_for"] = None
        if st["morning"].get("date") == today.isoformat():
            st["morning"]["step"] = None
        return []
    pre = []
    if len(p) > MAX_BACK_DAYS:
        h = current(st)
        cut = p[-MAX_BACK_DAYS - 1]
        st["log"].append({"for": f"{p[0].isoformat()}..{cut.isoformat()}", "habit": h["key"],
                          "answer": "без ответа", "at": today.isoformat()})
        st["last_for"] = cut.isoformat()
        st["count"] = 0
        pre.append({"text": f"Дни {_ddmm(p[0])}–{_ddmm(cut)} остались без ответа — это пропуск: "
                            f"счёт «{h['name']}» заново. Спрошу за последние {MAX_BACK_DAYS} дня.",
                    "buttons": None})
        p = p[-MAX_BACK_DAYS:]
    st["asking_for"] = p[0].isoformat()
    st["morning"] = {"date": today.isoformat(), "step": "habit"}
    return pre + [_question(st, p[0], today)]


def _close(st: dict, for_date: date, today: date) -> list:
    h = current(st)
    st["closed"].append({"idx": st["idx"], "name": h["name"], "on": for_date.isoformat()})
    out = [f"🏆 Привычка «{h['name']}» закреплена: {h['norm']} из {h['norm']}.\n"
           f"Закрой её в «Первом севе» как целое дело."]
    st["idx"] += 1
    st["count"] = 0
    st["last_for"] = None
    nxt = current(st)
    if not nxt:
        out.append("Список привычек и заповедей пройден целиком.")
        return out
    start = _first_free_day(max(for_date + timedelta(days=1), today))
    st["start"] = start.isoformat()
    if start > today:
        out.append(f"Следующая — «{nxt['name']}», с {_ddmm(start)}. До тех пор вопросов о привычках нет.")
    else:
        when = "сегодня вечером" if nxt["about"] == "today" else "завтра утром"
        out.append(f"С сегодняшнего дня — «{nxt['name']}». Спрошу {when}:\n{nxt['q']}")
    return out


def answer(st: dict, value: str, for_iso: str, today: date) -> list:
    """value: «да» / «нет» / Таран / Таракан / Тиберий. Возвращает сообщения."""
    if not for_iso or st.get("asking_for") != for_iso:
        return [{"text": "Этот день уже записан.", "buttons": None}]
    h = current(st)
    for_date = _d(for_iso)
    if h["kind"] == "tiberius":
        ok = value == "Тиберий"
    else:
        ok = value.lower() == "да"
    st["log"].append({"for": for_iso, "habit": h["key"], "answer": value, "at": today.isoformat()})
    st["last_for"] = for_iso
    st["asking_for"] = None
    msgs = []
    if ok:
        st["count"] += 1
        if st["count"] >= h["norm"]:
            msgs += _close(st, for_date, today)
        else:
            msgs.append(f"✅ День {st['count']} из {h['norm']}.")
    else:
        st["count"] = 0
        extra = f" (записал: {value})" if h["kind"] == "tiberius" else ""
        msgs.append(f"Счёт заново, день 0 из {h['norm']}.{extra}")
    out = [{"text": t, "buttons": None} for t in msgs]
    return out + ask_next(st, today)


def parse_callback(data: str):
    """'hab|да|2026-10-17' → ('да', '2026-10-17') или None."""
    parts = (data or "").split("|")
    if len(parts) == 3 and parts[0] == "hab":
        return parts[1], parts[2]
    return None


def text_as_answer(st: dict, text: str):
    """Текстовый ответ вместо кнопки, когда ждём привычку. None — если текст не про это."""
    if st["morning"].get("step") != "habit" or not st.get("asking_for"):
        return None
    t = text.strip().lower().rstrip(".!")
    h = current(st)
    if h and h["kind"] == "tiberius":
        for o in TIBERIUS_OPTIONS:
            if t == o.lower():
                return o
        return None
    if t in ("да", "ага", "yes", "+"):
        return "да"
    if t in ("нет", "no", "-"):
        return "нет"
    return None


# ── Утро ─────────────────────────────────────────────────────────────────────
def morning_start(st: dict, today: date) -> list:
    """После ответа про дела (или сразу в праздник/отпуск)."""
    st["waiting_sunday"] = False          # воскресный ответ принимается до утра понедельника
    st["morning"] = {"date": today.isoformat(), "step": "day"}
    return [{"text": DAY_QUESTION, "buttons": None}]


def morning_text(st: dict, text: str, today: date):
    """Если ждём «как прошёл день» — сохраняет и задаёт вопрос о привычке. Иначе None."""
    m = st.get("morning") or {}
    if m.get("step") != "day":
        return None
    day = (today - timedelta(days=1)).isoformat()
    prev = st["diary"].get(day)
    st["diary"][day] = (prev + "\n" + text) if prev else text
    st["morning"]["step"] = None
    out = ask_next(st, today)
    if out:
        return [{"text": "Записал.", "buttons": None}] + out
    return [{"text": "Записал. " + quiet_line(st, today), "buttons": None}]


def quiet_line(st: dict, today: date) -> str:
    h = current(st)
    if not h:
        return "Вопросов о привычках больше нет."
    start = _d(st["start"])
    if start > today:
        held = st["closed"][-1]["name"] if st["closed"] else None
        tail = f" Держим «{held}»." if held else ""
        return f"Вопросов о привычке сегодня нет: «{h['name']}» начнётся {_ddmm(start)}.{tail}"
    return f"О привычке «{h['name']}» спрошу завтра утром."


# ── Воскресенье, идеи, болезнь ───────────────────────────────────────────────
def sunday_due(st: dict, now: datetime) -> bool:
    return (now.weekday() == 6 and now.hour == SUNDAY_HOUR and now.minute == SUNDAY_MINUTE
            and st.get("sunday_sent") != now.date().isoformat())


def sunday_message(st: dict, today: date) -> list:
    st["sunday_sent"] = today.isoformat()
    st["waiting_sunday"] = True
    return [{"text": SUNDAY_TEXT, "buttons": None}]


def sunday_text(st: dict, text: str):
    if not st.get("waiting_sunday"):
        return None
    key = st.get("sunday_sent") or "?"
    st["sunday"][key] = text
    st["waiting_sunday"] = False
    return [{"text": "Записал. Разбор — на воскресном планировании.", "buttons": None}]


def idea_start(st: dict) -> list:
    st["waiting_idea"] = True
    return [{"text": "💡 Пиши идею одним сообщением.", "buttons": None}]


def idea_add(st: dict, text: str, now: datetime) -> list:
    text = text.strip()
    if not text:
        return idea_start(st)
    st["ideas"].append({"at": now.strftime("%Y-%m-%d %H:%M"), "text": text})
    st["waiting_idea"] = False
    return [{"text": f"💡 В копилке идей: {len(st['ideas'])}.", "buttons": None}]


def ideas_pages(st: dict, limit: int = 3800) -> list:
    if not st["ideas"]:
        return ["💡 Копилка идей пуста. Напиши «идея …» или нажми «💡 Идея»."]
    lines = [f"💡 КОПИЛКА ИДЕЙ — {len(st['ideas'])}\n"]
    for n, it in enumerate(st["ideas"], 1):
        lines.append(f"{n}. {it['at'][:10]} — {it['text']}")
    pages, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > limit:
            pages.append(cur)
            cur = ""
        cur += ln + "\n"
    pages.append(cur)
    return pages


def mark_sick(st: dict, today: date):
    d = today.isoformat()
    if d not in st["sick"]:
        st["sick"].append(d)


# ── Статус, план, ручная правка ──────────────────────────────────────────────
def status_line(st: dict, today: date) -> str:
    h = current(st)
    if not h:
        return "🌱 Привычки: все пройдены."
    start = _d(st["start"])
    if start > today:
        return f"🌱 Следующая привычка: «{h['name']}» с {_ddmm(start)}"
    return f"🌱 Привычка: «{h['name']}» — {st['count']} из {h['norm']}"


def plan_text(st: dict, today: date) -> str:
    """Ориентировочные даты при условии без пропусков."""
    lines = ["🌱 ПРИВЫЧКИ — план без пропусков\n"]
    for c in st["closed"]:
        lines.append(f"✅ {c['name']} — закреплена {_ddmm(_d(c['on']))}")
    h = current(st)
    if not h:
        return "\n".join(lines)
    start = _d(st["start"])
    # текущая: сколько дней осталось
    days_done_until = _d(st["last_for"]) if st.get("last_for") else start - timedelta(days=1)
    end = max(days_done_until, start - timedelta(days=1)) + timedelta(days=h["norm"] - st["count"])
    lines.append(f"▶️ {h['name']} — {st['count']}/{h['norm']}, до {_ddmm(end)}")
    i = st["idx"] + 1
    while i < len(HABITS) and i < st["idx"] + 15:
        nh = HABITS[i]
        s = _first_free_day(end + timedelta(days=1))
        end = s + timedelta(days=nh["norm"] - 1)
        mark = " (механику уточнить)" if nh["draft"] else ""
        lines.append(f"⬜ {nh['name']} — {_ddmm(s)}–{end.strftime('%d.%m.%y')}{mark}")
        i += 1
    if i < len(HABITS):
        lines.append(f"…и дальше заповеди, всего пунктов в списке: {len(HABITS)}")
    return "\n".join(lines)


def set_count(st: dict, n: int, today: date) -> str:
    """/habit N — «в счёте N дней по вчерашний день включительно» (разовая подстройка при запуске)."""
    h = current(st)
    if not h:
        return "Привычек больше нет."
    n = max(0, min(n, h["norm"] - 1))
    st["count"] = n
    last = _last_askable(h, today)
    st["last_for"] = last.isoformat() if n > 0 else None
    if n > 0 and _d(st["start"]) > last:
        st["start"] = (last - timedelta(days=n - 1)).isoformat()
    st["asking_for"] = None
    return f"Записал: «{h['name']}» — {n} из {h['norm']} по {_ddmm(last)}."
