import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from app import create_app, local_today


class StudentOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'test.sqlite3')
        self.app = create_app({'TESTING': True, 'DATABASE': self.path, 'SECRET_KEY': 'test-only', 'ENABLE_ADMIN_REVIEW': False})
        self.a = self.app.test_client()
        self.b = self.app.test_client()

    def post(self, client, route, **data):
        with client.session_transaction() as sess:
            token = sess['csrf']
        return client.post(route, data=dict(data, csrf_token=token))

    def signup_login(self, client, sid):
        client.get('/signup')
        self.assertEqual(self.post(client, '/signup', student_id=sid, password='student-test-1234', confirm_password='student-test-1234').status_code, 302)
        client.get('/login')
        self.assertEqual(self.post(client, '/login', student_id=sid, password='student-test-1234').status_code, 302)
        client.get('/reserve')

    def test_student_only_reservation(self):
        self.signup_login(self.a, 'TEST-A')
        self.signup_login(self.b, 'TEST-B')
        data = dict(equipment_id='EQ-001', reservation_date=(local_today()+timedelta(days=1)).isoformat(), start_time='10:00', end_time='11:00', quantity='6')
        self.assertEqual(self.post(self.a, '/reserve', student_id='TEST-B', **data).status_code, 302)
        self.assertEqual(self.post(self.b, '/reserve', **data).status_code, 400)
        self.assertEqual(self.post(self.a, '/reserve', **data).status_code, 400)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT student_id,status,quantity FROM reservations').fetchall(), [('TEST-A','Approved',6)])
        self.assertNotIn(b'TEST-A', self.b.get('/reservations').data)
        self.assertEqual(self.a.get('/admin/students').status_code, 403)
        self.assertEqual(self.post(self.a, '/reservations/1/reject').status_code, 403)
        guest = self.app.test_client()
        guest.get('/login')
        self.assertEqual(self.post(guest, '/login', role='admin', student_id='SWNN', password='test-only').status_code, 403)


if __name__ == '__main__':
    unittest.main()
