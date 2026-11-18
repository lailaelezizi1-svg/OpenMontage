"""Controllo prima di OGNI invio promozionale. Approccio prudente, non e un parere legale.
Regola: si invia solo se TUTTE le condizioni sono vere. Telefono: mai contatto automatico."""
import re
from . import db

FREE_MAIL = {"gmail.com","googlemail.com","libero.it","virgilio.it","hotmail.com","hotmail.it","outlook.com","outlook.it",
             "yahoo.com","yahoo.it","icloud.com","live.it","live.com","tiscali.it","alice.it","tin.it","fastwebnet.it","aruba.it"}
GENERIC = {"info","contatti","contact","contacts","booking","prenotazioni","reservations","reception","ufficio","segreteria","hello","ciao","amministrazione","direzione","commerciale"}

def classify_email(addr):
    local, _, dom = (addr or "").lower().partition("@")
    if not dom: return "unknown"
    if dom in FREE_MAIL: return "personal"          # spesso ditta individuale / persona fisica
    if local in GENERIC: return "generic_business"
    return "personal"                               # nome.cognome@... = persona identificabile

def can_send(c, company, to_addr, settings):
    """Ritorna (ok, [motivi di blocco])."""
    why = []
    if company["status"] in ("do_not_contact", "not_interested"): why.append("azienda in lista non ricontattare/non interessata")
    if db.is_suppressed(c, to_addr): why.append("indirizzo/dominio in lista di soppressione")
    row = c.execute("SELECT * FROM contacts WHERE company_id=? AND kind='email' AND value=?", (company["id"], to_addr)).fetchone()
    if not row: why.append("indirizzo non registrato tra i contatti con fonte")
    elif classify_email(to_addr) != "generic_business": why.append("indirizzo non generico aziendale (possibile persona fisica/ditta individuale): serve base giuridica verificata a mano")
    s = settings.get("sender", {})
    for k, lab in (("name","nome mittente"),("company","ragione sociale"),("postal_address","indirizzo postale"),("privacy_url","link informativa privacy")):
        if not s.get(k): why.append(f"manca in settings.json: {lab}")
    sent_today = c.execute("SELECT COUNT(*) n FROM messages WHERE direction='out' AND status='sent' AND date(sent_at)=date('now')").fetchone()["n"]
    if sent_today >= settings["limits"]["send_per_day"]: why.append("limite giornaliero raggiunto")
    if c.execute("SELECT 1 FROM messages WHERE company_id=? AND direction='out' AND status='sent'", (company["id"],)).fetchone():
        why.append("gia contattata (nessun secondo invio automatico)")
    return (not why), why

OPT_OUT = re.compile(r"\b(non (?:voglio|desidero|siamo interessat\w*|mi interessa)|cancell\w+|rimuov\w+|togliet\w+|non contattar\w+|unsubscribe|stop|opposizione|basta|privacy|gdpr|diritto)\b", re.I)
def is_opt_out(text): return bool(OPT_OUT.search(text or ""))
