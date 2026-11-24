"""EWU Laboratory Equipment Reservation System — Parts A and B."""
import os
import re
import secrets
import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

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
        ONLINE_DEMO=bool(os.environ.get('VERCEL')),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=bool(os.environ.get('VERCEL')),
        SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
    )
    if config:
        app.config.update(config)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)

    def db():
        """One SQLite connection per request; enforce foreign keys."""
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    with app.app_context():
        connection = db()
        connection.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        connection.executemany(
            'INSERT OR IGNORE INTO equipment VALUES (?, ?, ?, ?)', SAMPLE_EQUIPMENT
        )
        connection.commit()

    @app.context_processor
    def common():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(24)
        return {'csrf_token': session['csrf'], 'today': local_today().isoformat(), 'online_demo': app.config['ONLINE_DEMO']}

    @app.before_request
    def verify_csrf():
        if request.method == 'POST':
            token = session.get('csrf', '')
            if not token or not secrets.compare_digest(token, request.form.get('csrf_token', '')):
                abort(400, 'Invalid form token. Reload the page and try again.')

    def inventory():
        return db().execute('SELECT * FROM equipment ORDER BY id').fetchall()

    def reservations():
        return db().execute(
            '''SELECT r.*, e.name AS equipment_name FROM reservations r
               JOIN equipment e ON e.id = r.equipment_id ORDER BY r.id DESC'''
        ).fetchall()

    @app.get('/')
    def dashboard():
        connection = db()
        stats = {'equipment': connection.execute('SELECT COUNT(*) FROM equipment').fetchone()[0],
                 'Pending': 0, 'Approved': 0, 'Rejected': 0}
        for row in connection.execute('SELECT status, COUNT(*) AS total FROM reservations GROUP BY status'):
            stats[row['status']] = row['total']
        return render_template('index.html', page='dashboard', stats=stats, rows=reservations()[:5])

    @app.get('/equipment')
    def equipment():
        return render_template('index.html', page='equipment', items=inventory())

    @app.route('/reserve', methods=['GET', 'POST'])
    def reserve():
        values = request.form if request.method == 'POST' else {}
        if request.method == 'POST':
            student = values.get('student_id', '').strip()
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
                   (student_id, equipment_id, reservation_date, start_time, end_time, quantity)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (student, equipment_id, day, start, end, quantity),
            )
            connection.commit()
            flash('Reservation submitted successfully. Status: Pending.', 'success')
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
        student = request.args.get('student_id', '').strip()
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
