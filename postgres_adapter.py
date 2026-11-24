"""PostgreSQL adapter for the existing reservation service.

Only fixed application SQL passes through this adapter. User values remain
bound parameters. Writes are serialized before availability/overlap checks.
"""
import re
from urllib.parse import urlsplit, unquote


class DatabaseUnavailable(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def safe_reason(exc, phase, direct=False):
    state = getattr(exc, 'sqlstate', None)
    message = str(exc).lower()
    if isinstance(exc, ImportError):
        return 'database_driver_missing'
    if state in ('28P01', '28000') or 'password authentication failed' in message:
        return 'database_authentication_failed'
    if 'tenant or user not found' in message:
        return 'pooler_user_or_host_invalid'
    if state in ('42P01', '42703', '3F000'):
        return 'database_schema_missing'
    if state == '42501' or 'permission denied' in message:
        return 'database_permission_denied'
    if phase == 'connect' and direct:
        return 'direct_connection_failed_use_pooler'
    if phase == 'connect' and ('timeout' in message or 'timed out' in message):
        return 'database_connection_timeout'
    return 'database_connection_failed' if phase == 'connect' else 'database_query_failed'


def translate_sql(statement):
    if statement.strip().upper() == 'BEGIN IMMEDIATE':
        return 'LOCK TABLE ewu_lab.reservations IN SHARE ROW EXCLUSIVE MODE'
    statement = statement.replace(
        'student_id = ? COLLATE NOCASE', 'LOWER(student_id) = LOWER(?)'
    )
    statement = re.sub(
        r'\b(FROM|JOIN|INTO|UPDATE)\s+(equipment|reservations|students|admins)\b',
        lambda m: f'{m.group(1)} ewu_lab.{m.group(2)}',
        statement, flags=re.IGNORECASE,
    )
    return statement.replace('?', '%s')


class PostgresConnection:
    def __init__(self, url):
        try:
            uri = urlsplit(url.strip())
            if uri.scheme not in ('postgres', 'postgresql') or not uri.hostname or not uri.username or not uri.password:
                raise ValueError('invalid URI')
            if unquote(uri.password).lower() in ('[your-password]', 'your-password', '[password]', 'your_password'):
                raise DatabaseUnavailable('database_password_placeholder')
            direct = uri.hostname.startswith('db.') and uri.hostname.endswith('.supabase.co')
        except ValueError:
            raise DatabaseUnavailable('invalid_database_uri') from None
        try:
            import psycopg
            from psycopg.rows import dict_row
            self.connection = psycopg.connect(
                url.strip(), row_factory=dict_row, prepare_threshold=None,
                connect_timeout=10, sslmode='require',
            )
        except Exception as exc:
            raise DatabaseUnavailable(safe_reason(exc, 'connect', direct)) from None

    def execute(self, statement, params=()):
        try:
            return self.connection.execute(translate_sql(statement), params)
        except Exception as exc:
            raise DatabaseUnavailable(safe_reason(exc, 'query')) from None

    def commit(self):
        try:
            self.connection.commit()
        except Exception as exc:
            raise DatabaseUnavailable(safe_reason(exc, 'query')) from None

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False
