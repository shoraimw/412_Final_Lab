import unittest
from postgres_adapter import PostgresConnection, DatabaseUnavailable, safe_reason


class DatabaseFailureTests(unittest.TestCase):
    def test_rejects_https_project_url(self):
        with self.assertRaises(DatabaseUnavailable) as result:
            PostgresConnection('https://example.supabase.co')
        self.assertEqual(result.exception.reason, 'invalid_database_uri')

    def test_rejects_placeholder_password(self):
        with self.assertRaises(DatabaseUnavailable) as result:
            PostgresConnection('postgresql://postgres.example:[YOUR-PASSWORD]@example.com:6543/postgres'.replace('[YOUR-PASSWORD]', '%5BYOUR-PASSWORD%5D'))
        self.assertEqual(result.exception.reason, 'database_password_placeholder')

    def test_safe_errors_do_not_disclose_connection_string(self):
        self.assertEqual(safe_reason(Exception('password authentication failed'), 'connect'), 'database_authentication_failed')
        self.assertEqual(safe_reason(Exception('connection timed out'), 'connect'), 'database_connection_timeout')


if __name__ == '__main__':
    unittest.main()
