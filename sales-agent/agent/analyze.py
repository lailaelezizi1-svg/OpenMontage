"""Analisi presenza digitale. Solo richieste GET singole alla homepage pubblica."""
import re, time, urllib.request, ssl

UA = "Mozilla/5.0 (compatible; LocalWebAudit/1.0)"
BOOK = re.compile(r"booking\.com|thefork|prenota|booking|reserv|quandoo|treatwell|fresha|mindbody|beddy|smoobu|octorate|simplebooking", re.I)

def fetch_site(url, timeout=12):
    if not url.startswith("http"): url = "http://" + url
    t = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout, context=ssl.create_default_context())
        html = r.read(400_000).decode("utf-8", "ignore"); final = r.geturl()
    except Exception as e:
        return {"reachable": False, "error": type(e).__name__}
    secs = round(time.time() - t, 1)
    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)[^0-9]{0,20}((?:19|20)\d\d)", html, re.I)]
    return {"reachable": True, "final_url": final, "https": final.startswith("https"), "seconds": secs, "slow": secs > 4,
            "viewport": bool(re.search(r'<meta[^>]+name=["\']viewport', html, re.I)),
            "old_tech": bool(re.search(r"<frameset|\.swf|<marquee|shockwave", html, re.I)),
            "copyright_year": max(years) if years else None, "booking": bool(BOOK.search(html)),
            "emails": sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", html)))[:5]}
