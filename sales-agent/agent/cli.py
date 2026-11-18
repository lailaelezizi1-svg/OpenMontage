"""CLI dell'agente commerciale. Uso: python -m agent.cli <comando>"""
import argparse, json, os, sys, time
from . import db, discover as disc, analyze as an, score as sc, compliance, mailbox, inbox

CFG = os.path.join(db.ROOT, "config")
def jload(n): return json.load(open(os.path.join(CFG, n)))

def cmd_discover(a, c, S):
    T = jload("territories.json"); n = 0
    for t in T["territories"]:
        if not t["enabled"] or (a.territory and t["id"] != a.territory): continue
        for cid, cat in T["categories"].items():
            if a.category and cid != a.category: continue
            got = disc.discover(c, t, cid, cat, S["limits"]["discover_per_run"]); n += got
            print(f"{t['name']:18} {cid:11} nuove: {got}"); time.sleep(S["limits"]["min_seconds_between_requests"])
    print("Totale nuove aziende:", n)

def cmd_analyze(a, c, S):
    rows = c.execute("SELECT * FROM companies WHERE status='new' LIMIT ?", (S["limits"]["analyze_per_run"],)).fetchall()
    for co in rows:
        co = dict(co); analysis = None
        if co["website"]:
            analysis = an.fetch_site(co["website"]); time.sleep(S["limits"]["min_seconds_between_requests"])
            for e in (analysis.get("emails") or []):
                c.execute("INSERT OR IGNORE INTO contacts(company_id,kind,value,source) VALUES(?,?,?,?)", (co["id"], "email", e, f"sito web {co['website']}"))
        s, issues, impr = sc.score(co, analysis)
        for e in c.execute("SELECT value FROM contacts WHERE company_id=? AND kind='email'", (co["id"],)).fetchall():
            c.execute("UPDATE contacts SET nature=? WHERE company_id=? AND value=?", (compliance.classify_email(e["value"]), co["id"], e["value"]))
        status = "qualified" if s >= S["scoring_min_to_contact"] else "analyzed"
        c.execute("UPDATE companies SET score=?,issues=?,improvements=?,status=?,analyzed_at=? WHERE id=?",
                  (s, json.dumps(issues, ensure_ascii=False), json.dumps(impr, ensure_ascii=False), status, db.now(), co["id"]))
        db.log(c, "analyzed", co["id"], f"score={s}"); c.commit(); print(f"{s:3} {co['name']} ({co['city']}) {issues}")

def make_draft(co, S):
    s = S["sender"]; issues = json.loads(co["issues"] or "[]")
    pts = "\n".join(f"- {i}" for i in issues[:3])
    subject = f"Una proposta per la presenza online di {co['name']}"
    body = (f"Buongiorno,\n\nmi chiamo {s['name']} ({s['company']}). Guardando la presenza online di {co['name']} a {co['city']} ho notato:\n{pts}\n\n"
            f"Realizziamo siti web professionali per attivita locali. Se le fa piacere, le mostro alcuni esempi senza impegno.\n\n"
            f"Cordiali saluti,\n{s['name']}\n{s['company']} - {s['postal_address']}\n\n"
            f"Se non desidera ricevere altre comunicazioni, risponda STOP: la sua richiesta sara rispettata subito. Informativa privacy: {s['privacy_url']}")
    return subject, body

def cmd_draft(a, c, S):
    rows = c.execute("""SELECT co.* FROM companies co WHERE co.status='qualified' AND EXISTS
        (SELECT 1 FROM contacts k WHERE k.company_id=co.id AND k.kind='email' AND k.nature='generic_business')
        AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.company_id=co.id AND m.direction='out') ORDER BY score DESC LIMIT ?""", (a.n,)).fetchall()
    for co in rows:
        to = c.execute("SELECT value FROM contacts WHERE company_id=? AND kind='email' AND nature='generic_business'", (co["id"],)).fetchone()["value"]
        subj, body = make_draft(co, S)
        c.execute("INSERT INTO messages(company_id,direction,status,to_addr,subject,body,created_at) VALUES(?,?,?,?,?,?,?)", (co["id"], "out", "draft", to, subj, body, db.now()))
        c.execute("UPDATE companies SET status='drafted' WHERE id=?", (co["id"],)); db.log(c, "draft", co["id"]); c.commit()
        print("bozza per", co["name"], "->", to)

def cmd_review(a, c, S):
    for m in c.execute("SELECT m.id,m.to_addr,m.subject,m.body,co.name FROM messages m JOIN companies co ON co.id=m.company_id WHERE m.direction='out' AND m.status='draft'"):
        print(f"\n=== #{m['id']} {m['name']} -> {m['to_addr']}\n{m['subject']}\n{m['body']}")

def cmd_approve(a, c, S):
    for i in a.ids: c.execute("UPDATE messages SET status='approved' WHERE id=? AND status='draft'", (i,)); db.log(c, "approved", None, str(i))
    c.commit(); print("approvate:", a.ids)

def cmd_send(a, c, S):
    for m in c.execute("SELECT * FROM messages WHERE direction='out' AND status='approved'").fetchall():
        co = c.execute("SELECT * FROM companies WHERE id=?", (m["company_id"],)).fetchone()
        ok, why = compliance.can_send(c, co, m["to_addr"], S)     # verifica SEMPRE prima dell'invio
        if not ok: print(f"BLOCCATO #{m['id']} {co['name']}: {'; '.join(why)}"); continue
        if a.dry_run: print(f"[dry-run] invierei #{m['id']} a {m['to_addr']}"); continue
        msg, mid = mailbox.build_outbound(m["to_addr"], m["subject"], m["body"], S["sender"]["name"], mailbox.env("MAILBOX_USER"))
        mailbox.smtp_send(msg)
        c.execute("UPDATE messages SET status='sent',sent_at=?,message_id=? WHERE id=?", (db.now(), mid, m["id"]))
        c.execute("UPDATE companies SET status='contacted' WHERE id=?", (co["id"],)); db.log(c, "sent", co["id"], m["to_addr"]); c.commit(); print("inviata a", co["name"])

def cmd_inbox(a, c, S):
    res = inbox.process(c, mailbox.fetch_unseen()); print("risposte elaborate:", res)
    for cid, label in res:
        if label in inbox.NOTIFY:
            mid = c.execute("SELECT id FROM messages WHERE company_id=? AND direction='in' ORDER BY id DESC", (cid,)).fetchone()["id"]
            if c.execute("SELECT 1 FROM notifications WHERE message_id=?", (mid,)).fetchone(): continue
            e = inbox.notification_email(c, cid, mailbox.env("NOTIFY_TO"), mailbox.env("MAILBOX_USER")); mailbox.smtp_send(e)
            c.execute("INSERT INTO notifications(message_id,sent_at) VALUES(?,?)", (mid, db.now())); c.commit(); print("notifica inviata per azienda", cid)

def cmd_suppress(a, c, S): db.suppress(c, a.email, a.reason or "manuale"); print("in lista di soppressione:", a.email)

def cmd_status(a, c, S):
    for r in c.execute("SELECT status, COUNT(*) n FROM companies GROUP BY status"): print(f"{r['status']:15}{r['n']}")
    print("soppressioni:", c.execute("SELECT COUNT(*) FROM suppression").fetchone()[0])
    print("\nTop opportunita:")
    for r in c.execute("SELECT name,city,score,website,status FROM companies WHERE score IS NOT NULL ORDER BY score DESC LIMIT 10"): print(f"{r['score']:3} {r['name']} ({r['city']}) {r['website'] or '-'} [{r['status']}]")

def cmd_cycle(a, c, S):
    """Un ciclo completo: cerca, analizza, bozze, risposte. NON invia: l'invio richiede approvazione."""
    a.territory = a.category = None; a.n = 10
    for step in (cmd_discover, cmd_analyze, cmd_draft): step(a, c, S)
    if mailbox.env("MAILBOX_USER"): cmd_inbox(a, c, S)
    cmd_status(a, c, S)

def main(argv=None):
    mailbox.load_env(os.path.join(db.ROOT, ".env"))
    p = argparse.ArgumentParser(); sp = p.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("discover"); d.add_argument("--territory"); d.add_argument("--category")
    sp.add_parser("analyze"); dr = sp.add_parser("draft"); dr.add_argument("-n", type=int, default=10)
    sp.add_parser("review"); ap = sp.add_parser("approve"); ap.add_argument("ids", type=int, nargs="+")
    sd = sp.add_parser("send"); sd.add_argument("--dry-run", action="store_true")
    sp.add_parser("inbox"); su = sp.add_parser("suppress"); su.add_argument("email"); su.add_argument("--reason")
    sp.add_parser("status"); sp.add_parser("cycle")
    a = p.parse_args(argv); S = jload("settings.json"); c = db.connect()
    globals()["cmd_" + a.cmd](a, c, S)

if __name__ == "__main__": main()
