# University Laboratory Equipment Reservation System

**East West University — Software Engineering Lab (Parts A, B and C)**

A local web application for browsing laboratory equipment, submitting reservation requests, checking time-slot availability, and approving or rejecting requests.

## Overview and features

- Dashboard with equipment and reservation-status counts.
- Equipment catalogue.
- Reservation form with student ID, date, time, equipment and quantity validation.
- Live availability feedback through the Flask JSON endpoint `/api/availability`.
- Pending, Approved and Rejected reservation statuses.
- Approval/rejection actions for pending requests.
- SQLite persistence across application restarts.
- Automatic schema creation and sample equipment seeding.
- CSRF tokens for POST forms.
- Automated tests using isolated temporary databases.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript |
| Backend | Python 3, Flask |
| Database | SQLite 3 (`sqlite3`, included with Python) |
| Tests | Python `unittest` |

No MySQL/PostgreSQL server, cloud database, or paid service is required.

## Project structure

```text
412_Final_Lab/
├── app.py
├── requirements.txt
├── schema.sql
├── README.md
├── TEST_REPORT.md
├── test_reservations.py
├── tests/
│   └── test_app.py
├── templates/
│   ├── index.html
│   └── _reservations.html
├── static/
│   ├── app.js
│   └── style.css
└── instance/                 # generated automatically
    └── laboratory.sqlite3   # generated automatically
```

## Requirements

- Windows 10/11, macOS or Linux.
- Python 3.9 or newer.
- A modern web browser.
- Internet access for the first Flask package installation, unless already cached.

## Install and run on Windows

Open the repository folder in VS Code. Open **Terminal → New Terminal** and confirm that the current directory contains `app.py`.

Recommended virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:

```bat
.venv\Scripts\activate.bat
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start Flask:

```powershell
python app.py
```

Open **http://127.0.0.1:5000** in the browser. Keep the terminal open while using the application. Press Ctrl+C to stop the server.

## Database initialization and persistence

The application builds its database path from the Flask instance directory and creates the parent directory automatically. During `create_app()`, it executes `schema.sql` and inserts sample equipment with `INSERT OR IGNORE`. SQLite foreign-key enforcement is enabled on each connection.

The database file is `instance/laboratory.sqlite3`. It contains the equipment inventory and reservation records. Reservation inserts and status changes are committed to this file, so records remain after Flask is restarted. Do not delete the database file if you want to keep demonstration data.

## Frontend/backend connectivity

1. The browser requests a page from a Flask route.
2. Flask renders HTML from `templates/`.
3. The browser loads `static/style.css` and `static/app.js`.
4. JavaScript requests `/api/availability`; Flask reads SQLite and returns JSON.
5. When a form is submitted, Flask validates the request again on the server and writes the reservation to SQLite.
6. Approve/reject actions send POST requests to Flask routes, which update the reservation status in the database.

Server-side validation is authoritative; browser JavaScript is not a security boundary.

## Reservation business rules

- New requests are Pending.
- Pending and Rejected reservations do not consume stock.
- Approved reservations consume stock only during their reserved time interval.
- Availability is calculated using peak simultaneous approved quantity, not by subtracting every reservation for the whole day.
- A student cannot make overlapping Pending or Approved reservations for the same equipment and date; adjacent slots are allowed.
- Only Pending requests can be approved or rejected.
- An approval that exceeds stock is blocked and remains Pending.
- Total equipment stock is not permanently decremented.

Reservation and approval writes use SQLite `BEGIN IMMEDIATE` transactions to serialize competing writes and reduce overbooking risk.

## Automated testing

Run the application test suite:

```powershell
python -m unittest discover -s tests -v
```

Run the Part C reservation QA suite:

```powershell
python -m unittest -v test_reservations
```

Tests use isolated temporary databases. See [TEST_REPORT.md](TEST_REPORT.md) for scenarios and expected outcomes. The report currently records its prior execution status as **NOT RUN**; run both commands on the submission computer and retain the real output before claiming test success.

## Manual smoke test

1. Start Flask and open the dashboard.
2. Confirm equipment appears on the Equipment page.
3. Submit a valid reservation for a future date.
4. Confirm it appears with Pending status.
5. Approve it and confirm Approved status.
6. Submit a conflicting/over-capacity reservation and confirm the server rejects it.
7. Reject another Pending request.
8. Restart Flask and confirm earlier reservations remain visible.

## Troubleshooting

| Problem | Suggested fix |
|---|---|
| `python` is not recognized | Install Python, enable Add Python to PATH, then reopen the terminal. |
| `No module named flask` | Activate the virtual environment and run `python -m pip install -r requirements.txt`. |
| Requirements file not found | Change directory to the repository root containing `requirements.txt`. |
| Port 5000 is already in use | Stop the other process using port 5000, then restart Flask. |
| Browser cannot connect | Check that Flask is still running and visit `http://127.0.0.1:5000`. |
| Records appear missing | Confirm you are running the same repository folder and have not deleted `instance/laboratory.sqlite3`. |
| Invalid form token | Reload the page and submit again. |

## Submission checklist

- [ ] Install dependencies without errors.
- [ ] Start with `python app.py` without a traceback.
- [ ] Open `http://127.0.0.1:5000`.
- [ ] Verify dashboard and equipment list.
- [ ] Submit valid and invalid reservations.
- [ ] Verify approval and rejection.
- [ ] Restart Flask and verify persistence.
- [ ] Run both test commands and save actual terminal output.

## Local-use limitation

The Flask development server is appropriate for this lab demonstration, not production hosting. The portal uses role-based sessions. Set a strong ADMIN_PASSWORD and restrict access to authorized lab participants; do not use real student data in this academic demo.

See [INSTRUCTOR_DEMO_GUIDE.md](INSTRUCTOR_DEMO_GUIDE.md) for the demonstration sequence and ten viva questions.


## Vercel online demonstration with Supabase PostgreSQL

Local execution and tests still use SQLite. Online deployment supports a shared PostgreSQL database when DATABASE_URL is set. This is an academic demonstration only: use fictional student IDs. Admin and student sessions are separated. Admin issues student accounts; real university identity verification is outside this academic demo.

1. Create a dedicated Supabase project (not an unrelated app's database).
2. Run database/postgres.sql in the project's SQL Editor. It creates a private schema, enables RLS, and seeds the 12 equipment rows without overwriting existing stock.
3. From Supabase Connect, choose the IPv4-compatible **Transaction pooler** connection URI (port 6543). Use the actual database password, URL-encoded if necessary. Prefer a dedicated least-privilege database login with explicit schema/table/sequence grants in a production setup.
4. Set DATABASE_URL and a long random SECRET_KEY as server-only environment variables in the Vercel project settings. Do not commit these values or expose them to JavaScript. The adapter requires TLS and disables prepared statements for compatibility with the transaction pooler.
5. Redeploy the latest main commit. Open /api/health and verify it returns status ok, database postgresql, and persistent true. If DATABASE_URL is absent the existing demo still uses temporary SQLite on Vercel; if it is set, the application never falls back to temporary SQLite.
6. Test submitting, reloading, approving/rejecting, duplicate/overlap prevention and overbooking, using fictional IDs. Confirm records remain after a redeployment. Migration does not transfer local demonstration records.

PostgreSQL writes lock the reservation table before checking availability so concurrent approvals cannot overbook. All user values are parameterized. Local tests can continue using separate SQLite files. See https://supabase.com/docs/guides/database/connecting-to-postgres.

Static asset copies in public/static are served by Vercel. Campus photo: East West University website. Logo: Wikimedia Commons.

## Role-based reservation workflow
Set ADMIN_PASSWORD (a strong unique password) as a server-only Vercel secret, in addition to DATABASE_URL and SECRET_KEY. Apply database/student_accounts.sql to existing PostgreSQL deployments before deploying this version. Login as Administrator (leave Student ID blank), create accounts in Student accounts, then give each student their credentials privately. Students sign in with ID and password; requests always use the authenticated ID, and students see only their own requests. Only admin can approve or reject. Approval rechecks availability under a database write lock. If insufficient stock remains, the request stays Pending until reviewed. No open self-registration is provided to prevent claiming someone else's ID. For local admin login set ADMIN_PASSWORD in the shell before launching Flask. Legacy business-rule tests use an explicit testing-only bypass; role tests use authentication. For a real university deployment add institutional SSO, rate limiting, password reset and auditing.
