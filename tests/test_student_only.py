import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from app import create_app, local_today


class GuestBookingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'test.sqlite3')
        self.app = create_app({'TESTING': True, 'DATABASE': self.path, 'SECRET_KEY': 'test-only', 'ENABLE_ADMIN_REVIEW': False, 'GUEST_MODE': True})
        self.a = self.app.test_client()
        self.b = self.app.test_client()

    def post(self, client, route, **data):
        with client.session_transaction() as sess:
            token = sess['csrf']
        return client.post(route, data=dict(data, csrf_token=token))

    def test_guest_booking(self):
        self.assertEqual(self.a.get('/').status_code, 200)
        self.assertEqual(self.a.get('/login').status_code, 302)
        self.assertEqual(self.a.get('/signup').status_code, 302)
        self.assertEqual(self.a.get('/reserve').status_code, 200)
        self.b.get('/reserve')
        data = dict(equipment_id='EQ-001', reservation_date=(local_today()+timedelta(days=1)).isoformat(), start_time='10:00', end_time='11:00', quantity='6')
        self.assertEqual(self.post(self.a, '/reserve', student_id='TEST-A', **data).status_code, 302)
        blocked = self.post(self.b, '/reserve', student_id='TEST-B', **data)
        self.assertEqual(blocked.status_code, 400)
        self.assertIn(b'data-conflict="Requested quantity exceeds available equipment."', blocked.data)
        self.assertIn(b'id="booking-conflict"', blocked.data)
        self.assertEqual(self.post(self.a, '/reserve', student_id='TEST-A', **data).status_code, 400)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT student_id,status,quantity FROM reservations').fetchall(), [('TEST-A','Approved',6)])
        self.assertIn(b'TEST-A', self.a.get('/reservations').data)
        self.assertNotIn(b'TEST-A', self.b.get('/reservations').data)
        self.assertEqual(self.a.get('/admin/students').status_code, 403)
        self.assertEqual(self.post(self.a, '/reservations/1/reject').status_code, 403)
        self.assertIn(b'Cancel reservation', self.a.get('/reservations').data)
        self.assertEqual(self.post(self.b, '/reservations/1/cancel').status_code, 403)
        self.assertEqual(self.post(self.a, '/reservations/1/cancel').status_code, 302)
        self.assertNotIn(b'TEST-A', self.a.get('/reservations').data)
        self.assertEqual(self.post(self.b, '/reserve', student_id='TEST-B', **data).status_code, 302)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT student_id,status,quantity FROM reservations').fetchall(), [('TEST-B','Approved',6)])


if __name__ == '__main__':
    unittest.main()
