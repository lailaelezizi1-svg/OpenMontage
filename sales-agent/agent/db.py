"""Database SQLite persistente. Tutto lo stato dell'agente vive qui."""
import os, sqlite3, json, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("SALES_DB", os.path.join(ROOT, "data", "sales.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies(
  id INTEGER PRIMARY KEY, dedup_key TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL, category TEXT, city TEXT, territory_id TEXT, address TEXT,
  website TEXT, instagram TEXT, facebook TEXT, phone TEXT, email TEXT,
  source TEXT, source_ref TEXT, verified INTEGER DEFAULT 0,
  status TEXT DEFAULT 'new',  -- new|analyzed|qualified|drafted|contacted|interested|quote|meeting|not_interested|do_not_contact
  score INTEGER, issues TEXT, improvements TEXT, rationale TEXT,
  found_at TEXT, analyzed_at TEXT);
CREATE TABLE IF NOT EXISTS contacts(
  id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
  kind TEXT NOT NULL,            -- email|phone
  value TEXT NOT NULL, source TEXT NOT NULL,
  nature TEXT DEFAULT 'unknown', -- generic_business|personal|unknown
  UNIQUE(company_id, kind, value));
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
  direction TEXT NOT NULL,       -- out|in
  status TEXT NOT NULL,          -- draft|approved|sent|received|rejected
  to_addr TEXT, subject TEXT, body TEXT, message_id TEXT UNIQUE,
  classification TEXT, created_at TEXT, sent_at TEXT);
CREATE TABLE IF NOT EXISTS suppression(
  value TEXT PRIMARY KEY, reason TEXT, added_at TEXT);   -- email o dominio
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY, at TEXT, company_id INTEGER, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY, kind TEXT, territory_id TEXT, category TEXT, at TEXT, found INTEGER);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY, message_id INTEGER UNIQUE, sent_at TEXT);
"""

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def connect(path=None):
    path = path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path); c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON"); c.executescript(SCHEMA); return c

def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def dedup_key(name, city, address=None):
    return f"{norm(name)}|{norm(city)}"

def log(c, action, company_id=None, detail=""):
    c.execute("INSERT INTO activity(at,company_id,action,detail) VALUES(?,?,?,?)", (now(), company_id, action, detail))

def domain_of(email): return (email or "").split("@")[-1].lower()

def is_suppressed(c, email):
    e = (email or "").lower()
    return c.execute("SELECT 1 FROM suppression WHERE value IN (?,?)", (e, domain_of(e))).fetchone() is not None

def suppress(c, email, reason, company_id=None):
    c.execute("INSERT OR IGNORE INTO suppression VALUES(?,?,?)", ((email or "").lower(), reason, now()))
    if company_id:
        c.execute("UPDATE companies SET status='do_not_contact' WHERE id=?", (company_id,))
        c.execute("UPDATE messages SET status='rejected' WHERE company_id=? AND direction='out' AND status IN('draft','approved')", (company_id,))
    log(c, "suppress", company_id, reason); c.commit()

def add_company(c, **f):
    """Inserisce un'azienda evitando duplicati. Ritorna (id, created)."""
    key = dedup_key(f["name"], f.get("city"))
    row = c.execute("SELECT id FROM companies WHERE dedup_key=?", (key,)).fetchone()
    if row: return row["id"], False
    cols = ["dedup_key", "found_at"] + list(f); vals = [key, now()] + list(f.values())
    cur = c.execute(f"INSERT INTO companies({','.join(cols)}) VALUES({','.join('?'*len(cols))})", vals)
    log(c, "found", cur.lastrowid, f.get("source", "")); c.commit()
    return cur.lastrowid, True
