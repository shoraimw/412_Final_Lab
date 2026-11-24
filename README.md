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

Local execution and tests still use SQLite. Online deployment supports a shared PostgreSQL database when DATABASE_URL is set. This is an academic demonstration only: use fictional student IDs. Admin and student sessions are separated. Admin issues or activates student accounts; real university identity verification is outside this academic demo.

1. Create a dedicated Supabase project (not an unrelated app's database).
2. Run database/postgres.sql in the project's SQL Editor. It creates a private schema, enables RLS, and seeds the 12 equipment rows without overwriting existing stock.
3. From Supabase Connect, choose the IPv4-compatible **Transaction pooler** connection URI (port 6543). Use the actual database password, URL-encoded if necessary. Prefer a dedicated least-privilege database login with explicit schema/table/sequence grants in a production setup.
4. Set DATABASE_URL and a long random SECRET_KEY as server-only environment variables in the Vercel project settings. Do not commit these values or expose them to JavaScript. The adapter requires TLS and disables prepared statements for compatibility with the transaction pooler.
5. Redeploy the latest main commit. Open /api/health and verify it returns status ok, database postgresql, and persistent true. Hosted deployments require DATABASE_URL, SECRET_KEY and ADMIN_PASSWORD. Missing configuration returns a setup page and /api/health returns HTTP 503 with the missing variable names; the app never falls back to temporary SQLite on Vercel.
6. Test submitting, reloading, approving/rejecting, duplicate/overlap prevention and overbooking, using fictional IDs. Confirm records remain after a redeployment. Migration does not transfer local demonstration records.

PostgreSQL writes lock the reservation table before checking availability so concurrent approvals cannot overbook. All user values are parameterized. Local tests can continue using separate SQLite files. See https://supabase.com/docs/guides/database/connecting-to-postgres.

Static asset copies in public/static are served by Vercel. Campus photo: East West University website. Logo: user-supplied East West University artwork, packaged locally.

## Role-based reservation workflow
Set ADMIN_PASSWORD (a strong unique password) as a server-only Vercel secret, in addition to DATABASE_URL and SECRET_KEY. Apply database/student_accounts.sql to existing PostgreSQL deployments before deploying this version. Login as Administrator (enter SWNN), create accounts in Student accounts, then give each student their credentials privately. Students sign in with ID and password; requests always use the authenticated ID, and students see only their own requests. Only admin can approve or reject. Approval rechecks availability under a database write lock. If insufficient stock remains, the request stays Pending until reviewed. Student self-registration creates a pending account; an administrator must verify the ID before activation. For local admin login set ADMIN_PASSWORD in the shell before launching Flask. Legacy business-rule tests use an explicit testing-only bypass; role tests use authentication. For a real university deployment add institutional SSO, rate limiting, password reset and auditing.

### Hosted setup troubleshooting
If /api/health returns configuration_required, set each reported variable in Vercel Settings → Environment Variables (Production), then redeploy. If it returns unavailable, verify the exact Supabase transaction pooler URI, password and database schema. Only when it returns status ok, database postgresql and persistent true should the administrator create student accounts. Do not share secret values.

## Student sign-up and administrator account
Apply database/signup_accounts.sql after database/student_accounts.sql for cloud setups. The current EWU Supabase project already has this migration. The login page links to student sign-up. New students use an ID and matching passwords, and an admin must verify and activate the registration. Public signup cannot create admins. ADMIN is seeded in the admins table; its password is configured only through ADMIN_PASSWORD and the hash is recorded after successful login. Admin signs in with ID SWNN and the password configured in ADMIN_PASSWORD. DEMO-STUDENT is seeded with no usable password; the admin sets an initial password of at least 12 characters through Student accounts, which activates that account. Never use a default password in public deployments. No real university identity verification or email/password recovery is implemented.

The public administrator login ID is SWNN. The existing internal ADMIN database row is retained for compatibility. Configure ADMIN_PASSWORD only in the hosting environment, never in GitHub. Use a strong password for publicly accessible deployments.

## Student-only mode (default)
The public app now defaults to student-only mode. Students register and sign in without administrator activation, and valid requests are automatically confirmed as Approved under the existing reservation write lock. Students can only view their own reservations. Administrator routes are blocked, not made public. Only DATABASE_URL and SECRET_KEY are required on Vercel. Existing accounts and reservation records are preserved; old pending reservations are not silently approved. For the original instructor-required approval workflow, set ENABLE_ADMIN_REVIEW=true plus ADMIN_PASSWORD in the server environment and redeploy. Use fictional IDs only; student-only signup does not establish a real university identity. Database credentials must still be valid in either mode.

## Direct student booking (default public deployment)
Guest mode requires no student account, password or admin approval. Enter a fictional student ID, equipment, date, time and quantity; the system confirms valid bookings automatically. The dashboard uses aggregate totals, and the browser keeps up to five successful booking receipts. It does not disclose reservations via a student-ID-only search. The hosted guest mode uses the Supabase Edge Function ewu-guest-portal and a restricted service-role-only atomic database RPC; the public anon gateway credential is not a secret. Only the existing SECRET_KEY is required in Vercel, and the stale DATABASE_URL is ignored in hosted guest mode. Local guest mode uses SQLite; the original admin review can be restored with ENABLE_ADMIN_REVIEW=true, ADMIN_PASSWORD and a valid DATABASE_URL. This unauthenticated academic demo does not verify real university identity and should not be used for real student data without institutional authentication and abuse prevention.
