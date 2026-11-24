"""Pure unit tests for the PostgreSQL SQL adapter (no credentials required)."""
import unittest
from postgres_adapter import translate_sql


class PostgresAdapterTests(unittest.TestCase):
    def test_write_lock(self):
        self.assertEqual(translate_sql('BEGIN IMMEDIATE'),
                         'LOCK TABLE ewu_lab.reservations IN SHARE ROW EXCLUSIVE MODE')

    def test_bound_parameters_and_overlap(self):
        sql = translate_sql('SELECT 1 FROM reservations WHERE student_id = ? COLLATE NOCASE AND equipment_id = ?')
        self.assertEqual(sql, 'SELECT 1 FROM ewu_lab.reservations WHERE LOWER(student_id) = LOWER(%s) AND equipment_id = %s')

    def test_join_and_update(self):
        self.assertEqual(translate_sql('SELECT r.* FROM reservations r JOIN equipment e ON e.id = r.equipment_id'),
                         'SELECT r.* FROM ewu_lab.reservations r JOIN ewu_lab.equipment e ON e.id = r.equipment_id')
        self.assertEqual(translate_sql('UPDATE reservations SET status = ? WHERE id = ?'),
                         'UPDATE ewu_lab.reservations SET status = %s WHERE id = %s')


if __name__ == '__main__':
    unittest.main()
