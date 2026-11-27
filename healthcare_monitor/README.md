# MediAgents - Multi-Agent Healthcare Monitoring System

Two separate logins: **Patient** (`/login`) and **Doctor** (`/doctor/login`). Each role only sees its own area.

## Run
```
pip install -r requirements.txt
python build_dataset.py      # regenerates data/*.csv (optional, CSVs are included)
python app.py                # http://localhost:5000   (PORT=5055 python app.py to change port)
```
To open it from a phone/other PC on your network, use `http://<your-pc-ip>:5000`.

## Demo accounts (created on first run)
| Role | Email | Password |
|---|---|---|
| Patient | demo@health.com | demo123 |
| Patient (critical glucose alert) | patient2@health.com | patient123 |
| Doctor (Dr. Anjali Sharma) | doctor@health.com | doctor123 |

## Patient features
Health records, appointment booking (auto-jumps to the doctor's next working day), medicine reminders, NLP symptom checker, doctor recommendations, emergency alerts / SOS, health analytics. Appointment status, doctor's notes, doctor-written records and doctor-prescribed medicines all show up in the patient's account.

## Doctor features
- **Dashboard** - today's schedule, requests to confirm, open patient alerts, 7-day load chart
- **Appointments** - confirm / decline, mark completed with consultation notes, no-show, cancel with reason (patient sees it)
- **My patients** - only patients who have an appointment with you; full detail page: vitals charts, insights, allergies, history, medicines, symptom checks
- **Notes & prescriptions** - add notes to a patient's record; prescribe medicine -> the patient automatically gets daily reminders. Allergy check blocks conflicts (e.g. penicillin-class drugs) unless the doctor explicitly overrides
- **Patient alerts** - critical vitals / red-flag symptoms / SOS from your patients; mark resolved
- **Schedule & leave** - working days, block dates (patients can't book them)
- **Profile**; doctors can self-register at `/doctor/register`

## Agents (agents/core.py)
Symptom (NLP), Doctor, Appointment, Reminder, Emergency, Records, Analytics, Consultation - talking through a publish/subscribe MessageBus.
Example flow: doctor prescribes -> `prescription.issued` -> ReminderAgent creates reminders. Critical vitals -> EmergencyAgent -> alert + routed to treating doctors.

## Data (data/)
`disease_knowledge.csv`, `symptom_corpus.csv` (synthetic patient-style sentences), `doctors.csv`. Synthetic, not real patient data. To use a real dataset keep the same columns.

## Upgrading an existing database
Keep your old `healthcare.db` - new columns/tables are added automatically on start. Doctor demo data is added if missing.

## Notes
Emergency SMS / doctor notifications are simulated (logged only). Doctor registration number is stored but not verified. Not a medical device. Set `SECRET_KEY` and put the app behind HTTPS before any real deployment. `static/chart.umd.js` is Chart.js 4.4.1 (MIT) bundled so charts work offline.
