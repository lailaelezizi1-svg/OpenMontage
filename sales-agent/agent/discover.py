"""Scoperta attivita da OpenStreetMap (Overpass). Dati pubblici ODbL; indicare la fonte."""
import json, time, urllib.request, urllib.parse
from . import db

ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

def build_query(city, osm_tags):
    parts = "".join(f'nwr(area.a)["{k}"="{v}"]["name"];' for k, v in (t.split("=") for t in osm_tags))
    return f'[out:json][timeout:60];area["name"="{city}"]["boundary"="administrative"]->.a;({parts});out tags center;'

def query_overpass(q, post=None):
    post = post or _post
    last = None
    for ep in ENDPOINTS:
        try: return post(ep, q)
        except Exception as e: last = e
    raise RuntimeError(f"Overpass non raggiungibile: {last}")

def _post(ep, q):
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(ep, data, {"User-Agent": "LocalWebAudit/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=90))

def from_element(el, territory, cat):
    t = el.get("tags", {})
    def tag(*ks):
        for k in ks:
            if t.get(k): return t[k].strip()
    street = " ".join(x for x in [t.get("addr:street"), t.get("addr:housenumber")] if x)
    insta = tag("contact:instagram", "instagram"); fb = tag("contact:facebook", "facebook")
    return dict(name=t["name"], category=cat, city=territory["name"], territory_id=territory["id"],
                address=street or None, website=tag("website", "contact:website", "url"),
                instagram=insta, facebook=fb, phone=tag("phone", "contact:phone"),
                email=tag("email", "contact:email"),
                source="OpenStreetMap", source_ref=f"{el['type']}/{el['id']}", verified=0)

def discover(c, territory, cat_id, cat, limit=150, post=None):
    q = build_query(territory["name"], cat["osm"])
    els = query_overpass(q, post).get("elements", [])
    new = 0
    for el in els[:limit]:
        if "name" not in el.get("tags", {}): continue
        f = from_element(el, territory, cat_id)
        cid, created = db.add_company(c, **f)
        if created:
            new += 1
            for kind, key in (("email", "email"), ("phone", "phone")):
                if f.get(key):
                    c.execute("INSERT OR IGNORE INTO contacts(company_id,kind,value,source) VALUES(?,?,?,?)", (cid, kind, f[key], "OpenStreetMap (pubblico)"))
    c.execute("INSERT INTO runs(kind,territory_id,category,at,found) VALUES('discover',?,?,?,?)", (territory["id"], cat_id, db.now(), new))
    c.commit(); return new
