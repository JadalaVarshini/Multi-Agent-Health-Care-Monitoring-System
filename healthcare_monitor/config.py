"""Central configuration for the Multi-Agent Healthcare Monitoring System."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "models")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTBOX_DIR = os.path.join(BASE_DIR, "outbox")
DB_PATH = os.path.join(BASE_DIR, "healthcare.db")

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
ALLOWED_UPLOADS = {"pdf", "png", "jpg", "jpeg", "txt", "doc", "docx"}
MAX_UPLOAD_MB = 8

# India defaults - change these for another country
EMERGENCY_NUMBERS = [
    ("National Emergency", "112"),
    ("Ambulance", "108"),
    ("Mental-health helpline (Tele-MANAS)", "14416"),
]

for _d in (DATA_DIR, MODEL_DIR, UPLOAD_DIR, OUTBOX_DIR):
    os.makedirs(_d, exist_ok=True)
