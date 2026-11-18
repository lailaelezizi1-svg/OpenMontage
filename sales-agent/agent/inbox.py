"""Classificazione risposte (base a parole chiave; Claude Code puo rivedere con `reclassify`) e notifiche."""
import re
from . import db, compliance
from email.message import EmailMessage

RULES = [  # ordine = priorita
    ("opt_out", compliance.OPT_OUT),
    ("quote", re.compile(r"preventiv|quanto cost|prezzo|prezzi|listino|tariff|costo", re.I)),
    ("meeting", re.compile(r"appuntament|chiamat|incontr|vediamoci|disponibil\w+ (?:per|a)|passare|telefon|call\b|videochiamata", re.I)),
    ("interested", re.compile(r"interessat|volentieri|mi piacerebbe|vorrei sapere|raccont|mandami|inviami|esempi|ok\b|perfetto", re.I)),
    ("undecided", re.compile(r"forse|ci (?:penso|pensiamo)|pi[uù] avanti|non ora|per ora|valut", re.I)),
]
def classify(text):
    for label, rx in RULES:
        if rx.search(text or ""): return label
    return "other"

NOTIFY = {"interested", "quote", "meeting"}
LEVEL = {"quote": "ALTO (richiesta preventivo)", "meeting": "ALTO (richiesta appuntamento)", "interested": "MEDIO (interesse espresso)"}
NEXT = {"quote": "Rispondere entro la giornata con una proposta/range di prezzo; proporre una breve call.",
        "meeting": "Confermare data e ora; preparare esempi di siti del settore.",
        "interested": "Rispondere con 2-3 esempi pertinenti e proporre una call di 15 minuti."}

def match_company(c, msg):
    if msg.get("in_reply_to"):
        r = c.execute("SELECT company_id FROM messages WHERE message_id=?", (msg["in_reply_to"].strip(),)).fetchone()
        if r: return r["company_id"]
    r = c.execute("SELECT company_id FROM contacts WHERE kind='email' AND value=?", (msg["from"],)).fetchone()
    return r["company_id"] if r else None

def process(c, msgs):
    results = []
    for m in msgs:
        cid = match_company(c, m)
        if cid is None: continue                       # ignora posta non legata a una trattativa
        if m.get("message_id") and c.execute("SELECT 1 FROM messages WHERE message_id=?", (m["message_id"],)).fetchone(): continue
        label = classify(m["subject"] + "\n" + m["body"])
        c.execute("INSERT INTO messages(company_id,direction,status,to_addr,subject,body,message_id,classification,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (cid, "in", "received", m["from"], m["subject"], m["body"], m.get("message_id"), label, db.now()))
        if label == "opt_out": db.suppress(c, m["from"], "opposizione ricevuta", cid)   # immediato
        else:
            status = {"interested": "interested", "quote": "quote", "meeting": "meeting", "undecided": "contacted"}.get(label)
            if status: c.execute("UPDATE companies SET status=? WHERE id=?", (status, cid))
        db.log(c, "reply:" + label, cid, m["subject"]); c.commit(); results.append((cid, label))
    return results

def notification_email(c, company_id, to_addr, from_addr):
    co = c.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    conv = c.execute("SELECT direction,subject,body,created_at,to_addr FROM messages WHERE company_id=? AND status IN('sent','received') ORDER BY id", (company_id,)).fetchall()
    last = [m for m in conv if m["direction"] == "in"][-1]
    label = last and c.execute("SELECT classification FROM messages WHERE company_id=? AND direction='in' ORDER BY id DESC", (company_id,)).fetchone()["classification"]
    lines = [f"Attivita: {co['name']}", f"Contatto: {last['to_addr'] or co['email'] or co['phone'] or 'n/d'}", f"Citta: {co['city']}",
             f"Sito web: {co['website'] or 'nessuno rilevato'}", f"Livello di interesse: {LEVEL.get(label, label)}",
             f"Prossima azione consigliata: {NEXT.get(label, 'Valutare manualmente')}", "", "--- Conversazione ---"]
    for m in conv: lines.append(f"[{'NOI' if m['direction']=='out' else 'LORO'} {m['created_at']}] {m['subject']}\n{m['body']}\n")
    e = EmailMessage(); e["From"] = from_addr; e["To"] = to_addr; e["Subject"] = f"[Opportunita] {co['name']} ({co['city']}) - {label}"
    e.set_content("\n".join(lines)); return e
