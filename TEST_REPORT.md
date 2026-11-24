# Part C — QA Test Report

Repository: shoraimw/412_Final_Lab. Test suite: `test_reservations.py`.

Each test uses an isolated temporary SQLite database, with EQ-001 stock set to 5. The application date is fixed to 2026-11-24 for repeatable examination scenarios. No demonstration database is modified.

**Execution status:** NOT RUN in this environment. GitHub source and the live Supabase RPC were updated, but this session did not run the Python test suite against a local checkout. No PASS result is claimed. Run the commands below to obtain actual results.

Unless otherwise specified, inputs use student 2026-1-60-001, EQ-001 (Digital Oscilloscope), 2026-11-25, 10:00–11:00, quantity 2, stock 5.

| ID | Scenario | Test input | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| TC01 | Valid request | Default input | HTTP 200 after redirect; one Pending row with exact values; pending count 0→1 | Not executed | NOT RUN |
| TC02 | Excess quantity | Qty 10 | HTTP 400, quantity error, database unchanged | Not executed | NOT RUN |
| TC03 | Reversed times | 12:00–10:00 | HTTP 400, time error, database unchanged | Not executed | NOT RUN |
| TC04 | Overlap | Existing default; same student 10:30–11:30 | HTTP 400, overlap error, original row only | Not executed | NOT RUN |
| TC05 | Approve/reject | Two students; approve first, reject second | Approved and Rejected persisted; dashboard 0/1/1 | Not executed | NOT RUN |
| TC06 | Dynamic stock | Approve qty 2; second student requests 4 | Stock 5→3; qty 4 rejected | Not executed | NOT RUN |
| TC07 | Approval overbooking | Pending qty 4 and 3; approve both sequentially | First Approved, second Pending, available 1 | Not executed | NOT RUN |
| TC08 | Equal times | 10:00–10:00 | HTTP 400; no insertion | Not executed | NOT RUN |
| TC09 | Invalid quantity | 0, -1, 1.5 | Each rejected; no insertion | Not executed | NOT RUN |
| TC10 | Missing fields | Each required field empty individually | HTTP 400 and relevant error; no insertion | Not executed | NOT RUN |
| TC11 | Adjacent slots | 10:00–11:00 and 11:00–12:00 | Two Pending rows | Not executed | NOT RUN |
| TC12 | Different equipment, same student and time | Existing EQ-001 10:00–11:00; request EQ-002 10:00–11:00 | HTTP 400, cross-equipment overlap error, no second row | Not executed in this environment; regression test added | NOT RUN |
| TC13 | Different date | Nov 25 and Nov 26 | Two Pending rows | Not executed | NOT RUN |
| TC14 | Dashboard | Three requests, approve one, reject one | Pending 1, Approved 1, Rejected 1 | Not executed | NOT RUN |
| TC15 | Restart persistence | Approve a request, recreate Flask application using same DB | Identical records after restart | Not executed | NOT RUN |
| TC16 | Rejected overlap | Reject default then resubmit | Rejected and Pending rows | Not executed | NOT RUN |
| TC17 | Exact duplicates | Repeat default while Pending and Approved | Both rejected; database unchanged | Not executed | NOT RUN |
| TC18 | Peak availability | Approve qty 3 at 10:00–10:30 and qty 3 at 10:30–11:00 | Available 2 across full hour; qty 2 accepted | Not executed | NOT RUN |
| TC19 | Approval guard for legacy cross-equipment overlap | Insert two legacy Pending rows for same student/date with overlapping times on EQ-001 and EQ-002; approve second | Approval rejected; second row remains Pending | Not executed in this environment; regression test added | NOT RUN |

## Identified bugs and applied solutions

Confirmed bug: the student overlap query incorrectly included `equipment_id`, allowing one student to reserve different equipment for overlapping times. The same condition existed in the live Supabase RPC. Fixed the Flask validation and approval guard, changed the live RPC, and updated the PostgreSQL index to support student/date overlap checks. The suite sets EQ-001 stock to 5 in its isolated temporary database. Automated tests have not been executed in this environment, so no PASS result is claimed.

## Execute

```bash
python -m pip install -r requirements.txt
python -m unittest -v test_reservations
```

## Manual demonstration

Use a clean demonstration database on 2026-11-24 (or choose a future date consistently if demonstrating later). Open the dashboard and note Pending count. For the exact stock-5 demonstration, use a separate database:

```bash
python -c "from app import create_app; import sqlite3; a=create_app({'DATABASE':'demo_qa.sqlite3'}); c=sqlite3.connect('demo_qa.sqlite3'); c.execute('UPDATE equipment SET quantity=5 WHERE id=?',('EQ-001',)); c.commit(); c.close(); a.run()"
```

1. Submit default input. Show Pending status and dashboard increment.
2. Use another student ID (2026-1-60-002) and quantity 10. Show quantity rejection; reservation count unchanged.
3. Enter 12:00–10:00, quantity 2. Show time rejection and unchanged count.
4. Use original student and equipment/date, 10:30–11:30, quantity 2. Show overlap rejection and unchanged count.

Browser validation may block some invalid forms before submission; the automated suite posts directly to verify the backend independently.
