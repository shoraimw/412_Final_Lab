import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from app import create_app, local_today


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.temp.name) / 'test.sqlite3'), 'SECRET_KEY': 'test-only', 'ADMIN_PASSWORD': 'test-admin-123456'})
        self.admin = self.app.test_client()
        self.student = self.app.test_client()
        self.other = self.app.test_client()

    def post(self, client, route, **data):
        with client.session_transaction() as sess:
            token = sess['csrf']
        return client.post(route, data=dict(data, csrf_token=token))

    def login(self, client, role, student_id='', password='test-admin-123456'):
        client.get('/login')
        return self.post(client, '/login', role=role, student_id=student_id, password=password)

    def test_permissions_ownership_and_approval(self):
        self.assertEqual(self.student.get('/reserve').status_code, 302)
        self.assertEqual(self.login(self.admin, 'admin').status_code, 302)
        self.admin.get('/admin/students')
        for sid in ('TEST-A', 'TEST-B'):
            self.assertEqual(self.post(self.admin, '/admin/students', student_id=sid, password='student-test-1234').status_code, 302)
        self.assertEqual(self.login(self.student, 'student', 'TEST-A', 'student-test-1234').status_code, 302)
        self.student.get('/reserve')
        day = (local_today() + timedelta(days=1)).isoformat()
        self.assertEqual(self.post(self.student, '/reserve', student_id='TEST-B', equipment_id='EQ-001', reservation_date=day, start_time='10:00', end_time='11:00', quantity='6').status_code, 302)
        mine = self.student.get('/reservations').data
        self.assertIn(b'TEST-A', mine)
        self.assertNotIn(b'TEST-B', mine)
        self.assertNotIn(b'>Approve</button>', mine)
        self.assertEqual(self.post(self.student, '/reservations/1/approve').status_code, 403)
        self.assertEqual(self.student.get('/admin/students').status_code, 403)
        self.assertEqual(self.login(self.other, 'student', 'TEST-B', 'student-test-1234').status_code, 302)
        self.other.get('/reserve')
        self.assertNotIn(b'TEST-A', self.other.get('/reservations').data)
        self.assertEqual(self.post(self.other, '/reserve', equipment_id='EQ-001', reservation_date=day, start_time='10:00', end_time='11:00', quantity='6').status_code, 302)
        self.assertEqual(self.post(self.admin, '/reservations/1/approve').status_code, 302)
        self.assertEqual(self.post(self.admin, '/reservations/2/approve').status_code, 302)
        self.assertIn(b'Insufficient equipment available', self.admin.get('/reservations').data)
        self.assertIn(b'Pending', self.other.get('/reservations').data)
        self.assertEqual(self.post(self.admin, '/reservations/2/reject').status_code, 302)
        self.assertIn(b'Rejected', self.other.get('/reservations').data)


    def test_signup_requires_approval(self):
        self.student.get('/signup')
        self.assertEqual(self.post(self.student, '/signup', student_id='SIGNUP-01', password='student-test-1234', confirm_password='student-test-1234', role='admin').status_code, 302)
        self.assertEqual(self.login(self.student, 'student', 'SIGNUP-01', 'student-test-1234').status_code, 403)
        self.assertEqual(self.login(self.admin, 'admin').status_code, 302)
        self.admin.get('/admin/students')
        self.assertEqual(self.post(self.admin, '/admin/students/SIGNUP-01/approve').status_code, 302)
        self.assertEqual(self.login(self.student, 'student', 'SIGNUP-01', 'student-test-1234').status_code, 302)
        self.assertEqual(self.student.get('/admin/students').status_code, 403)


if __name__ == '__main__':
    unittest.main()
