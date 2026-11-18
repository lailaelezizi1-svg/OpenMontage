"""Valutazione opportunita 1-100 basata solo su fatti rilevati. Niente dati inventati."""
def score(company, analysis):
    s, issues, impr = 0, [], []
    site = company.get("website")
    social_only = (company.get("instagram") or company.get("facebook")) and not site
    if not site:
        s += 55; issues.append("Nessun sito web rilevato nelle fonti consultate")
        impr.append("Sito professionale con orari, menu/servizi, contatti e mappa")
        if social_only: s += 10; issues.append("Presenza solo su social")
    else:
        a = analysis or {}
        if not a.get("reachable", True): s += 40; issues.append("Il sito non risponde")
        else:
            if not a.get("https"): s += 12; issues.append("Sito senza HTTPS")
            if not a.get("viewport"): s += 18; issues.append("Non ottimizzato per smartphone (manca meta viewport)")
            if a.get("slow"): s += 10; issues.append(f"Risposta lenta ({a.get('seconds')}s)")
            if a.get("old_tech"): s += 8; issues.append("Tecnologie datate (es. Flash/frameset/tabelle)")
            if a.get("copyright_year") and a["copyright_year"] < 2020: s += 8; issues.append(f"Contenuti non aggiornati (copyright {a['copyright_year']})")
            if not a.get("booking") and company.get("category") in ("hotel", "ristorante", "bar", "lido", "bellezza", "sport"):
                s += 10; issues.append("Nessun sistema di prenotazione online rilevato")
            if s: impr.append("Rifacimento responsive, HTTPS, velocita, prenotazione online")
    if not company.get("email") and not company.get("phone"): s -= 5
    return max(1, min(100, s)), issues, impr
