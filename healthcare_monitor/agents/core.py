"""Multi-agent system. Each agent owns one responsibility and talks to the others
only through the MessageBus (publish/subscribe). The Coordinator wires them together.
"""
import csv, os, re, datetime as dt
from collections import defaultdict, Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from db import q, x

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# ---------------------------------------------------------------- message bus
class MessageBus:
    def __init__(self): self.subs = defaultdict(list)
    def subscribe(self, topic, fn): self.subs[topic].append(fn)
    def publish(self, topic, payload):
        x("INSERT INTO agent_log(user_id,agent,event,detail) VALUES(?,?,?,?)",
          (payload.get("user_id"), payload.get("_from", "system"), topic, str(payload.get("_note", ""))[:200]))
        for fn in self.subs[topic]: fn(payload)

class Agent:
    name = "Agent"
    def __init__(self, bus): self.bus = bus
    def say(self, topic, **p): p["_from"] = self.name; self.bus.publish(topic, p)

def now(): return dt.datetime.now().strftime("%Y-%m-%d %H:%M")

# ------------------------------------------------------------- NLP symptom agent
SYNONYMS = {  # colloquial phrase -> canonical symptom
 "throwing up":"vomiting","puking":"vomiting","threw up":"vomiting","loose motions":"diarrhea","loose stools":"diarrhea",
 "tired":"fatigue","tiredness":"fatigue","exhausted":"fatigue","weak":"weakness","breathless":"shortness of breath",
 "breathlessness":"shortness of breath","can't breathe":"difficulty breathing","cannot breathe":"difficulty breathing",
 "head pain":"headache","head hurts":"headache","tummy ache":"stomach pain","stomach ache":"stomach pain","belly pain":"stomach pain",
 "temperature":"fever","feverish":"fever","runny nose":"runny nose","stuffy nose":"nasal congestion","blocked nose":"nasal congestion",
 "dizzy":"dizziness","giddy":"dizziness","itching":"itchy skin","no interest":"loss of interest","lost interest":"loss of interest","peeing a lot":"frequent urination",
 "pee often":"frequent urination","burning when i pee":"burning urination","thirsty":"increased thirst","joint ache":"joint pain",
 "chest tightness":"chest tightness","heart racing":"palpitations","racing heart":"palpitations","can't sleep":"trouble sleeping",
 "insomnia":"trouble sleeping","sad":"persistent sadness","worried":"excessive worry","vomit":"vomiting","puke":"vomiting",
}
RED_FLAGS = ["severe chest pain","chest pain","can't breathe","cannot breathe","difficulty breathing","unconscious","fainted",
 "severe bleeding","suicidal","want to die","slurred speech","face drooping","seizure","throat tightening","coughing blood",
 "swelling of face","poison","overdose","paralysis","sudden vision loss","pain in left arm"]
NEG = re.compile(r"\b(no|not|without|never|don't have|do not have|denies|free of)\b(?:\W+\w+){0,2}?\W+$")

class SymptomAgent(Agent):
    name = "SymptomAgent (NLP)"
    def __init__(self, bus):
        super().__init__(bus)
        self.kb = {}
        with open(os.path.join(DATA, "disease_knowledge.csv")) as f:
            for r in csv.DictReader(f):
                self.kb[r["disease"]] = dict(specialty=r["specialty"], severity=int(r["severity"]),
                    symptoms=r["symptoms"].split(";"), precautions=r["precautions"].split(";"))
        self.vocab = sorted({s for k in self.kb.values() for s in k["symptoms"]}, key=len, reverse=True)
        texts, labels = [], []
        with open(os.path.join(DATA, "symptom_corpus.csv")) as f:
            for r in csv.DictReader(f): texts.append(r["text"]); labels.append(r["disease"])
        Xtr, Xte, ytr, yte = train_test_split(texts, labels, test_size=0.2, random_state=1, stratify=labels)
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True)
        self.clf = LogisticRegression(max_iter=2000, C=8)
        self.clf.fit(self.vec.fit_transform(Xtr), ytr)
        self.accuracy = round(accuracy_score(yte, self.clf.predict(self.vec.transform(Xte))), 3)
        self.n_train = len(Xtr)

    def extract(self, text):
        t = " " + re.sub(r"[^\w\s']", " ", text.lower()) + " "
        found, negated = [], []
        cands = [(p, c) for p, c in SYNONYMS.items()] + [(s, s) for s in self.vocab]
        for phrase, canon in sorted(cands, key=lambda z: -len(z[0])):
            for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", t):
                before = t[:m.start()]
                (negated if NEG.search(before[-30:]) else found).append(canon); break
        return sorted(set(found) - set(negated)), sorted(set(negated))

    def analyze(self, text, user_id=None):
        symptoms, negated = self.extract(text)
        proba = self.clf.predict_proba(self.vec.transform([text.lower()]))[0]
        scores = {}
        for dis, p in zip(self.clf.classes_, proba):
            kb = self.kb[dis]["symptoms"]
            overlap = len(set(symptoms) & set(kb)) / max(1, len(set(symptoms) | set(kb)) ) if symptoms else 0
            penalty = 0.5 if set(negated) & set(kb) and not set(symptoms) & set(kb) else 1
            scores[dis] = (0.65 * p + 0.35 * min(1, overlap * 2.2)) * penalty
        tot = sum(scores.values()) or 1
        top = sorted(((str(d), float(s) / tot) for d, s in scores.items()), key=lambda z: -z[1])[:3]
        lower = text.lower()
        flags = [f for f in RED_FLAGS if f in lower and not NEG.search(lower[:lower.find(f)][-25:])]
        top_d, top_c = top[0]
        sev = self.kb[top_d]["severity"]
        emergency = bool(flags) or (sev >= 5 and top_c > 0.30)
        res = dict(symptoms=symptoms, negated=negated, red_flags=flags, emergency=emergency, results=[
            dict(disease=str(d), confidence=round(float(c) * 100, 1), severity=self.kb[d]["severity"], specialty=self.kb[d]["specialty"],
                 precautions=self.kb[d]["precautions"], matched=sorted(set(symptoms) & set(self.kb[d]["symptoms"]))) for d, c in top])
        res["specialty"] = res["results"][0]["specialty"] if not flags else ("Emergency Medicine" if not res["results"][0]["severity"] >= 5 else res["results"][0]["specialty"])
        if user_id:
            x("INSERT INTO symptom_checks(user_id,ts,text,symptoms,top_disease,confidence,severity,specialty) VALUES(?,?,?,?,?,?,?,?)",
              (user_id, now(), text, ", ".join(symptoms), top_d, round(top_c * 100, 1), sev, res["specialty"]))
            self.say("symptom.analyzed", user_id=user_id, result=res, _note=f"{top_d} {top_c:.0%}; emergency={emergency}")
        return res

# ------------------------------------------------------------------- doctor agent
class DoctorAgent(Agent):
    name = "DoctorAgent"
    def __init__(self, bus):
        super().__init__(bus); self.last = {}
        bus.subscribe("symptom.analyzed", lambda p: self.last.__setitem__(p["user_id"], p["result"]["specialty"]))
    def recommend(self, specialty, limit=5):
        docs = [dict(r) for r in q("SELECT * FROM doctors WHERE specialty=?", (specialty,))]
        for d in docs: d["score"] = round(d["rating"] * 0.7 + min(d["experience"], 25) / 25 * 5 * 0.3, 2)
        docs.sort(key=lambda d: -d["score"])
        if not docs:  # fall back to GP
            docs = [dict(r) | {"score": r["rating"]} for r in q("SELECT * FROM doctors WHERE specialty='General Physician'")]
        return docs[:limit]
    def all_specialties(self): return [r[0] for r in q("SELECT DISTINCT specialty FROM doctors ORDER BY 1")]

# ------------------------------------------------------------- appointment agent
class AppointmentAgent(Agent):
    name = "AppointmentAgent"
    SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) if h != 13 for m in (0, 30)]
    def slots(self, doctor_id, date):
        doc = q("SELECT * FROM doctors WHERE id=?", (doctor_id,), one=True)
        try: day = dt.date.fromisoformat(date).strftime("%a")
        except ValueError: return []
        if not doc or day not in doc["days"].split(","): return []
        if q("SELECT 1 FROM doctor_leave WHERE doctor_id=? AND date=?", (doctor_id, date), one=True): return []
        taken = {r["time"] for r in q("SELECT time FROM appointments WHERE doctor_id=? AND date=? AND status IN ('booked','confirmed')", (doctor_id, date))}
        free = [s for s in self.SLOTS if s not in taken]
        if date == dt.date.today().isoformat():
            free = [s for s in free if s > dt.datetime.now().strftime("%H:%M")]
        return free
    def book(self, user_id, doctor_id, date, time, reason):
        try:
            if dt.date.fromisoformat(date) < dt.date.today(): return False, "Date is in the past."
        except ValueError: return False, "Invalid date."
        if time not in self.slots(doctor_id, date): return False, "That slot is not available. Pick another."
        x("INSERT INTO appointments(user_id,doctor_id,date,time,reason) VALUES(?,?,?,?,?)", (user_id, doctor_id, date, time, reason))
        self.say("appointment.booked", user_id=user_id, _note=f"doctor {doctor_id} {date} {time}")
        return True, "Appointment booked."
    def cancel(self, user_id, appt_id):
        x("UPDATE appointments SET status='cancelled', updated=? WHERE id=? AND user_id=? AND status IN ('booked','confirmed')", (now(), appt_id, user_id))
        self.say("appointment.cancelled", user_id=user_id, _note=str(appt_id))
    TRANS = {"confirm": ("confirmed", {"booked"}), "complete": ("completed", {"booked", "confirmed"}),
             "cancel": ("cancelled", {"booked", "confirmed"}), "noshow": ("no_show", {"confirmed"})}
    def set_status(self, doctor_id, appt_id, action, note=""):
        """Doctor-side workflow: booked -> confirmed -> completed / no_show, or cancelled."""
        if action not in self.TRANS: return False, "Unknown action."
        new, allowed = self.TRANS[action]
        a = q("SELECT * FROM appointments WHERE id=? AND doctor_id=?", (appt_id, doctor_id), one=True)
        if not a: return False, "Appointment not found."
        if a["status"] not in allowed: return False, f"Cannot {action} an appointment that is {a['status'].replace('_', ' ')}."
        if action in ("complete", "noshow") and a["date"] > dt.date.today().isoformat(): return False, "That appointment is still in the future."
        note = note.strip()
        if action == "cancel" and note: note = "Cancelled by doctor: " + note
        x("UPDATE appointments SET status=?, doctor_notes=?, updated=? WHERE id=?", (new, note or a["doctor_notes"], now(), appt_id))
        self.say(f"appointment.{new}", user_id=a["user_id"], doctor_id=doctor_id, _note=f"appointment {appt_id}")
        return True, f"Appointment marked {new.replace('_', ' ')}."
    def upcoming(self, user_id):
        return q("""SELECT a.*, d.name doctor, d.specialty FROM appointments a JOIN doctors d ON d.id=a.doctor_id
                    WHERE a.user_id=? ORDER BY a.date DESC, a.time DESC""", (user_id,))

# ---------------------------------------------------------------- reminder agent
class ReminderAgent(Agent):
    name = "ReminderAgent"
    def __init__(self, bus):
        super().__init__(bus); bus.subscribe("prescription.issued", self.on_prescription)
    def on_prescription(self, p):  # doctor prescribes -> patient automatically gets a daily reminder
        start = dt.date.today(); end = start + dt.timedelta(days=p["days"] - 1)
        x("INSERT INTO reminders(user_id,medicine,dosage,time,start_date,end_date,notes,doctor_id) VALUES(?,?,?,?,?,?,?,?)",
          (p["user_id"], p["medicine"], p["dosage"], p["time"], start.isoformat(), end.isoformat(), p["notes"], p["doctor_id"]))
    def status_today(self, user_id, today, hhmm):
        out = []
        for r in q("SELECT * FROM reminders WHERE user_id=? AND active=1 AND start_date<=? AND (end_date='' OR end_date>=?) ORDER BY time",
                   (user_id, today, today)):
            taken = q("SELECT taken_at FROM reminder_log WHERE reminder_id=? AND date=?", (r["id"], today), one=True)
            if taken: st = "taken"
            elif r["time"] > hhmm: st = "upcoming"
            else:
                mins = (dt.datetime.strptime(hhmm, "%H:%M") - dt.datetime.strptime(r["time"], "%H:%M")).seconds // 60
                st = "due" if mins <= 60 else "missed"
            out.append(dict(r) | {"status": st})
        return out
    def take(self, user_id, rid, today):
        if q("SELECT 1 FROM reminders WHERE id=? AND user_id=?", (rid, user_id), one=True) and \
           not q("SELECT 1 FROM reminder_log WHERE reminder_id=? AND date=?", (rid, today), one=True):
            x("INSERT INTO reminder_log(reminder_id,user_id,date,taken_at) VALUES(?,?,?,?)", (rid, user_id, today, now()))
            self.say("medicine.taken", user_id=user_id, _note=str(rid))
    def adherence(self, user_id, days=14):
        end = dt.date.today(); series = []
        for i in range(days - 1, -1, -1):
            d = (end - dt.timedelta(days=i)).isoformat()
            exp = q("SELECT COUNT(*) c FROM reminders WHERE user_id=? AND active=1 AND start_date<=? AND (end_date='' OR end_date>=?)", (user_id, d, d), one=True)["c"]
            got = q("SELECT COUNT(*) c FROM reminder_log WHERE user_id=? AND date=?", (user_id, d), one=True)["c"]
            series.append(dict(date=d, expected=exp, taken=min(got, exp), pct=round(100 * min(got, exp) / exp) if exp else None))
        return series

# ---------------------------------------------------------------- emergency agent
CRITICAL = [("systolic", lambda v: v >= 180, "Systolic BP {v} mmHg is dangerously high"), ("systolic", lambda v: v < 90, "Systolic BP {v} mmHg is dangerously low"),
 ("diastolic", lambda v: v >= 120, "Diastolic BP {v} mmHg is dangerously high"),
 ("heart_rate", lambda v: v > 130, "Heart rate {v} bpm is very high"), ("heart_rate", lambda v: v < 40, "Heart rate {v} bpm is very low"),
 ("glucose", lambda v: v > 300, "Blood glucose {v} mg/dL is critically high"), ("glucose", lambda v: v < 60, "Blood glucose {v} mg/dL is critically low"),
 ("temperature", lambda v: v >= 39.5, "Temperature {v} °C is a high fever"), ("temperature", lambda v: v < 35, "Temperature {v} °C indicates hypothermia"),
 ("spo2", lambda v: v < 90, "Oxygen saturation {v}% is critically low")]

class EmergencyAgent(Agent):
    name = "EmergencyAgent"
    def __init__(self, bus):
        super().__init__(bus)
        bus.subscribe("symptom.analyzed", self.on_symptoms)
        bus.subscribe("vitals.recorded", self.on_vitals)
    def raise_alert(self, user_id, level, source, msg):
        aid = x("INSERT INTO alerts(user_id,ts,level,source,message) VALUES(?,?,?,?,?)", (user_id, now(), level, source, msg))
        u = q("SELECT emergency_name,emergency_phone FROM users WHERE id=?", (user_id,), one=True)
        if level == "critical" and u and u["emergency_phone"]:  # simulated notification
            x("INSERT INTO agent_log(user_id,agent,event,detail) VALUES(?,?,?,?)",
              (user_id, self.name, "notify.contact", f"[SIMULATED SMS] to {u['emergency_name']} {u['emergency_phone']}: {msg}"))
        if level == "critical":  # route to every doctor currently treating this patient (simulated notification)
            for d in q("""SELECT DISTINCT d.name FROM appointments a JOIN doctors d ON d.id=a.doctor_id
                          WHERE a.user_id=? AND a.status IN ('booked','confirmed','completed')""", (user_id,)):
                x("INSERT INTO agent_log(user_id,agent,event,detail) VALUES(?,?,?,?)", (user_id, self.name, "notify.doctor", f"[SIMULATED] alert routed to {d['name']}: {msg}"))
        return aid
    def on_symptoms(self, p):
        r = p["result"]
        if r["emergency"]:
            why = ("red-flag: " + ", ".join(r["red_flags"])) if r["red_flags"] else f"possible {r['results'][0]['disease']}"
            self.raise_alert(p["user_id"], "critical", "Symptom checker", f"Emergency warning from symptom analysis ({why}).")
    def on_vitals(self, p):
        v = p["vitals"]
        for field, test, msg in CRITICAL:
            if v.get(field) is not None and test(v[field]):
                self.raise_alert(p["user_id"], "critical", "Vitals monitor", msg.format(v=v[field]))
    def sos(self, user_id, note=""):
        return self.raise_alert(user_id, "critical", "SOS button", "SOS triggered by user. " + note)

# ----------------------------------------------------------------- records agent
class RecordsAgent(Agent):
    name = "RecordsAgent"
    FIELDS = ["systolic", "diastolic", "heart_rate", "glucose", "temperature", "weight", "spo2"]
    def add_vitals(self, user_id, form):
        v = {}
        for f in self.FIELDS:
            try: v[f] = float(form.get(f)) if form.get(f) not in (None, "") else None
            except ValueError: v[f] = None
        for f in ("systolic", "diastolic", "heart_rate", "spo2"):
            if v[f] is not None: v[f] = int(v[f])
        if all(val is None for val in v.values()): return False
        ts = (form.get("ts") or now()).replace("T", " ")[:16]
        x("INSERT INTO vitals(user_id,ts,systolic,diastolic,heart_rate,glucose,temperature,weight,spo2) VALUES(?,?,?,?,?,?,?,?,?)",
          (user_id, ts, *[v[f] for f in self.FIELDS]))
        self.say("vitals.recorded", user_id=user_id, vitals=v, _note=str({k: val for k, val in v.items() if val is not None}))
        return True

# --------------------------------------------------------------- analytics agent
def _trend(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 3: return "not enough data"
    s = np.polyfit(range(len(vals)), vals, 1)[0]; rng = (max(vals) - min(vals)) or 1
    return "stable" if abs(s) * len(vals) < 0.15 * rng else ("rising" if s > 0 else "falling")

class AnalyticsAgent(Agent):
    name = "AnalyticsAgent"
    def summary(self, user_id, adherence):
        vit = [dict(r) for r in q("SELECT * FROM vitals WHERE user_id=? ORDER BY ts", (user_id,))]
        u = q("SELECT * FROM users WHERE id=?", (user_id,), one=True)
        out = dict(vitals=vit, labels=[v["ts"][5:16] for v in vit], insights=[], stats={})
        for f in RecordsAgent.FIELDS:
            vals = [v[f] for v in vit if v[f] is not None]
            if vals: out["stats"][f] = dict(avg=round(float(np.mean(vals)), 1), min=min(vals), max=max(vals), latest=vals[-1], trend=_trend(vals))
        st = out["stats"]; ins = out["insights"]
        if "systolic" in st:
            s, d = st["systolic"]["avg"], st.get("diastolic", {}).get("avg", 0)
            cat = "Normal" if s < 120 and d < 80 else "Elevated" if s < 130 and d < 80 else "Stage 1 hypertension range" if s < 140 and d < 90 else "Stage 2 hypertension range"
            ins.append(f"Average blood pressure {s:.0f}/{d:.0f} mmHg - {cat}; trend {st['systolic']['trend']}.")
        if "glucose" in st:
            g = st["glucose"]["avg"]; ins.append(f"Average glucose {g} mg/dL - {'normal' if g < 100 else 'pre-diabetic range' if g < 126 else 'diabetic range (confirm with your doctor)'}; trend {st['glucose']['trend']}.")
        if "heart_rate" in st: ins.append(f"Resting heart rate averages {st['heart_rate']['avg']:.0f} bpm ({'normal' if 60 <= st['heart_rate']['avg'] <= 100 else 'outside the usual 60-100 range'}).")
        if "weight" in st and u["height_cm"]:
            bmi = st["weight"]["latest"] / ((u["height_cm"] / 100) ** 2); out["bmi"] = round(bmi, 1)
            ins.append(f"BMI {bmi:.1f} - {'underweight' if bmi < 18.5 else 'healthy' if bmi < 25 else 'overweight' if bmi < 30 else 'obese'}; weight trend {st['weight']['trend']}.")
        if "spo2" in st and st["spo2"]["min"] < 94: ins.append(f"Oxygen saturation dipped to {st['spo2']['min']}% at least once.")
        exp = sum(a["expected"] for a in adherence); got = sum(a["taken"] for a in adherence)
        out["adherence_pct"] = round(100 * got / exp) if exp else None
        if out["adherence_pct"] is not None: ins.append(f"Medicine adherence over 14 days: {out['adherence_pct']}%." + (" Try to take doses on time." if out["adherence_pct"] < 80 else " Great consistency."))
        sc = q("SELECT symptoms FROM symptom_checks WHERE user_id=?", (user_id,))
        cnt = Counter(s.strip() for r in sc for s in r["symptoms"].split(",") if s.strip())
        out["symptom_freq"] = cnt.most_common(8)
        out["alerts"] = q("SELECT COUNT(*) c FROM alerts WHERE user_id=?", (user_id,), one=True)["c"]
        score = 100  # simple heuristic, not a clinical score
        if out["adherence_pct"] is not None: score -= (100 - out["adherence_pct"]) * 0.3
        score -= min(30, out["alerts"] * 5)
        if "systolic" in st and st["systolic"]["avg"] >= 130: score -= 10
        if "glucose" in st and st["glucose"]["avg"] >= 126: score -= 10
        out["health_score"] = max(0, round(score))
        return out

# ---------------------------------------------------------- consultation agent
ALLERGY_CLASSES = {"penicillin": ["amoxicillin", "ampicillin", "amoxyclav", "augmentin", "cloxacillin", "penicillin"],
                   "sulfa": ["sulfamethoxazole", "cotrimoxazole", "septran", "sulfa"],
                   "aspirin": ["aspirin", "ecosprin"], "nsaid": ["ibuprofen", "diclofenac", "naproxen", "aspirin"]}

class ConsultationAgent(Agent):
    name = "ConsultationAgent"
    def patients(self, doctor_id):
        return q("""SELECT u.*, COUNT(a.id) visits, MAX(a.date) last_date,
                    (SELECT COUNT(*) FROM alerts al WHERE al.user_id=u.id AND al.resolved=0) open_alerts
                    FROM users u JOIN appointments a ON a.user_id=u.id WHERE a.doctor_id=? AND a.status!='cancelled'
                    GROUP BY u.id ORDER BY open_alerts DESC, last_date DESC""", (doctor_id,))
    def can_view(self, doctor_id, user_id):  # doctors may only see patients they have an (uncancelled) appointment with
        return q("SELECT 1 FROM appointments WHERE doctor_id=? AND user_id=? AND status!='cancelled'", (doctor_id, user_id), one=True) is not None
    def allergy_conflict(self, user_id, medicine):
        med = medicine.lower(); words = set(re.findall(r"[a-z]{4,}", med))
        for r in q("SELECT * FROM records WHERE user_id=? AND category='Allergy'", (user_id,)):
            text = ((r["title"] or "") + " " + (r["notes"] or "")).lower()
            if any(w in text for w in words): return r
            for key, members in ALLERGY_CLASSES.items():
                if key in text and any(m in med for m in members): return r
        return None
    def add_note(self, doctor_id, user_id, category, title, notes):
        if not title.strip(): return False
        x("INSERT INTO records(user_id,date,category,title,notes,doctor_id) VALUES(?,?,?,?,?,?)",
          (user_id, dt.date.today().isoformat(), category, title.strip(), notes.strip(), doctor_id))
        self.say("record.added", user_id=user_id, doctor_id=doctor_id, _note=title.strip()); return True
    def prescribe(self, doctor_id, user_id, medicine, dosage, times, days, notes, appt_id=None, override=False):
        medicine, dosage = medicine.strip(), dosage.strip()
        tl = [t.strip() for t in times.split(",") if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t.strip())]
        if not medicine or not dosage or not tl: return False, "Medicine, dosage and at least one valid time (HH:MM, comma separated) are required."
        if not 1 <= days <= 365: return False, "Duration must be between 1 and 365 days."
        c = self.allergy_conflict(user_id, medicine)
        if c and not override:
            return False, f"ALLERGY WARNING: patient has a recorded allergy ('{c['title']}') that may conflict with {medicine}. Tick 'override' to prescribe anyway."
        x("INSERT INTO prescriptions(doctor_id,user_id,appt_id,medicine,dosage,times,days,notes,created) VALUES(?,?,?,?,?,?,?,?,?)",
          (doctor_id, user_id, appt_id, medicine, dosage, ",".join(tl), days, notes.strip(), now()))
        x("INSERT INTO records(user_id,date,category,title,notes,doctor_id) VALUES(?,?,?,?,?,?)",
          (user_id, dt.date.today().isoformat(), "Prescription", f"{medicine} {dosage}", f"{', '.join(tl)} daily for {days} day(s). {notes.strip()}".strip(), doctor_id))
        for t in tl:
            self.say("prescription.issued", user_id=user_id, doctor_id=doctor_id, medicine=medicine, dosage=dosage, time=t, days=days, notes=notes.strip(), _note=f"{medicine} {dosage} at {t}")
        return True, f"Prescribed {medicine}. {len(tl)} daily reminder(s) created for the patient."

def doctor_overview(doctor_id):
    today = dt.date.today(); c = lambda sql, *a: q(sql, a, one=True)[0]
    od = "SELECT COUNT(*) FROM appointments WHERE doctor_id=? "
    ov = dict(today=c(od + "AND date=? AND status IN ('booked','confirmed')", doctor_id, today.isoformat()),
              pending=c(od + "AND status='booked' AND date>=?", doctor_id, today.isoformat()),
              completed=c(od + "AND status='completed'", doctor_id),
              patients=c("SELECT COUNT(DISTINCT user_id) FROM appointments WHERE doctor_id=? AND status!='cancelled'", doctor_id),
              alerts=c("SELECT COUNT(*) FROM alerts WHERE resolved=0 AND user_id IN (SELECT user_id FROM appointments WHERE doctor_id=? AND status!='cancelled')", doctor_id))
    days = [(today + dt.timedelta(days=i)) for i in range(7)]
    ov["load_labels"] = [d.strftime("%a %d") for d in days]
    ov["load"] = [c(od + "AND date=? AND status IN ('booked','confirmed')", doctor_id, d.isoformat()) for d in days]
    return ov

# ------------------------------------------------------------------ coordinator
class Coordinator:
    def __init__(self):
        self.bus = MessageBus()
        self.symptom = SymptomAgent(self.bus); self.doctor = DoctorAgent(self.bus)
        self.appointment = AppointmentAgent(self.bus); self.reminder = ReminderAgent(self.bus)
        self.emergency = EmergencyAgent(self.bus); self.records = RecordsAgent(self.bus)
        self.analytics = AnalyticsAgent(self.bus); self.consult = ConsultationAgent(self.bus)
    def agents(self): return [self.symptom, self.doctor, self.appointment, self.reminder, self.emergency, self.records, self.analytics, self.consult]
