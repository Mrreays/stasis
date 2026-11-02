"""Politique au quotidien : une leçon de 5 min + des flashcards à réviser (Leitner).

Les leçons sont des fichiers JSON dans content/ (un par jour, nommé AAAA-MM-JJ.json),
produits chaque matin par une tâche planifiée Claude. L'appli les importe en base
(SQLite) et gère seule la répétition espacée.
"""
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown as md
import nh3
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

BASE = Path(__file__).resolve().parent
CONTENT_DIR = Path(os.getenv("CONTENT_DIR", BASE.parent / "content"))
DB_PATH = Path(os.getenv("DB_PATH", BASE.parent / "data" / "app.db"))
PASSWORD = os.getenv("APP_PASSWORD", "")
TZ = ZoneInfo(os.getenv("APP_TZ", "Europe/Paris"))

# Boîtes de Leitner : intervalle (jours) avant la prochaine révision
INTERVALS = {1: 1, 2: 3, 3: 7, 4: 16, 5: 35}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TYPE_LABELS = {
    "notion": "Notion de fond",
    "actu": "Décryptage d'actu",
    "synthese": "Synthèse de la semaine",
    "debat": "Exercice de débat",
}
LEVEL_LABELS = {
    "academique": "Académique",
    "officiel": "Données officielles",
    "presse": "Presse de référence",
    "think_tank": "Think tank",
    "partisan": "Source partisane",
}

security = HTTPBasic(auto_error=False)


def check_auth(credentials: HTTPBasicCredentials | None = Depends(security)):
    if not PASSWORD:
        return
    ok = credentials is not None and secrets.compare_digest(
        credentials.password.encode(), PASSWORD.encode()
    )
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Authentification requise",
            headers={"WWW-Authenticate": 'Basic realm="Politique"'},
        )


app = FastAPI(dependencies=[Depends(check_auth)], docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def today() -> date:
    return datetime.now(TZ).date()


def render_md(text: str) -> Markup:
    html = md.markdown(text or "", extensions=["extra"])
    return Markup(nh3.clean(html))


def fr_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{jours[d.weekday()]} {d.day} {mois[d.month - 1]} {d.year}"


templates.env.filters["md"] = render_md
templates.env.filters["frdate"] = fr_date
templates.env.globals["TYPE_LABELS"] = TYPE_LABELS
templates.env.globals["LEVEL_LABELS"] = LEVEL_LABELS


# ---------- Base de données ----------

@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS lessons(
                date TEXT PRIMARY KEY, type TEXT, titre TEXT, parcours TEXT,
                resume TEXT, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cards(
                id TEXT PRIMARY KEY, lesson_date TEXT NOT NULL,
                q TEXT NOT NULL, r TEXT NOT NULL,
                box INTEGER NOT NULL DEFAULT 1, due TEXT NOT NULL,
                reps INTEGER NOT NULL DEFAULT 0, lapses INTEGER NOT NULL DEFAULT 0,
                last_review TEXT
            );
            CREATE TABLE IF NOT EXISTS reviews(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT NOT NULL, day TEXT NOT NULL, result TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due);
            """
        )


_signature = None


def sync_content():
    """Importe les JSON de content/ (idempotent, ne touche pas à la progression)."""
    global _signature
    files = sorted(p for p in CONTENT_DIR.glob("*.json") if DATE_RE.match(p.stem))
    sig = tuple((p.name, p.stat().st_mtime_ns) for p in files)
    if sig == _signature:
        return
    with db() as c:
        for p in files:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                day = p.stem
                due = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
            except Exception:
                continue  # fichier invalide : on l'ignore sans planter l'appli
            c.execute(
                """INSERT INTO lessons(date, type, titre, parcours, resume, data)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(date) DO UPDATE SET type=excluded.type, titre=excluded.titre,
                   parcours=excluded.parcours, resume=excluded.resume, data=excluded.data""",
                (day, d.get("type", "notion"), d.get("titre", day), d.get("parcours", ""),
                 d.get("resume", ""), json.dumps(d, ensure_ascii=False)),
            )
            for i, card in enumerate(d.get("flashcards", [])):
                q, r = card.get("q"), card.get("r")
                if not q or not r:
                    continue
                c.execute(
                    """INSERT INTO cards(id, lesson_date, q, r, due) VALUES(?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET q=excluded.q, r=excluded.r""",
                    (f"{day}-{i}", day, q, r, due),
                )
    _signature = sig


@app.on_event("startup")
def startup():
    init_db()
    sync_content()


def load_lesson(row) -> dict:
    d = json.loads(row["data"])
    d["date"] = row["date"]
    words = len((d.get("contenu_md") or "").split())
    d["minutes"] = max(1, round(words / 200))
    return d


def streak(conn) -> int:
    days = {r["day"] for r in conn.execute("SELECT DISTINCT day FROM reviews")}
    d = today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


# ---------- Pages ----------

@app.get("/")
def home(request: Request):
    sync_content()
    t = today().isoformat()
    with db() as c:
        row = c.execute(
            "SELECT * FROM lessons WHERE date<=? ORDER BY date DESC LIMIT 1", (t,)
        ).fetchone()
        lesson = load_lesson(row) if row else None
        due = c.execute("SELECT COUNT(*) FROM cards WHERE due<=?", (t,)).fetchone()[0]
        boxes = {r["box"]: r["n"] for r in c.execute(
            "SELECT box, COUNT(*) n FROM cards GROUP BY box")}
        total = sum(boxes.values())
        lessons_count = c.execute("SELECT COUNT(*) FROM lessons WHERE date<=?", (t,)).fetchone()[0]
        st = streak(c)
    return templates.TemplateResponse(request, "home.html", {
        "lesson": lesson, "is_today": bool(lesson and lesson["date"] == t),
        "due": due, "boxes": boxes, "total": total,
        "lessons_count": lessons_count, "streak": st, "today": t,
    })


@app.get("/lecon/{day}")
def lesson_page(request: Request, day: str):
    sync_content()
    if not DATE_RE.match(day):
        raise HTTPException(404)
    with db() as c:
        row = c.execute(
            "SELECT * FROM lessons WHERE date=? AND date<=?", (day, today().isoformat())
        ).fetchone()
    if not row:
        raise HTTPException(404, "Leçon introuvable")
    return templates.TemplateResponse(request, "lesson.html", {"lesson": load_lesson(row)})


@app.get("/archives")
def archives(request: Request):
    sync_content()
    with db() as c:
        rows = c.execute(
            "SELECT date, type, titre, parcours, resume FROM lessons WHERE date<=? ORDER BY date DESC",
            (today().isoformat(),),
        ).fetchall()
    return templates.TemplateResponse(request, "archives.html", {"rows": rows})


@app.get("/revision")
def revision(request: Request):
    sync_content()
    t = today().isoformat()
    with db() as c:
        card = c.execute(
            "SELECT * FROM cards WHERE due<=? ORDER BY due, box, id LIMIT 1", (t,)
        ).fetchone()
        remaining = c.execute("SELECT COUNT(*) FROM cards WHERE due<=?", (t,)).fetchone()[0]
        reviewed_today = c.execute(
            "SELECT COUNT(*) FROM reviews WHERE day=?", (t,)).fetchone()[0]
        nxt = c.execute("SELECT MIN(due) FROM cards WHERE due>?", (t,)).fetchone()[0]
    return templates.TemplateResponse(request, "revision.html", {
        "card": card, "remaining": remaining,
        "reviewed_today": reviewed_today, "next_due": nxt,
    })


@app.post("/revision/{card_id}")
def review(card_id: str, result: str = Form(...)):
    if result not in ("rate", "hesite", "su"):
        raise HTTPException(400, "Résultat invalide")
    t = today()
    with db() as c:
        card = c.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not card:
            raise HTTPException(404, "Carte introuvable")
        box, lapses = card["box"], card["lapses"]
        if result == "su":
            box = min(box + 1, 5)
            days = INTERVALS[box]
        elif result == "hesite":
            days = max(1, INTERVALS[box] // 2)
        else:
            box, lapses, days = 1, lapses + 1, 1
        c.execute(
            "UPDATE cards SET box=?, lapses=?, reps=reps+1, due=?, last_review=? WHERE id=?",
            (box, lapses, (t + timedelta(days=days)).isoformat(), t.isoformat(), card_id),
        )
        c.execute("INSERT INTO reviews(card_id, day, result) VALUES(?,?,?)",
                  (card_id, t.isoformat(), result))
    return RedirectResponse("/revision", status_code=303)
