import os, sys, tempfile, unittest, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import db, discover, score, compliance, inbox, cli

S = {"limits": {"send_per_day": 2, "discover_per_run": 50}, "sender": {"name": "A", "company": "B", "postal_address": "Via X 1", "privacy_url": "https://x.it/p"}}
TERR = {"id": "monopoli", "name": "Monopoli"}
FAKE = {"elements": [
    {"type": "node", "id": 1, "tags": {"name": "Bar Mare", "amenity": "bar", "email": "info@baremare.it", "instagram": "baremare"}},
    {"type": "node", "id": 2, "tags": {"name": "Bar Mare", "amenity": "bar"}},          # duplicato
    {"type": "node", "id": 3, "tags": {"name": "Hotel Sole", "tourism": "hotel", "website": "http://x", "email": "mario.rossi@gmail.com"}},
    {"type": "node", "id": 4, "tags": {"amenity": "bar"}}]}                             # senza nome

class T(unittest.TestCase):
    def setUp(self):
        self.c = db.connect(os.path.join(tempfile.mkdtemp(), "t.db"))
        self.n = discover.discover(self.c, TERR, "bar", {"osm": ["amenity=bar"]}, post=lambda ep, q: FAKE)
    def test_dedup_and_rerun(self):
        self.assertEqual(self.n, 2)
        again = discover.discover(self.c, TERR, "bar", {"osm": ["amenity=bar"]}, post=lambda ep, q: FAKE)
        self.assertEqual(again, 0)
    def test_score_no_site_high(self):
        co = dict(self.c.execute("SELECT * FROM companies WHERE name='Bar Mare'").fetchone())
        s, issues, _ = score.score(co, None); self.assertGreaterEqual(s, 60); self.assertIn("solo su social", " ".join(issues))
    def test_score_bad_site(self):
        s, issues, _ = score.score({"website": "x", "category": "hotel"}, {"reachable": True, "https": False, "viewport": False, "slow": True})
        self.assertGreater(s, 40)
    def test_email_nature(self):
        self.assertEqual(compliance.classify_email("info@baremare.it"), "generic_business")
        self.assertEqual(compliance.classify_email("mario.rossi@gmail.com"), "personal")
        self.assertEqual(compliance.classify_email("mario@azienda.it"), "personal")
    def test_send_gate(self):
        co = dict(self.c.execute("SELECT * FROM companies WHERE name='Bar Mare'").fetchone())
        self.assertTrue(compliance.can_send(self.c, co, "info@baremare.it", S)[0])
        co2 = dict(self.c.execute("SELECT * FROM companies WHERE name='Hotel Sole'").fetchone())
        ok, why = compliance.can_send(self.c, co2, "mario.rossi@gmail.com", S); self.assertFalse(ok)
        ok, why = compliance.can_send(self.c, co, "info@baremare.it", {**S, "sender": {}}); self.assertFalse(ok)
        db.suppress(self.c, "info@baremare.it", "test"); co = dict(self.c.execute("SELECT * FROM companies WHERE id=?", (co["id"],)).fetchone())
        self.assertFalse(compliance.can_send(self.c, co, "info@baremare.it", S)[0])
    def test_reply_flow(self):
        cid = self.c.execute("SELECT id FROM companies WHERE name='Bar Mare'").fetchone()["id"]
        self.c.execute("INSERT INTO messages(company_id,direction,status,to_addr,subject,body,message_id,created_at) VALUES(?,?,?,?,?,?,?,?)", (cid, "out", "sent", "info@baremare.it", "Proposta", "ciao", "<o1>", db.now()))
        r = inbox.process(self.c, [{"from": "info@baremare.it", "subject": "Re: Proposta", "body": "Interessante, quanto costa un sito?", "message_id": "<r1>", "in_reply_to": "<o1>"}])
        self.assertEqual(r, [(cid, "quote")])
        e = inbox.notification_email(self.c, cid, "me@x.it", "bot@x.it"); self.assertIn("preventivo", e.get_content()); self.assertIn("Bar Mare", e.get_content())
        self.assertEqual(inbox.process(self.c, [{"from": "info@baremare.it", "subject": "Re", "body": "x", "message_id": "<r1>", "in_reply_to": "<o1>"}]), [])  # no doppioni
        r = inbox.process(self.c, [{"from": "info@baremare.it", "subject": "Re", "body": "Non contattatemi piu, cancellate i miei dati", "message_id": "<r2>", "in_reply_to": "<o1>"}])
        self.assertEqual(r[0][1], "opt_out"); self.assertTrue(db.is_suppressed(self.c, "info@baremare.it"))
        self.assertEqual(self.c.execute("SELECT status FROM companies WHERE id=?", (cid,)).fetchone()["status"], "do_not_contact")
    def test_classify(self):
        self.assertEqual(inbox.classify("Possiamo fissare un appuntamento giovedi?"), "meeting")
        self.assertEqual(inbox.classify("ci penso, forse più avanti"), "undecided")
        self.assertEqual(inbox.classify("Buongiorno"), "other")

if __name__ == "__main__": unittest.main()
