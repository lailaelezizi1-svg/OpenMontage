"""SMTP/IMAP. Credenziali SOLO da variabili d'ambiente (.env), mai stampate nei log."""
import os, smtplib, imaplib, email, ssl, uuid
from email.message import EmailMessage
from email.header import decode_header, make_header

def env(k, d=""): return os.environ.get(k, d)

def load_env(path):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

def smtp_send(msg):
    with smtplib.SMTP_SSL(env("SMTP_HOST"), int(env("SMTP_PORT", "465")), context=ssl.create_default_context()) as s:
        s.login(env("MAILBOX_USER"), env("MAILBOX_APP_PASSWORD")); s.send_message(msg)

def build_outbound(to, subject, body, sender_name, mailbox_user):
    m = EmailMessage(); mid = f"<{uuid.uuid4().hex}@sales-agent>"
    m["From"] = f"{sender_name} <{mailbox_user}>"; m["To"] = to; m["Subject"] = subject; m["Message-ID"] = mid
    local, dom = mailbox_user.split("@")
    m["List-Unsubscribe"] = f"<mailto:{local}+unsub@{dom}>"
    m.set_content(body); return m, mid

def _dec(v): return str(make_header(decode_header(v or "")))

def fetch_unseen(limit=50):
    """Ritorna lista di dict dei messaggi non letti (non li segna come letti)."""
    out = []
    with imaplib.IMAP4_SSL(env("IMAP_HOST")) as im:
        im.login(env("MAILBOX_USER"), env("MAILBOX_APP_PASSWORD")); im.select("INBOX", readonly=True)
        _, ids = im.search(None, "UNSEEN")
        for i in ids[0].split()[-limit:]:
            _, d = im.fetch(i, "(BODY.PEEK[])"); m = email.message_from_bytes(d[0][1])
            body = ""
            for p in (m.walk() if m.is_multipart() else [m]):
                if p.get_content_type() == "text/plain":
                    body = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "ignore"); break
            out.append({"from": email.utils.parseaddr(m["From"])[1].lower(), "subject": _dec(m["Subject"]), "body": body[:4000],
                        "message_id": m["Message-ID"], "in_reply_to": m.get("In-Reply-To", "")})
    return out
