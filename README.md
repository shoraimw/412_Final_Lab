# University Laboratory Equipment Reservation System

East West University — Software Engineering Lab, Parts A and B.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. SQLite initializes automatically with sample equipment. The dashboard counts distinct inventory records and reservation statuses. Approved bookings consume inventory only during their time slot; overlapping approvals cannot exceed stock. Rejected and pending requests do not consume stock. This is a local lab demonstration with no authentication; do not expose it publicly as-is.

Run tests: `python -m unittest discover -s tests -v`.

## Part B business rules

Submission and approval use `BEGIN IMMEDIATE` SQLite transactions. Availability equals total stock minus the peak simultaneous approved quantity during the selected half-open time interval. Pending and rejected requests do not consume stock. Pending and approved bookings block overlapping requests by the same student for the same equipment/date; adjacent slots are allowed. Only pending requests may transition to approved or rejected. The reservation form fetches live availability and overlap information from `/api/availability`; server-side checks remain authoritative. Total stock is never decremented.
