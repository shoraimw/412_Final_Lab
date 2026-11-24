# University Laboratory Equipment Reservation System

East West University — Software Engineering Lab, Part A.

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
