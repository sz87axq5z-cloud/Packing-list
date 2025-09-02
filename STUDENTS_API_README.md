# Students API (FastAPI + SQLite)

This backend creates a student management ID from date of birth and phone number and saves records with upsert and history logging.

- Management ID: `YYYYMMDD` + `phoneDigits`
- On save: if same ID exists, update it and store the previous version in `student_history`.

## Requirements
- Python 3.10+

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the server
```bash
uvicorn app.main:app --reload
```
- API base: http://127.0.0.1:8000
- Docs (Swagger): http://127.0.0.1:8000/docs

## API
### Upsert/Create student
POST /students
```json
{
  "dob": "20010403",
  "phone": "09012345678",
  "name": "山田太郎"
}
```
Response
```json
{
  "id": "2001040309012345678",
  "dob": "20010403",
  "phone": "09012345678",
  "name": "山田太郎",
  "version": 1,
  "updated_at": "2025-01-01T00:00:00.000000"
}
```

- If the same `id` is posted again with new data, the record is updated and the old one is stored in `student_history` with incremented `version`.

### Get student by ID
GET /students/{student_id}

Example
```
GET /students/2001040309012345678
```

## Notes
- Database file: `students.db` in project root.
- Tables: `students`, `student_history`.
- Pydantic validation enforces `dob`=8 digits, `phone`=7-20 digits.
