import re
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from app import create_app


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp.name) / 'test.sqlite3')
        self.app = create_app({'TESTING': True, 'AUTH_REQUIRED': False, 'DATABASE': self.database, 'SECRET_KEY': 'test'})
        self.client = self.app.test_client()
        self.day = (date.today() + timedelta(days=1)).isoformat()
        self.client.get('/reserve')
        with self.client.session_transaction() as session:
            self.token = session['csrf']

    def tearDown(self):
        self.temp.cleanup()

    def submit(self, **changes):
        data = dict(csrf_token=self.token, student_id='2024-1-60-001',
                    equipment_id='EQ-001', reservation_date=self.day,
                    start_time='10:00', end_time='11:00', quantity='2')
        data.update(changes)
        return self.client.post('/reserve', data=data, follow_redirects=True)

    def status(self, number, action):
        return self.client.post(f'/reservations/{number}/{action}',
                                data={'csrf_token': self.token}, follow_redirects=True)

    def query(self, sql):
        with sqlite3.connect(self.database) as connection:
            return connection.execute(sql).fetchall()

    def test_pages_and_seed(self):
        for route in ['/', '/equipment', '/reserve', '/reservations']:
            self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(self.query('SELECT COUNT(*) FROM equipment'), [(12,)])

    def test_submit_approve_reject_and_dashboard(self):
        self.assertIn(b'Pending', self.submit().data)
        self.submit(student_id='2024-1-60-002')
        self.submit(student_id='2024-1-60-003')
        self.status(1, 'approve')
        self.status(2, 'reject')
        self.assertEqual(self.query('SELECT status FROM reservations ORDER BY id'),
                         [('Approved',), ('Rejected',), ('Pending',)])
        html = self.client.get('/').get_data(as_text=True)
        self.assertEqual(re.findall(r'<strong>(\d+)</strong>', html), ['12', '1', '1', '1'])
        self.status(1, 'reject')
        self.assertEqual(self.query('SELECT status FROM reservations WHERE id=1'), [('Approved',)])

    def test_invalid_requests(self):
        for changes in [{'student_id': ''}, {'equipment_id': 'fake'}, {'quantity': '0'},
                        {'quantity': '9'}, {'end_time': '09:00'}, {'reservation_date': '2020-01-01'},
                        {'reservation_date': 'invalid'}, {'quantity': '1.5'}]:
            self.assertEqual(self.submit(**changes).status_code, 400)
        self.assertEqual(self.query('SELECT COUNT(*) FROM reservations'), [(0,)])

    def test_overbooking_and_adjacent_slots(self):
        self.submit(quantity='8')
        self.submit(student_id='2024-1-60-002', quantity='1')
        self.status(1, 'approve')
        self.assertIn(b'Insufficient equipment available for approval', self.status(2, 'approve').data)
        self.assertEqual(self.submit(student_id='2024-1-60-003', quantity='1').status_code, 400)
        self.submit(start_time='11:00', end_time='12:00', quantity='8')
        self.status(3, 'approve')
        self.assertEqual(self.query('SELECT status FROM reservations ORDER BY id'),
                         [('Approved',), ('Pending',), ('Approved',)])

    def test_overlap_and_rejection(self):
        self.submit()
        for changes in ({}, {'start_time':'10:30','end_time':'11:30'}, {'start_time':'09:30','end_time':'10:30'}):
            response = self.submit(**changes)
            self.assertEqual(response.status_code, 400)
            self.assertIn(b'An overlapping reservation already exists', response.data)
        self.assertEqual(self.query('SELECT COUNT(*) FROM reservations'), [(1,)])
        self.assertEqual(self.submit(equipment_id='EQ-002').status_code, 200)
        self.status(1, 'reject')
        self.assertEqual(self.submit().status_code, 200)

    def test_peak_not_sum_and_live_availability(self):
        self.submit(quantity='5')
        self.submit(student_id='B', start_time='11:00', end_time='12:00', quantity='5')
        self.status(1, 'approve')
        self.status(2, 'approve')
        slot = dict(equipment_id='EQ-001', reservation_date=self.day, start_time='10:00', end_time='12:00')
        self.assertEqual(self.client.get('/api/availability', query_string=slot).json['available'], 3)
        self.assertEqual(self.submit(student_id='C', end_time='12:00', quantity='4').status_code, 400)
        self.assertEqual(self.submit(student_id='C', end_time='12:00', quantity='3').status_code, 200)
        self.status(3, 'approve')
        self.assertEqual(self.client.get('/api/availability', query_string=slot).json['available'], 0)
        self.assertEqual(self.query("SELECT quantity FROM equipment WHERE id='EQ-001'"), [(8,)])
        self.status(3, 'approve')
        self.assertEqual(self.query("SELECT status FROM reservations WHERE id=3"), [('Approved',)])

    def test_equal_time_negative_and_missing_fields(self):
        for changes in ({'quantity':'-1'}, {'end_time':'10:00'}, {'start_time':''}, {'reservation_date':''}, {'quantity':''}):
            self.assertEqual(self.submit(**changes).status_code, 400)
        self.assertEqual(self.query('SELECT COUNT(*) FROM reservations'), [(0,)])

    def test_restart_persists_data(self):
        self.submit()
        self.status(1, 'approve')
        restarted = create_app({'TESTING': True, 'DATABASE': self.database})
        self.assertIn(b'Approved', restarted.test_client().get('/reservations').data)
        self.assertEqual(self.query('SELECT COUNT(*) FROM equipment'), [(12,)])

    def test_csrf_and_invalid_action(self):
        self.assertEqual(self.client.post('/reserve', data={}).status_code, 400)
        self.assertEqual(self.status(999, 'approve').status_code, 404)
        self.assertEqual(self.status(1, 'delete').status_code, 404)


if __name__ == '__main__':
    unittest.main()
