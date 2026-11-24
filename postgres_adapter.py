"""PostgreSQL adapter for the existing reservation service.

Only fixed application SQL passes through this adapter. User values remain
bound parameters. Writes are serialized before availability/overlap checks.
"""
import re


def translate_sql(statement):
    if statement.strip().upper() == 'BEGIN IMMEDIATE':
        return 'LOCK TABLE ewu_lab.reservations IN SHARE ROW EXCLUSIVE MODE'
    statement = statement.replace(
        'student_id = ? COLLATE NOCASE', 'LOWER(student_id) = LOWER(?)'
    )
    statement = re.sub(
        r'\b(FROM|JOIN|INTO|UPDATE)\s+(equipment|reservations)\b',
        lambda m: f'{m.group(1)} ewu_lab.{m.group(2)}',
        statement, flags=re.IGNORECASE,
    )
    return statement.replace('?', '%s')


class PostgresConnection:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.connection = psycopg.connect(
            url, row_factory=dict_row, prepare_threshold=None,
            connect_timeout=10, sslmode='require',
        )

    def execute(self, statement, params=()):
        return self.connection.execute(translate_sql(statement), params)

    def commit(self):
        self.connection.commit()

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
