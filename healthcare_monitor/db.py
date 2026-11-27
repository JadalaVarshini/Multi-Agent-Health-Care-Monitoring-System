import sqlite3, os, csv
from flask import g
DB_PATH = os.path.join(os.path.dirname(__file__), "healthcare.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password_hash TEXT,
  age INTEGER, gender TEXT, height_cm REAL, phone TEXT, emergency_name TEXT, emergency_phone TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS vitals(id INTEGER PRIMARY KEY, user_id INTEGER, ts TEXT, systolic INTEGER, diastolic INTEGER,
  heart_rate INTEGER, glucose REAL, temperature REAL, weight REAL, spo2 INTEGER);
CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, category TEXT, title TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS doctors(id INTEGER PRIMARY KEY, name TEXT, specialty TEXT, experience INTEGER, rating REAL, days TEXT);
CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, user_id INTEGER, doctor_id INTEGER, date TEXT, time TEXT,
  reason TEXT, status TEXT DEFAULT 'booked');
CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, user_id INTEGER, medicine TEXT, dosage TEXT, time TEXT,
  start_date TEXT, end_date TEXT, notes TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS reminder_log(id INTEGER PRIMARY KEY, reminder_id INTEGER, user_id INTEGER, date TEXT, taken_at TEXT);
CREATE TABLE IF NOT EXISTS symptom_checks(id INTEGER PRIMARY KEY, user_id INTEGER, ts TEXT, text TEXT, symptoms TEXT,
  top_disease TEXT, confidence REAL, severity INTEGER, specialty TEXT);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, user_id INTEGER, ts TEXT, level TEXT, source TEXT, message TEXT, resolved INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS doctor_leave(id INTEGER PRIMARY KEY, doctor_id INTEGER, date TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS prescriptions(id INTEGER PRIMARY KEY, doctor_id INTEGER, user_id INTEGER, appt_id INTEGER, medicine TEXT,
  dosage TEXT, times TEXT, days INTEGER, notes TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS agent_log(id INTEGER PRIMARY KEY, ts TEXT DEFAULT CURRENT_TIMESTAMP, user_id INTEGER, agent TEXT, event TEXT, detail TEXT);
"""

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH); g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args); rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows

def x(sql, args=()):
    d = get_db(); cur = d.execute(sql, args); d.commit(); return cur.lastrowid

# (table, column, definition) - added to databases created by older versions
MIGRATIONS = [("users", "role", "TEXT DEFAULT 'patient'"), ("users", "doctor_id", "INTEGER"), ("doctors", "license", "TEXT"),
              ("appointments", "doctor_notes", "TEXT"), ("appointments", "updated", "TEXT"),
              ("records", "doctor_id", "INTEGER"), ("reminders", "doctor_id", "INTEGER")]

def init_db():
    c = sqlite3.connect(DB_PATH); c.executescript(SCHEMA)
    for tbl, col, ddl in MIGRATIONS:
        if col not in [r[1] for r in c.execute(f"PRAGMA table_info({tbl})")]:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ddl}")
    c.execute("UPDATE users SET role='patient' WHERE role IS NULL")
    if c.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
        with open(os.path.join(os.path.dirname(__file__), "data", "doctors.csv")) as f:
            for r in csv.DictReader(f):
                c.execute("INSERT INTO doctors(name,specialty,experience,rating,days) VALUES(?,?,?,?,?)",
                          (r["name"], r["specialty"], int(r["experience"]), float(r["rating"]), r["days"]))
    c.commit(); c.close()
