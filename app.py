"""EWU Laboratory Equipment Reservation System — Parts A and B."""
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from postgres_adapter import PostgresConnection, DatabaseUnavailable
from werkzeug.security import generate_password_hash, check_password_hash

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for

ROOT = Path(__file__).resolve().parent


def local_today():
    return datetime.now(ZoneInfo('Asia/Dhaka')).date()
SAMPLE_EQUIPMENT = [
    ('EQ-001', 'Digital Oscilloscope', 'Electronics', 8),
    ('EQ-002', 'Digital Multimeter', 'Electronics', 20),
    ('EQ-003', 'DC Power Supply', 'Electronics', 12),
    ('EQ-004', 'Function Generator', 'Electronics', 6),
    ('EQ-005', 'Compound Microscope', 'Biology', 15),
    ('EQ-006', 'Electronic Balance', 'Chemistry', 10),
    ('EQ-007', 'pH Meter', 'Chemistry', 7),
    ('EQ-008', 'Arduino Uno Kit', 'Embedded Systems', 25),
    ('EQ-009', 'Raspberry Pi Kit', 'Embedded Systems', 10),
    ('EQ-010', 'Cisco Network Router', 'Networking', 6),
    ('EQ-011', 'Managed Network Switch', 'Networking', 8),
    ('EQ-012', 'Optical Bench', 'Physics', 5),
]


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get('DATABASE_PATH') or (('/tmp/ewu-laboratory.sqlite3') if os.environ.get('VERCEL') else str(Path(app.instance_path) / 'laboratory.sqlite3')),
        DATABASE_URL=os.environ.get('DATABASE_URL', '').strip() or None,
        ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD'),
        ADMIN_ID='SWNN',
        ENABLE_ADMIN_REVIEW=os.environ.get('ENABLE_ADMIN_REVIEW', '').lower() == 'true',
        AUTH_REQUIRED=True,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        ONLINE_DEMO=bool(os.environ.get('VERCEL')),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=bool(os.environ.get('VERCEL')),
        SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
    )
    if config:
        app.config.update(config)
        if 'DATABASE' in config and 'DATABASE_URL' not in config:
            app.config['DATABASE_URL'] = None
    remote = bool(app.config['DATABASE_URL'])
    admin_review = bool(app.config['ENABLE_ADMIN_REVIEW']) or (app.testing and app.config.get('AUTH_REQUIRED') is False)
    missing = []
    if app.config['ONLINE_DEMO'] and not app.testing:
        for key in (('DATABASE_URL', 'SECRET_KEY', 'ADMIN_PASSWORD') if admin_review else ('DATABASE_URL', 'SECRET_KEY')):
            if not os.environ.get(key, '').strip():
                missing.append(key)
    # A hosted instance must never silently create an isolated reservation database.
    if not remote and not missing:
        Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)

    def db():
        """One connection per request; SQLite locally or shared PostgreSQL."""
        if missing:
            raise RuntimeError('Hosted database configuration incomplete')
        if 'db' not in g:
            if remote:
                g.db = PostgresConnection(app.config['DATABASE_URL'])
            else:
                g.db = sqlite3.connect(app.config['DATABASE'], timeout=10)
                g.db.row_factory = sqlite3.Row
                g.db.execute('PRAGMA foreign_keys = ON')
        return g.db

    @app.errorhandler(DatabaseUnavailable)
    def handle_database_unavailable(error):
        app.logger.warning('Database request failed: %s', error.reason)
        if request.path.startswith('/api/'):
            return jsonify(status='unavailable', reason=error.reason), 503
        return render_template('index.html', page='database_error', database_reason=error.reason), 503

    @app.after_request
    def protect_account_responses(response):
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    if not remote and not missing:
        with app.app_context():
            connection = db()
            connection.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
            connection.executemany(
                'INSERT OR IGNORE INTO equipment VALUES (?, ?, ?, ?)', SAMPLE_EQUIPMENT
            )
            if 'approved' not in {row['name'] for row in connection.execute('PRAGMA table_info(students)')}:
                connection.execute('ALTER TABLE students ADD COLUMN approved INTEGER NOT NULL DEFAULT 1 CHECK (approved IN (0,1))')
            connection.execute("INSERT OR IGNORE INTO admins(username) VALUES ('ADMIN')")
            connection.execute("INSERT OR IGNORE INTO students(student_id,password_hash,approved) VALUES ('DEMO-STUDENT','',0)")
            connection.commit()


    @app.before_request
    def require_configuration():
        if missing and request.endpoint not in ('health', 'static', None):
            return render_template('index.html', page='setup'), 503

    auth_required = not (app.testing and app.config.get('AUTH_REQUIRED') is False)

    def role():
        if not auth_required:
            return 'legacy'
        current = session.get('role')
        if current == 'admin' and not admin_review:
            return None
        return current

    def student_identity():
        return session.get('student_id') if role() == 'student' else None

    @app.before_request
    def require_login():
        if not admin_review and request.endpoint in ('update_status', 'student_accounts', 'approve_student'):
            abort(403)
        if not auth_required or request.endpoint in ('login', 'signup', 'static', 'health', None):
            return
        if role() not in ('admin', 'student'):
            if request.endpoint == 'availability':
                return jsonify(error='Login required.'), 401
            if request.method == 'POST':
                abort(403)
            return redirect(url_for('login'))
        if request.endpoint in ('update_status', 'student_accounts', 'approve_student') and role() != 'admin':
            abort(403)
        if request.endpoint == 'reserve' and role() != 'student':
            abort(403)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if role() in ('student', 'admin'):
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            selected = request.form.get('role', 'student')
            if selected == 'admin' and not admin_review:
                abort(403)
            username = request.form.get('student_id', '').strip().upper()
            password = request.form.get('password', '')
            if len(password) > 256 or len(username) > 40:
                abort(400)
            authenticated = False
            if selected == 'admin':
                expected = app.config.get('ADMIN_PASSWORD') or ''
                if expected and secrets.compare_digest(password.encode(), expected.encode()) and username == app.config['ADMIN_ID']:
                    connection = db()
                    account = connection.execute("SELECT password_hash, enabled FROM admins WHERE username = 'ADMIN'").fetchone()
                    authenticated = bool(account and account['enabled'])
                    if authenticated and (not account['password_hash'] or not check_password_hash(account['password_hash'], password)):
                        connection.execute("UPDATE admins SET password_hash = ? WHERE username = 'ADMIN'", (generate_password_hash(password),))
                        connection.commit()
            elif selected == 'student':
                account = db().execute('SELECT password_hash, approved FROM students WHERE student_id = ?', (username,)).fetchone()
                authenticated = bool(account and account['password_hash'] and check_password_hash(account['password_hash'], password))
                if authenticated and not account['approved']:
                    if admin_review:
                        flash('Your account is awaiting administrator approval.', 'error')
                        return render_template('index.html', page='login', selected_role=selected, entered_id=username), 403
                    connection = db()
                    connection.execute('UPDATE students SET approved = 1 WHERE student_id = ?', (username,))
                    connection.commit()
            if authenticated:
                session.clear()
                session['role'] = selected
                if selected == 'student':
                    session['student_id'] = username
                session.permanent = True
                return redirect(url_for('dashboard'))
            flash('Invalid login details. Check your password or create a student account first.', 'error')
            return render_template('index.html', page='login', selected_role=selected, entered_id=username), 401
        return render_template('index.html', page='login')

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if role() in ('student', 'admin'):
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('student_id', '').strip().upper()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')
            if not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,39}', username) or username in ('ADMIN', app.config['ADMIN_ID']) or not 12 <= len(password) <= 256 or password != confirm:
                flash('Enter a valid student ID and matching passwords of at least 12 characters.', 'error')
                return render_template('index.html', page='signup', entered_id=username), 400
            connection = db()
            cursor = connection.execute(
                "INSERT INTO students (student_id, password_hash, approved) VALUES (?, ?, ?) ON CONFLICT (student_id) DO UPDATE SET password_hash = excluded.password_hash, approved = excluded.approved WHERE students.password_hash = ''",
                (username, generate_password_hash(password), 0 if admin_review else 1),
            )
            connection.commit()
            if not cursor.rowcount:
                flash('This ID is already registered. Contact your administrator for account help.', 'error')
                return render_template('index.html', page='signup', entered_id=username), 409
            flash('Account created. Ask the administrator to verify and activate your student ID before signing in.' if admin_review else 'Account created successfully. You can sign in now.', 'success')
            return redirect(url_for('login'))
        return render_template('index.html', page='signup')

    @app.post('/admin/students/<student_id>/approve')
    def approve_student(student_id):
        connection = db()
        cursor = connection.execute('UPDATE students SET approved = 1 WHERE student_id = ? AND approved = 0 AND password_hash <> ?', (student_id, ''))
        connection.commit()
        flash('Student account activated.' if cursor.rowcount else 'No pending account with a password was found.', 'success' if cursor.rowcount else 'error')
        return redirect(url_for('student_accounts'))

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/admin/students', methods=['GET', 'POST'])
    def student_accounts():
        if request.method == 'POST':
            username = request.form.get('student_id', '').strip().upper()
            password = request.form.get('password', '')
            if not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,39}', username) or username in ('ADMIN', app.config['ADMIN_ID']) or not 12 <= len(password) <= 256:
                flash('Enter a valid student ID and a password of at least 12 characters.', 'error')
                return redirect(url_for('student_accounts'))
            connection = db()
            cursor = connection.execute(
                "INSERT INTO students (student_id, password_hash, approved) VALUES (?, ?, 1) ON CONFLICT (student_id) DO UPDATE SET password_hash = excluded.password_hash, approved = 1 WHERE students.password_hash = ''",
                (username, generate_password_hash(password)),
            )
            connection.commit()
            if cursor.rowcount:
                flash('Student account created. Share credentials privately.', 'success')
            else:
                flash('This student account already exists.', 'error')
            return redirect(url_for('student_accounts'))
        accounts = db().execute("SELECT student_id, approved, CASE WHEN password_hash = '' THEN 0 ELSE 1 END AS has_password FROM students ORDER BY student_id").fetchall()
        return render_template('index.html', page='students', accounts=accounts)

    @app.context_processor
    def common():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(24)
        return {'csrf_token': session['csrf'], 'today': local_today().isoformat(), 'online_demo': app.config['ONLINE_DEMO'], 'persistent_database': remote and not missing, 'configuration_missing': missing, 'admin_review': admin_review, 'role': role(), 'current_student': student_identity(), 'can_manage': role() in ('admin', 'legacy'), 'can_reserve': role() in ('student', 'legacy')}

    @app.before_request
    def verify_csrf():
        if request.method == 'POST':
            token = session.get('csrf', '')
            if not token or not secrets.compare_digest(token, request.form.get('csrf_token', '')):
                abort(400, 'Invalid form token. Reload the page and try again.')

    def inventory():
        return db().execute('SELECT * FROM equipment ORDER BY id').fetchall()

    def reservations():
        query = '''SELECT r.*, e.name AS equipment_name FROM reservations r
                   JOIN equipment e ON e.id = r.equipment_id'''
        student = student_identity()
        if student:
            return db().execute(query + ' WHERE LOWER(r.student_id) = LOWER(?) ORDER BY r.id DESC', (student,)).fetchall()
        return db().execute(query + ' ORDER BY r.id DESC').fetchall()

    @app.get('/api/health')
    def health():
        if missing:
            return jsonify(status='configuration_required', missing=missing, persistent=False), 503
        if remote:
            from urllib.parse import urlsplit, unquote
            try:
                uri = urlsplit(app.config['DATABASE_URL'].strip())
                if uri.scheme not in ('postgres', 'postgresql') or not uri.hostname or not uri.username or not uri.password:
                    return jsonify(status='unavailable', reason='invalid_database_uri'), 503
                if unquote(uri.password).lower() in ('[your-password]', 'your-password', '[password]', 'your_password'):
                    return jsonify(status='unavailable', reason='database_password_placeholder'), 503
                if app.config['ONLINE_DEMO'] and uri.hostname.endswith('.supabase.co') and uri.hostname.startswith('db.'):
                    # Direct Supabase hosts may be IPv6-only. Report this only if connection fails.
                    direct_host = True
                else:
                    direct_host = False
            except ValueError:
                return jsonify(status='unavailable', reason='invalid_database_uri'), 503
        else:
            direct_host = False
        phase = 'connect'
        try:
            connection = db()
            phase = 'schema'
            connection.execute('SELECT COUNT(*) AS total FROM equipment').fetchone()
            connection.execute('SELECT COUNT(*) AS total FROM reservations').fetchone()
            connection.execute('SELECT COUNT(*) AS total FROM students').fetchone()
            if admin_review:
                connection.execute('SELECT COUNT(*) AS total FROM admins').fetchone()
            connection.execute('SELECT approved FROM students LIMIT 1').fetchone()
        except Exception as exc:
            # Never return raw exception messages: drivers may include credential-bearing DSNs.
            state = getattr(exc, 'sqlstate', None)
            message = str(exc).lower()
            if isinstance(exc, DatabaseUnavailable):
                reason = exc.reason
            elif isinstance(exc, ImportError):
                reason = 'database_driver_missing'
            elif state in ('28P01', '28000') or 'password authentication failed' in message:
                reason = 'database_authentication_failed'
            elif 'tenant or user not found' in message:
                reason = 'pooler_user_or_host_invalid'
            elif state in ('42P01', '42703', '3F000'):
                reason = 'database_schema_missing'
            elif state == '42501' or 'permission denied' in message:
                reason = 'database_permission_denied'
            elif phase == 'connect' and direct_host:
                reason = 'direct_connection_failed_use_pooler'
            elif phase == 'connect' and ('timeout' in message or 'timed out' in message):
                reason = 'database_connection_timeout'
            elif phase == 'connect':
                reason = 'database_connection_failed'
            else:
                reason = 'database_query_failed'
            app.logger.warning('Database health check failed: %s (%s)', reason, phase)
            return jsonify(status='unavailable', reason=reason), 503
        mode = 'postgresql' if remote else ('temporary-sqlite' if app.config['ONLINE_DEMO'] else 'sqlite')
        return jsonify(status='ok', database=mode, persistent=remote or not app.config['ONLINE_DEMO'])

    @app.get('/')
    def dashboard():
        connection = db()
        stats = {'equipment': connection.execute('SELECT COUNT(*) AS total FROM equipment').fetchone()['total'],
                 'Pending': 0, 'Approved': 0, 'Rejected': 0}
        student = student_identity()
        query = 'SELECT status, COUNT(*) AS total FROM reservations'
        groups = connection.execute(query + ' WHERE LOWER(student_id) = LOWER(?) GROUP BY status', (student,)) if student else connection.execute(query + ' GROUP BY status')
        for row in groups:
            stats[row['status']] = row['total']
        return render_template('index.html', page='dashboard', stats=stats, rows=reservations()[:5])

    @app.get('/equipment')
    def equipment():
        return render_template('index.html', page='equipment', items=inventory())

    @app.route('/reserve', methods=['GET', 'POST'])
    def reserve():
        values = request.form if request.method == 'POST' else {}
        if request.method == 'POST':
            student = student_identity() or values.get('student_id', '').strip()
            equipment_id = values.get('equipment_id', '')
            day = values.get('reservation_date', '')
            start = values.get('start_time', '')
            end = values.get('end_time', '')
            error = None
            connection = db()
            connection.execute('BEGIN IMMEDIATE')
            item = connection.execute('SELECT * FROM equipment WHERE id = ?', (equipment_id,)).fetchone()
            try:
                raw_quantity = values.get('quantity', '')
                if not re.fullmatch(r'[0-9]+', raw_quantity):
                    raise ValueError
                quantity = int(raw_quantity)
            except ValueError:
                quantity = 0
            if not student or len(student) > 40 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', student):
                error = 'Enter a valid student ID (letters, numbers and hyphens only).'
            elif item is None:
                error = 'Select valid laboratory equipment.'
            else:
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
                        raise ValueError
                    if date.fromisoformat(day) < local_today():
                        error = 'Reservation date cannot be in the past.'
                except ValueError:
                    error = 'Enter a valid reservation date.'
                if not error and (not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in (start, end)) or start >= end):
                    error = 'End time must be later than start time. Enter valid times.'
                if not error and quantity <= 0:
                    error = 'Quantity must be a positive integer.'
                slot = dict(equipment_id=equipment_id, reservation_date=day, start_time=start, end_time=end)
                if not error and overlapping_student(connection, student, slot):
                    error = 'An overlapping reservation already exists.'
                if not error and quantity > item['quantity'] - peak_reserved(connection, slot):
                    error = 'Requested quantity exceeds available equipment.'
            if error:
                connection.rollback()
                flash(error, 'error')
                return render_template('index.html', page='reserve', items=inventory(), values=values), 400
            connection.execute(
                '''INSERT INTO reservations
                   (student_id, equipment_id, reservation_date, start_time, end_time, quantity, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (student, equipment_id, day, start, end, quantity, 'Pending' if admin_review else 'Approved'),
            )
            connection.commit()
            flash('Reservation submitted successfully. Status: Pending.' if admin_review else 'Reservation confirmed successfully. Status: Approved.', 'success')
            return redirect(url_for('manage'))
        return render_template('index.html', page='reserve', items=inventory(), values=values)

    @app.get('/reservations')
    def manage():
        return render_template('index.html', page='reservations', rows=reservations())

    def overlapping_student(connection, student, row):
        return connection.execute(
            """SELECT 1 FROM reservations WHERE student_id = ? COLLATE NOCASE
               AND equipment_id = ? AND reservation_date = ?
               AND status IN ('Pending', 'Approved')
               AND start_time < ? AND end_time > ? LIMIT 1""",
            (student, row['equipment_id'], row['reservation_date'], row['end_time'], row['start_time']),
        ).fetchone() is not None

    @app.get('/api/availability')
    def availability():
        slot = {key: request.args.get(key, '') for key in
                ('equipment_id', 'reservation_date', 'start_time', 'end_time')}
        day, start, end = (slot[key] for key in ('reservation_date', 'start_time', 'end_time'))
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day) or date.fromisoformat(day) < local_today():
                raise ValueError
            if not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in (start, end)) or start >= end:
                raise ValueError
        except ValueError:
            return jsonify(error='Enter a valid date and time slot.'), 400
        connection = db()
        item = connection.execute('SELECT quantity FROM equipment WHERE id = ?', (slot['equipment_id'],)).fetchone()
        if item is None:
            return jsonify(error='Select valid laboratory equipment.'), 400
        available = max(0, item['quantity'] - peak_reserved(connection, slot))
        student = student_identity() or (request.args.get('student_id', '').strip() if not auth_required else '')
        return jsonify(available=available, stock=item['quantity'],
                       overlap=bool(student and overlapping_student(connection, student, slot)))

    def peak_reserved(connection, row):
        """Sweep overlapping approved intervals; end events precede start events."""
        events = []
        for booking in connection.execute(
            '''SELECT start_time, end_time, quantity FROM reservations
               WHERE equipment_id = ? AND reservation_date = ? AND status = 'Approved'
               AND start_time < ? AND end_time > ?''',
            (row['equipment_id'], row['reservation_date'], row['end_time'], row['start_time']),
        ):
            events.append((max(booking['start_time'], row['start_time']), booking['quantity']))
            events.append((min(booking['end_time'], row['end_time']), -booking['quantity']))
        peak = active = 0
        for _, delta in sorted(events):
            active += delta
            peak = max(peak, active)
        return peak

    @app.post('/reservations/<int:reservation_id>/<action>')
    def update_status(reservation_id, action):
        status = {'approve': 'Approved', 'reject': 'Rejected'}.get(action)
        if status is None:
            abort(404)
        connection = db()
        # Lock writes before reading availability to prevent simultaneous overbooking.
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute(
                '''SELECT r.*, e.quantity AS stock FROM reservations r
                   JOIN equipment e ON e.id = r.equipment_id WHERE r.id = ?''',
                (reservation_id,),
            ).fetchone()
            if row is None:
                abort(404)
            if row['status'] != 'Pending':
                flash('Only pending reservations can be changed.', 'error')
            elif status == 'Approved' and peak_reserved(connection, row) + row['quantity'] > row['stock']:
                flash('Insufficient equipment available for approval. Request remains Pending.', 'error')
            else:
                connection.execute('UPDATE reservations SET status = ? WHERE id = ?', (status, reservation_id))
                flash(f'Reservation #{reservation_id} {status.lower()}.', 'success')
        return redirect(url_for('manage'))

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
