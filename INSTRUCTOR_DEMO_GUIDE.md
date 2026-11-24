# Instructor Demonstration Guide
## University Laboratory Equipment Reservation System

### 1. Start the application (Windows)

Open the repository folder in VS Code. In Terminal, make sure the current directory contains `app.py`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use Command Prompt and run `.venv\Scripts\activate.bat`. Then open **http://127.0.0.1:5000**. Keep the terminal running.

### 2. Explain the architecture

```text
Browser (HTML / CSS / JavaScript)
       | HTTP requests; fetch() for live availability
       v
Flask backend (app.py)
       | SQL queries and transactions
       v
SQLite file (instance/laboratory.sqlite3)
```

- `templates/`: HTML pages rendered by Flask.
- `static/`: browser JavaScript and CSS.
- `app.py`: routes, validation, reservation logic and database access.
- `schema.sql`: database table definitions.
- SQLite is a local file database; there is no separate database server.

### 3. Demonstration sequence

1. **Dashboard:** show equipment count and Pending, Approved and Rejected counts.
2. **Equipment:** open the equipment catalogue and show the available equipment records.
3. **Frontend/backend connection:** open the reservation form. Change equipment, date or time. Explain that JavaScript calls `/api/availability`; Flask checks SQLite and returns JSON.
4. **Valid reservation:** choose a future date, a valid student ID (letters, numbers and hyphens), equipment, positive whole-number quantity, and an end time later than the start time. Submit and show the Pending record.
5. **Invalid reservation:** try a past date, zero quantity, an end time earlier than the start time, or an overlapping reservation for the same student/equipment/date. Show that Flask rejects it.
6. **Approval:** approve a Pending request. Show its status becomes Approved. Explain that approved quantities affect stock only during overlapping time intervals.
7. **Rejection:** reject another Pending request. Show Rejected status and explain that it does not consume stock.
8. **Persistence:** stop Flask with Ctrl+C, restart with `python app.py`, reload Reservations and show that existing records remain.
9. Leave the browser on **http://127.0.0.1:5000**.

### 4. Reservation rules to explain

- New requests begin as Pending.
- Pending and Rejected requests do not consume equipment stock.
- Approved reservations count against stock only during their reserved time interval.
- Peak simultaneous approved quantity is used to calculate availability.
- A student cannot create overlapping Pending or Approved reservations for the same equipment on the same date.
- Adjacent time slots are allowed.
- Only Pending requests can be approved or rejected.
- An approval that would exceed available stock is blocked; the request remains Pending.
- The backend repeats validation even if browser-side validation is bypassed.

### 5. Ten potential viva questions

**1. What is Flask?**  
Flask is a Python web framework. It receives browser requests, runs application logic and returns HTML or JSON.

**2. What is SQLite?**  
SQLite is a relational database stored in a local file. It does not need a separate database server.

**3. How does the frontend communicate with Flask?**  
The browser sends HTTP requests to Flask routes. JavaScript uses `fetch()` to request live availability from `/api/availability`.

**4. Where are reservations stored?**  
In the `reservations` table inside `instance/laboratory.sqlite3`.

**5. How is the database initialized?**  
When the Flask app is created, it executes `schema.sql` and inserts sample equipment if those records do not already exist.

**6. What do Pending, Approved and Rejected mean?**  
Pending waits for a decision. Approved is accepted and consumes stock for its time slot. Rejected is declined and does not consume stock.

**7. How does the system prevent overbooking?**  
It checks the peak quantity already approved during the requested time interval and blocks a reservation or approval that exceeds stock.

**8. Why validate on the backend if JavaScript validates too?**  
Browser checks can be bypassed. Server-side validation protects the database and is authoritative.

**9. Why are database transactions used?**  
Transactions keep related database operations consistent. `BEGIN IMMEDIATE` helps serialize competing writes and reduces overbooking risk.

**10. How do you install, run and test the system?**  
Run `python -m pip install -r requirements.txt`, then `python app.py`. Run tests with `python -m unittest discover -s tests -v`.

### 6. Verification reminder

The repository's existing QA report marks the tests **NOT RUN** in its original environment. The commands in this guide are instructions, not evidence of a successful test run. Execute the tests on the demonstration computer and retain the actual terminal output. Do not claim deployment or test success until it has been observed.

### 7. Local demonstration limitation

The Flask built-in server is for local coursework demonstrations, not production hosting. The project has no authentication/authorization layer; anyone who can access the local app can use its management actions. Do not expose it publicly as-is.
