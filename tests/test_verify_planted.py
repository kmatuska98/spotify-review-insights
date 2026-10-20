"""Planted-error test for VERIFY (offline, fake model, zero cost).

A deliberately WRONG label is planted into a separate test copy of the enrich results. The blind verifier
(which never sees the first answer) gives the sensible label, and code must report the disagreement.

run:  python -m unittest tests.test_verify_planted -v
"""
import csv, json, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import enrich, verify  # noqa: E402
from tests.test_pipeline import FakeModel, write_csv, good  # noqa: E402

RATES = str(ROOT / "cost" / "rates.json")
TEXTS = ["App keeps crashing when I open it", "Cannot log in to my account", "Love it", "Downloads vanish every week"]


class PlantedWrongLabel(unittest.TestCase):
    def test_verifier_flags_the_planted_wrong_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            src = Path(tmp) / "in.csv"
            write_csv(src, TEXTS)
            orig = enrich.call_model
            try:
                enrich.call_model = FakeModel()       # enrich labels everything playback/complaint/3
                enrich.run(src, run, 1.0, 50, "initial", None, RATES)
                # PLANT: corrupt one stored first-pass record in this TEST COPY (billing/praise/5 for a crash report)
                db = sqlite3.connect(run / "enrich.db")
                rid, rec = db.execute("SELECT review_id, record FROM results WHERE review_id='R0'").fetchone()
                bad = dict(json.loads(rec), topic="billing", intent="praise", severity=5)
                db.execute("UPDATE results SET record=? WHERE review_id='R0'", (json.dumps(bad),))
                db.commit(); db.close()
                seen_by_verifier = []

                class Blind(FakeModel):                # verifier gets only texts; answers independently
                    def __call__(self, key, items, max_out, model=enrich.MODEL, system=None):
                        seen_by_verifier.append(items)
                        return super().__call__(key, items, max_out, model, system)
                verify.call_model = Blind()
                rep = verify.run(run, 10, 1.0, verify.VERIFY_MODEL, RATES)
            finally:
                enrich.call_model = orig
            self.assertEqual(rep["verified"], 4)
            flagged = {d["review_id"] for d in rep["disagreements"]}
            self.assertIn("R0", flagged)               # the planted wrong label is caught
            self.assertNotIn("R1", flagged)            # untouched records agree
            self.assertTrue(all(set(x) == {"id", "text"} for batch in seen_by_verifier for x in batch))  # blind: no labels sent
            self.assertTrue(rep["agreement"]["all_three"] < 1.0)


if __name__ == "__main__":
    unittest.main()
