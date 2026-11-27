# MediAgents – Multi-Agent Health Care Monitoring System

## Project Overview

MediAgents is a web-based Multi-Agent Healthcare Monitoring System designed to simplify patient healthcare management through intelligent agents and automated workflows.

The system provides separate portals for patients and doctors, allowing patients to manage health records, monitor vital signs, check symptoms, book appointments, receive medicine reminders and access emergency support.

It uses a multi-agent architecture in which specialized agents communicate through a publish/subscribe messaging system to perform healthcare-related tasks efficiently.

## Key Features

### Patient Module
- Patient registration and secure login.
- Personal health records management.
- Vital signs tracking, including blood pressure, heart rate, glucose, temperature, weight and SpO2.
- NLP-based symptom checking.
- AI-assisted disease prediction and severity estimation.
- Doctor recommendations based on predicted conditions.
- Online doctor appointment booking.
- Medicine reminders and medication tracking.
- Emergency alerts and SOS functionality.
- Health analytics and medication adherence reports.

### Doctor Module
- Doctor registration and login.
- Doctor dashboard and appointment management.
- Patient information and medical history access.
- Patient vital signs monitoring.
- Add diagnosis notes and medical records.
- Prescribe medicines to patients.
- Automatic medicine reminder creation after prescriptions.
- Patient emergency alerts.
- Doctor availability and leave management.
- Appointment confirmation, cancellation and completion.

## Multi-Agent Architecture

The system consists of specialized agents that communicate using a central MessageBus with a publish/subscribe mechanism.

| Agent | Responsibility |
|---|---|
| Symptom Agent | Analyzes patient symptoms using NLP and predicts possible diseases. |
| Doctor Agent | Recommends doctors based on medical specialties. |
| Appointment Agent | Manages doctor availability and appointment bookings. |
| Reminder Agent | Creates and tracks medicine reminders. |
| Emergency Agent | Detects critical health conditions and generates alerts. |
| Records Agent | Manages patient medical records and vital signs. |
| Analytics Agent | Generates health summaries and medication adherence analytics. |
| Consultation Agent | Handles doctor notes and prescriptions. |

### Example Agent Workflow

1. A patient enters their symptoms.
2. The Symptom Agent analyzes the input.
3. A possible condition and relevant medical specialty are identified.
4. The Doctor Agent recommends suitable doctors.
5. The patient can book an appointment.
6. The doctor can add consultation notes and prescribe medication.
7. The Reminder Agent automatically creates medicine reminders.
8. The Emergency Agent monitors critical health indicators and generates alerts.

## Technologies Used

**Frontend**
- HTML5
- CSS3
- JavaScript
- Bootstrap / Custom CSS
- Chart.js

**Backend**
- Python
- Flask

**Database**
- SQLite

**Machine Learning and NLP**
- Scikit-learn
- NumPy
- Pandas
- Natural Language Processing

**Development Tools**
- Visual Studio Code
- Git
- GitHub

## Project Structure

```text
Multi-Agent-Health-Care-Monitoring-System/
│
└── healthcare_monitor/
    ├── agents/
    │   ├── __init__.py
    │   └── core.py
    │
    ├── data/
    │   ├── disease_knowledge.csv
    │   ├── symptom_corpus.csv
    │   └── doctors.csv
    │
    ├── models/
    ├── nlp/
    ├── outbox/
    ├── uploads/
    │
    ├── static/
    │   ├── css/
    │   ├── js/
    │   ├── style.css
    │   └── chart.umd.js
    │
    ├── templates/
    │
    ├── app.py
    ├── config.py
    ├── db.py
    ├── build_dataset.py
    ├── requirements.txt
    └── README.md
```

## Installation and Execution

### Step 1: Clone the Repository

```bash
git clone https://github.com/JadalaVarshini/Multi-Agent-Health-Care-Monitoring-System.git
```

### Step 2: Navigate to the Project Directory

```bash
cd Multi-Agent-Health-Care-Monitoring-System/healthcare_monitor
```

### Step 3: Create a Virtual Environment

```bash
python -m venv venv
```

### Step 4: Activate the Virtual Environment

**Windows:**

```bash
venv\Scripts\activate
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6: Run the Application

```bash
python app.py
```



## Demo Login Credentials

The following demo accounts are provided by the application:

| User Role | Email | Password |
|---|---|---|
| Patient | demo@health.com | demo123 |
| Patient (critical glucose demo) | patient2@health.com | patient123 |
| Doctor | doctor@health.com | doctor123 |

These are development/demo credentials. Change or disable them before public deployment.

## Dataset Information

The system includes three CSV datasets:

- **disease_knowledge.csv:** Contains disease names, associated symptoms, medical specialties, severity levels and precautions.
- **symptom_corpus.csv:** Contains synthetic patient-style symptom descriptions labelled with diseases for NLP model training.
- **doctors.csv:** Contains sample doctor profiles, specialties, experience, ratings and availability.

The included symptom dataset is synthetic and is intended for demonstration and development.

## Future Enhancements

- Integration with real hospital management systems.
- Integration with verified medical datasets.
- Improved NLP models for symptom understanding.
- Real-time SMS and email notifications.
- Cloud-based deployment and database integration.
- Integration with wearable health monitoring devices.
- Telemedicine and online consultation support.

## Important Disclaimer

This project is developed for educational and demonstration purposes. Symptom predictions and health alerts are not medical diagnoses. The system is not a certified medical device. Patients should consult qualified healthcare professionals for medical decisions.

Emergency notifications in the current implementation are simulated and logged rather than delivered through an actual SMS service.


GitHub: https://github.com/JadalaVarshini

## License

This project is intended for academic and educational purposes.
