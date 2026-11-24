"""Part C: isolated integration tests for the original Flask application."""
import unittest
import tempfile
import sqlite3
from pathlib import Path
from datetime import date
from unittest.mock import patch
from app import create_app

class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 24)

class ReservationQA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "test.sqlite3")
        clock = patch("app.local_today", return_value=FixedDate.today())
        clock.start()
        self.addCleanup(clock.stop)
        self.app = create_app({"TESTING": True, "AUTH_REQUIRED": False, "DATABASE": self.path, "SECRET_KEY": "qa-only"})
        self.client = self.app.test_client()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE equipment SET quantity=5 WHERE id='EQ-001'")
        self.client.get("/reserve")
        with self.client.session_transaction() as s:
            self.token = s["csrf"]

    def rows(self):
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute("SELECT * FROM reservations ORDER BY id")]

    def submit(self, **changes):
        data = dict(student_id="2026-1-60-001", equipment_id="EQ-001",
                    reservation_date="2026-11-25", start_time="10:00",
                    end_time="11:00", quantity="2", csrf_token=self.token)
        data.update(changes)
        return self.client.post("/reserve", data=data, follow_redirects=True)

    def valid(self, **changes):
        response = self.submit(**changes)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Reservation submitted successfully", response.data)
        return self.rows()[-1]

    def invalid(self, message, **changes):
        before = self.rows()
        response = self.submit(**changes)
        self.assertEqual(response.status_code, 400)
        self.assertIn(message.encode(), response.data)
        self.assertEqual(self.rows(), before)

    def status(self, row, action):
        return self.client.post(f"/reservations/{row['id']}/{action}",
                                data={"csrf_token":self.token}, follow_redirects=True)

    def available(self):
        response = self.client.get("/api/availability", query_string=dict(
            equipment_id="EQ-001", reservation_date="2026-11-25",
            start_time="10:00", end_time="11:00"))
        self.assertEqual(response.status_code, 200)
        return response.json["available"]

    def dashboard(self, pending, approved, rejected):
        import re
        html = self.client.get("/").get_data(as_text=True)
        for label, count in [("Pending requests",pending),("Approved requests",approved),("Rejected requests",rejected)]:
            self.assertRegex(html, rf"<p>{label}</p>\s*<strong>{count}</strong>")

    def test_01_valid(self):
        self.dashboard(0,0,0)
        row = self.valid()
        self.assertEqual((row["student_id"], row["equipment_id"], row["reservation_date"], row["start_time"], row["end_time"], row["quantity"], row["status"]),
                         ("2026-1-60-001","EQ-001","2026-11-25","10:00","11:00",2,"Pending"))
        self.assertEqual(len(self.rows()),1)
        self.dashboard(1,0,0)

    def test_02_excess(self):
        self.invalid("exceeds available", quantity="10")

    def test_03_reversed(self):
        self.invalid("End time must be later", start_time="12:00", end_time="10:00")

    def test_04_overlap(self):
        self.valid()
        self.invalid("overlapping reservation", start_time="10:30", end_time="11:30")

    def test_05_approval_rejection(self):
        a = self.valid()
        b = self.valid(student_id="2026-1-60-002")
        self.assertIn(b"approved", self.status(a,"approve").data)
        self.assertIn(b"rejected", self.status(b,"reject").data)
        self.assertEqual([r["status"] for r in self.rows()],["Approved","Rejected"])
        self.dashboard(0,1,1)

    def test_06_dynamic_quantity(self):
        a = self.valid()
        self.assertEqual(self.available(),5)
        self.status(a,"approve")
        self.assertEqual(self.available(),3)
        self.invalid("exceeds available",student_id="2026-1-60-002",quantity="4")

    def test_07_approval_overbooking(self):
        a = self.valid(quantity="4")
        b = self.valid(student_id="2026-1-60-002",quantity="3")
        self.status(a,"approve")
        response = self.status(b,"approve")
        self.assertIn(b"Insufficient equipment",response.data)
        self.assertEqual([r["status"] for r in self.rows()],["Approved","Pending"])
        self.assertEqual(self.available(),1)

    def test_08_equal(self):
        self.invalid("End time must be later",end_time="10:00")

    def test_09_invalid_quantities(self):
        for q in ("0","-1","1.5"):
            with self.subTest(quantity=q):
                self.invalid("positive integer",quantity=q)

    def test_10_empty(self):
        for field, message in [("student_id","valid student ID"),("equipment_id","valid laboratory equipment"),("reservation_date","valid reservation date"),("start_time","End time must be later"),("end_time","End time must be later"),("quantity","positive integer")]:
            with self.subTest(field=field):
                self.invalid(message,**{field:""})

    def test_11_adjacent(self):
        self.valid()
        self.valid(start_time="11:00",end_time="12:00")
        self.assertEqual(len(self.rows()),2)

    def test_12_different_equipment(self):
        self.valid()
        self.valid(equipment_id="EQ-002")
        self.assertEqual(len(self.rows()),2)

    def test_13_different_date(self):
        self.valid()
        self.valid(reservation_date="2026-11-26")
        self.assertEqual(len(self.rows()),2)

    def test_14_dashboard(self):
        a = self.valid()
        b = self.valid(student_id="2026-1-60-002")
        self.valid(student_id="2026-1-60-003")
        self.status(a,"approve")
        self.status(b,"reject")
        self.dashboard(1,1,1)

    def test_15_persistence(self):
        a = self.valid()
        self.status(a,"approve")
        before = self.rows()
        restarted = create_app({"TESTING":True,"DATABASE":self.path,"SECRET_KEY":"qa-only"})
        self.assertEqual(restarted.test_client().get("/reservations").status_code,200)
        self.assertEqual(self.rows(),before)

    def test_16_rejected_not_overlap(self):
        a = self.valid()
        self.status(a,"reject")
        self.valid()
        self.assertEqual([r["status"] for r in self.rows()],["Rejected","Pending"])

    def test_17_duplicate_approved(self):
        a = self.valid()
        self.invalid("overlapping reservation")
        self.status(a,"approve")
        self.invalid("overlapping reservation")

    def test_18_peak_not_sum(self):
        a = self.valid(quantity="3",end_time="10:30")
        b = self.valid(quantity="3",start_time="10:30")
        self.status(a,"approve")
        self.status(b,"approve")
        self.assertEqual(self.available(),2)
        self.valid(student_id="2026-1-60-002",quantity="2")

if __name__ == "__main__":
    unittest.main(verbosity=2)
