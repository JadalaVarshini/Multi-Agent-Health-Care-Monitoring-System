import os, secrets, random, datetime as dt
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g, abort
from werkzeug.security import generate_password_hash, check_password_hash
import config
import db
from db import q, x
from agents.core import Coordinator, doctor_overview

app = Flask(__name__)
KEY = os.path.join(os.path.dirname(__file__), ".secret_key")
if not os.path.exists(KEY): open(KEY, "w").write(secrets.token_hex(32))
app.secret_key = open(KEY).read()
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True)
app.teardown_appcontext(db.close_db)
db.init_db()
AI = Coordinator()  # the multi-agent system

def _guard(role):
    """Route decorator: must be signed in with this role; the other role is bounced to its own area."""
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if "uid" not in session: return redirect(url_for("login" if role == "patient" else "doctor_login", next=request.path))
            u = q("SELECT * FROM users WHERE id=?", (session["uid"],), one=True)
            if not u: session.clear(); return redirect(url_for("login"))
            g.user = u
            if (u["role"] or "patient") != role:
                return redirect(url_for("doctor_dashboard" if u["role"] == "doctor" else "dashboard"))
            if role == "doctor":
                g.doc = q("SELECT * FROM doctors WHERE id=?", (u["doctor_id"],), one=True)
                if not g.doc: session.clear(); return redirect(url_for("doctor_login"))
            return f(*a, **k)
        return w
    return deco
login_required = _guard("patient"); doctor_required = _guard("doctor")

@app.template_filter("stars")
def stars(r): return f"★ {r:.1f}" if r else "New"

@app.context_processor
def inject():
    n = pend = dalerts = 0
    if "uid" in session:
        if session.get("role") == "doctor":
            u = q("SELECT doctor_id FROM users WHERE id=?", (session["uid"],), one=True)
            if u and u["doctor_id"]:
                ov = doctor_overview(u["doctor_id"]); pend, dalerts = ov["pending"], ov["alerts"]
        else:
            n = q("SELECT COUNT(*) c FROM alerts WHERE user_id=? AND resolved=0", (session["uid"],), one=True)["c"]
    return dict(open_alerts=n, pending_count=pend, doc_alert_count=dalerts, user=getattr(g, "user", None), doc=getattr(g, "doc", None),
                today=dt.date.today().isoformat(), emergency_numbers=config.EMERGENCY_NUMBERS)

def _home(): return url_for("doctor_dashboard" if session.get("role") == "doctor" else "dashboard")

# ------------------------------------------------------------------ auth pages
@app.route("/")
def index(): return redirect(_home() if "uid" in session else url_for("login"))

def _do_login(role, template):
    if "uid" in session: return redirect(_home())
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            if (u["role"] or "patient") != role:
                flash("This is a doctor account - please use the Doctor login." if role == "patient" else "This is a patient account - please use the Patient login.", "error")
            else:
                session.clear(); session["uid"] = u["id"]; session["role"] = role
                nxt = request.args.get("next", "")
                ok = nxt.startswith("/") and not nxt.startswith("//") and "\\" not in nxt and nxt.startswith("/doctor") == (role == "doctor")
                return redirect(nxt if ok else _home())
        else: flash("Invalid email or password.", "error")
    return render_template(template)

@app.route("/login", methods=["GET", "POST"])
def login(): return _do_login("patient", "login.html")

@app.route("/doctor/login", methods=["GET", "POST"])
def doctor_login(): return _do_login("doctor", "doctor_login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form; email = f["email"].strip().lower()
        if len(f["password"]) < 6: flash("Password must be at least 6 characters.", "error")
        elif q("SELECT 1 FROM users WHERE email=?", (email,), one=True): flash("Email already registered.", "error")
        else:
            x("INSERT INTO users(name,email,password_hash,age,gender,height_cm,phone,emergency_name,emergency_phone,role) VALUES(?,?,?,?,?,?,?,?,?,'patient')",
              (f["name"].strip(), email, generate_password_hash(f["password"]), f.get("age") or None, f.get("gender"),
               f.get("height_cm") or None, f.get("phone"), f.get("emergency_name"), f.get("emergency_phone")))
            flash("Account created. Please sign in.", "ok"); return redirect(url_for("login"))
    return render_template("register.html")

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
def _specialties():
    return sorted({r[0] for r in q("SELECT DISTINCT specialty FROM doctors")} | {v["specialty"] for v in AI.symptom.kb.values()})

@app.route("/doctor/register", methods=["GET", "POST"])
def doctor_register():
    if request.method == "POST":
        f = request.form; email = f["email"].strip().lower(); days = [d for d in f.getlist("days") if d in DAYS]
        name = f["name"].strip()
        for pre in ("dr.", "dr "):
            if name.lower().startswith(pre): name = name[len(pre):].strip()
        try: exp = int(f.get("experience") or 0)
        except ValueError: exp = -1
        if not name or not f.get("license", "").strip(): flash("Name and medical registration number are required.", "error")
        elif len(f["password"]) < 6: flash("Password must be at least 6 characters.", "error")
        elif f["specialty"] not in _specialties(): flash("Choose a valid specialty.", "error")
        elif not days: flash("Select at least one working day.", "error")
        elif not 0 <= exp <= 60: flash("Enter valid years of experience.", "error")
        elif q("SELECT 1 FROM users WHERE email=?", (email,), one=True): flash("Email already registered.", "error")
        else:
            did = x("INSERT INTO doctors(name,specialty,experience,rating,days,license) VALUES(?,?,?,?,?,?)",
                    ("Dr. " + name, f["specialty"], exp, 0, ",".join(d for d in DAYS if d in days), f["license"].strip()))
            x("INSERT INTO users(name,email,password_hash,phone,role,doctor_id) VALUES(?,?,?,?,'doctor',?)",
              ("Dr. " + name, email, generate_password_hash(f["password"]), f.get("phone"), did))
            flash("Doctor account created. Please sign in.", "ok"); return redirect(url_for("doctor_login"))
    return render_template("doctor_register.html", specs=_specialties(), days=DAYS)

@app.route("/logout", methods=["POST", "GET"])
def logout():
    role = session.get("role", "patient"); session.clear(); return redirect(url_for("logged_out", role=role))

@app.route("/logged-out")
def logged_out(): return render_template("logout.html", role=request.args.get("role", "patient"))

# ------------------------------------------------------------------- features
@app.route("/dashboard")
@login_required
def dashboard():
    uid = g.user["id"]
    last = q("SELECT * FROM vitals WHERE user_id=? ORDER BY ts DESC LIMIT 1", (uid,), one=True)
    appts = [a for a in AI.appointment.upcoming(uid) if a["status"] in ("booked", "confirmed") and a["date"] >= dt.date.today().isoformat()][::-1][:3]
    alerts = q("SELECT * FROM alerts WHERE user_id=? AND resolved=0 ORDER BY id DESC LIMIT 3", (uid,))
    summ = AI.analytics.summary(uid, AI.reminder.adherence(uid))
    log = q("SELECT * FROM agent_log WHERE user_id=? ORDER BY id DESC LIMIT 12", (uid,))
    return render_template("dashboard.html", last=last, appts=appts, alerts=alerts, summ=summ, log=log,
                           agents=AI.agents(), nlp_acc=AI.symptom.accuracy)

@app.route("/records", methods=["GET", "POST"])
@login_required
def records():
    uid = g.user["id"]
    if request.method == "POST":
        if request.form["kind"] == "vitals":
            flash("Vitals saved." if AI.records.add_vitals(uid, request.form) else "Enter at least one value.", "ok")
        else:
            x("INSERT INTO records(user_id,date,category,title,notes) VALUES(?,?,?,?,?)", (uid, request.form["date"], request.form["category"],
              request.form["title"].strip(), request.form["notes"].strip())); flash("Record saved.", "ok")
        return redirect(url_for("records"))
    return render_template("records.html", vitals=q("SELECT * FROM vitals WHERE user_id=? ORDER BY ts DESC LIMIT 30", (uid,)),
                           recs=q("SELECT r.*, d.name doctor FROM records r LEFT JOIN doctors d ON d.id=r.doctor_id WHERE r.user_id=? ORDER BY r.date DESC, r.id DESC", (uid,)))

@app.post("/records/delete/<kind>/<int:i>")
@login_required
def delete_record(kind, i):
    tbl = {"vitals": "vitals", "record": "records"}.get(kind)
    if tbl: x(f"DELETE FROM {tbl} WHERE id=? AND user_id=?" + (" AND doctor_id IS NULL" if tbl == "records" else ""), (i, g.user["id"]))
    return redirect(url_for("records"))

@app.route("/appointments", methods=["GET", "POST"])
@login_required
def appointments():
    uid = g.user["id"]
    if request.method == "POST":
        ok, msg = AI.appointment.book(uid, int(request.form["doctor_id"]), request.form["date"], request.form["time"], request.form["reason"].strip())
        flash(msg, "ok" if ok else "error"); return redirect(url_for("appointments"))
    docs = q("SELECT * FROM doctors ORDER BY specialty, rating DESC")
    return render_template("appointments.html", docs=docs, appts=AI.appointment.upcoming(uid), sel=request.args.get("doctor", type=int))

@app.get("/api/slots")
@login_required
def api_slots(): return jsonify(AI.appointment.slots(request.args.get("doctor", type=int), request.args.get("date", "")))

@app.get("/api/next-date")
@login_required
def api_next_date():
    doc = request.args.get("doctor", type=int)
    start = dt.date.today()
    for i in range(30):
        d = (start + dt.timedelta(days=i)).isoformat()
        if AI.appointment.slots(doc, d): return jsonify(date=d)
    return jsonify(date=None)

@app.post("/appointments/cancel/<int:i>")
@login_required
def cancel_appt(i): AI.appointment.cancel(g.user["id"], i); flash("Appointment cancelled.", "ok"); return redirect(url_for("appointments"))

@app.route("/reminders", methods=["GET", "POST"])
@login_required
def reminders():
    uid = g.user["id"]
    if request.method == "POST":
        f = request.form
        x("INSERT INTO reminders(user_id,medicine,dosage,time,start_date,end_date,notes) VALUES(?,?,?,?,?,?,?)",
          (uid, f["medicine"].strip(), f["dosage"].strip(), f["time"], f["start_date"], f.get("end_date", ""), f.get("notes", "")))
        flash("Reminder added.", "ok"); return redirect(url_for("reminders"))
    return render_template("reminders.html", all=q("SELECT r.*, d.name doctor FROM reminders r LEFT JOIN doctors d ON d.id=r.doctor_id WHERE r.user_id=? AND r.active=1 ORDER BY r.time", (uid,)),
                           adh=AI.reminder.adherence(uid))

@app.get("/api/reminders")
@login_required
def api_reminders():
    return jsonify(AI.reminder.status_today(g.user["id"], request.args.get("date", dt.date.today().isoformat()), request.args.get("time", dt.datetime.now().strftime("%H:%M"))))

@app.post("/api/reminders/<int:i>/take")
@login_required
def api_take(i): AI.reminder.take(g.user["id"], i, request.args.get("date", dt.date.today().isoformat())); return jsonify(ok=True)

@app.post("/reminders/delete/<int:i>")
@login_required
def del_reminder(i): x("UPDATE reminders SET active=0 WHERE id=? AND user_id=?", (i, g.user["id"])); return redirect(url_for("reminders"))

@app.route("/symptoms", methods=["GET", "POST"])
@login_required
def symptoms():
    res = docs = None; text = ""
    if request.method == "POST":
        text = request.form["text"].strip()
        if len(text) < 4: flash("Please describe your symptoms.", "error")
        else:
            res = AI.symptom.analyze(text, g.user["id"]); docs = AI.doctor.recommend(res["specialty"], 3)
    hist = q("SELECT * FROM symptom_checks WHERE user_id=? ORDER BY id DESC LIMIT 8", (g.user["id"],))
    return render_template("symptoms.html", res=res, docs=docs, text=text, hist=hist, acc=AI.symptom.accuracy, ntrain=AI.symptom.n_train)

@app.route("/doctors")
@login_required
def doctors():
    spec = request.args.get("specialty", "")
    specs = AI.doctor.all_specialties()
    last = q("SELECT specialty FROM symptom_checks WHERE user_id=? ORDER BY id DESC LIMIT 1", (g.user["id"],), one=True)
    rec = AI.doctor.recommend(last["specialty"], 3) if last else []
    lst = [dict(r) for r in q("SELECT * FROM doctors" + (" WHERE specialty=?" if spec else "") + " ORDER BY rating DESC", (spec,) if spec else ())]
    return render_template("doctors.html", specs=specs, spec=spec, docs=lst, rec=rec, rec_spec=last["specialty"] if last else None)

@app.route("/emergency", methods=["GET", "POST"])
@login_required
def emergency():
    uid = g.user["id"]
    if request.method == "POST":
        if request.form.get("action") == "sos":
            AI.emergency.sos(uid, request.form.get("note", "")); flash("SOS alert raised and your emergency contact has been notified (simulated). If this is life-threatening, call your local emergency number now.", "error")
        elif request.form.get("action") == "resolve": x("UPDATE alerts SET resolved=1 WHERE id=? AND user_id=?", (request.form["id"], uid))
        return redirect(url_for("emergency"))
    return render_template("emergency.html", alerts=q("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC LIMIT 40", (uid,)),
                           notified=q("SELECT * FROM agent_log WHERE user_id=? AND event='notify.contact' ORDER BY id DESC LIMIT 5", (uid,)))

@app.route("/analytics")
@login_required
def analytics():
    uid = g.user["id"]; adh = AI.reminder.adherence(uid)
    return render_template("analytics.html", s=AI.analytics.summary(uid, adh), adh=adh,
                           checks=q("SELECT top_disease d, COUNT(*) c FROM symptom_checks WHERE user_id=? GROUP BY d ORDER BY c DESC LIMIT 6", (uid,)))

@app.route("/agents")
@login_required
def agents():
    return render_template("agents.html", agents=AI.agents(), log=q("SELECT * FROM agent_log WHERE user_id=? ORDER BY id DESC LIMIT 60", (g.user["id"],)),
                           acc=AI.symptom.accuracy, ntrain=AI.symptom.n_train)

# --------------------------------------------------------------- doctor portal
def _appts(doc_id, where="", args=(), order="a.date, a.time"):
    return q(f"""SELECT a.*, u.name patient, u.age, u.gender FROM appointments a JOIN users u ON u.id=a.user_id
                 WHERE a.doctor_id=? {where} ORDER BY {order}""", (doc_id, *args))

@app.route("/doctor")
@doctor_required
def doctor_dashboard():
    did = g.doc["id"]; t = dt.date.today().isoformat()
    ov = doctor_overview(did)
    today_list = _appts(did, "AND a.date=? AND a.status IN ('booked','confirmed')", (t,))
    pending = _appts(did, "AND a.status='booked' AND a.date>=?", (t,))[:6]
    alerts = q("""SELECT al.*, u.name patient FROM alerts al JOIN users u ON u.id=al.user_id WHERE al.resolved=0 AND al.user_id IN
                  (SELECT user_id FROM appointments WHERE doctor_id=? AND status!='cancelled') ORDER BY al.id DESC LIMIT 5""", (did,))
    return render_template("doctor_dashboard.html", ov=ov, today_list=today_list, pending=pending, alerts=alerts)

@app.route("/doctor/appointments")
@doctor_required
def doctor_appointments():
    did = g.doc["id"]; t = dt.date.today().isoformat(); flt = request.args.get("f", "upcoming")
    if flt == "pending": rows = _appts(did, "AND a.status='booked' AND a.date>=?", (t,))
    elif flt == "past": rows = _appts(did, "AND (a.status IN ('completed','no_show') OR (a.date<? AND a.status!='cancelled'))", (t,), "a.date DESC, a.time DESC")
    elif flt == "all": rows = _appts(did, order="a.date DESC, a.time DESC")
    else: flt = "upcoming"; rows = _appts(did, "AND a.status IN ('booked','confirmed') AND a.date>=?", (t,))
    return render_template("doctor_appointments.html", rows=rows, flt=flt)

@app.post("/doctor/appointments/<int:i>/status")
@doctor_required
def doctor_appt_status(i):
    ok, msg = AI.appointment.set_status(g.doc["id"], i, request.form.get("action", ""), request.form.get("note", ""))
    flash(msg, "ok" if ok else "error")
    nxt = request.form.get("next", "")
    return redirect(nxt if nxt.startswith("/doctor") and not nxt.startswith("//") else url_for("doctor_appointments"))

@app.route("/doctor/patients")
@doctor_required
def doctor_patients(): return render_template("doctor_patients.html", pts=AI.consult.patients(g.doc["id"]))

def _patient_or_404(uid):
    p = q("SELECT * FROM users WHERE id=? AND role='patient'", (uid,), one=True)
    if not p or not AI.consult.can_view(g.doc["id"], uid): abort(404)  # doctors only see their own patients
    return p

@app.route("/doctor/patients/<int:uid>")
@doctor_required
def doctor_patient(uid):
    p = _patient_or_404(uid); did = g.doc["id"]
    return render_template("doctor_patient.html", p=p, s=AI.analytics.summary(uid, AI.reminder.adherence(uid)),
        recs=q("SELECT r.*, d.name doctor FROM records r LEFT JOIN doctors d ON d.id=r.doctor_id WHERE r.user_id=? ORDER BY r.date DESC, r.id DESC", (uid,)),
        checks=q("SELECT * FROM symptom_checks WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)),
        meds=q("SELECT r.*, d.name doctor FROM reminders r LEFT JOIN doctors d ON d.id=r.doctor_id WHERE r.user_id=? AND r.active=1 ORDER BY r.time", (uid,)),
        alerts=q("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)),
        appts=_appts(did, "AND a.user_id=?", (uid,), "a.date DESC, a.time DESC"))

@app.post("/doctor/patients/<int:uid>/note")
@doctor_required
def doctor_note(uid):
    _patient_or_404(uid); f = request.form
    ok = AI.consult.add_note(g.doc["id"], uid, f.get("category", "Diagnosis"), f.get("title", ""), f.get("notes", ""))
    flash("Note added to the patient's record." if ok else "A title is required.", "ok" if ok else "error")
    return redirect(url_for("doctor_patient", uid=uid))

@app.post("/doctor/patients/<int:uid>/prescribe")
@doctor_required
def doctor_prescribe(uid):
    _patient_or_404(uid); f = request.form
    try: days = int(f.get("days", "0"))
    except ValueError: days = 0
    ok, msg = AI.consult.prescribe(g.doc["id"], uid, f.get("medicine", ""), f.get("dosage", ""), f.get("times", ""), days,
                                   f.get("notes", ""), override=bool(f.get("override")))
    flash(msg, "ok" if ok else "error")
    return redirect(url_for("doctor_patient", uid=uid))

@app.route("/doctor/alerts", methods=["GET", "POST"])
@doctor_required
def doctor_alerts():
    did = g.doc["id"]; scope = "(SELECT user_id FROM appointments WHERE doctor_id=? AND status!='cancelled')"
    if request.method == "POST":
        x(f"UPDATE alerts SET resolved=1 WHERE id=? AND user_id IN {scope}", (request.form["id"], did))
        flash("Alert marked as resolved.", "ok"); return redirect(url_for("doctor_alerts"))
    return render_template("doctor_alerts.html", alerts=q(f"""SELECT al.*, u.name patient FROM alerts al JOIN users u ON u.id=al.user_id
                                                            WHERE al.user_id IN {scope} ORDER BY al.resolved, al.id DESC LIMIT 60""", (did,)))

@app.route("/doctor/schedule", methods=["GET", "POST"])
@doctor_required
def doctor_schedule():
    did = g.doc["id"]
    if request.method == "POST":
        act = request.form.get("action")
        if act == "days":
            days = [d for d in DAYS if d in request.form.getlist("days")]
            if days: x("UPDATE doctors SET days=? WHERE id=?", (",".join(days), did)); flash("Working days updated.", "ok")
            else: flash("Select at least one working day.", "error")
        elif act == "leave":
            d = request.form.get("date", "")
            try: valid = dt.date.fromisoformat(d) >= dt.date.today()
            except ValueError: valid = False
            if not valid: flash("Choose today or a future date.", "error")
            else:
                x("INSERT INTO doctor_leave(doctor_id,date,reason) VALUES(?,?,?)", (did, d, request.form.get("reason", "").strip()))
                n = q("SELECT COUNT(*) c FROM appointments WHERE doctor_id=? AND date=? AND status IN ('booked','confirmed')", (did, d), one=True)["c"]
                flash("Day blocked - no new bookings." + (f" {n} existing appointment(s) that day still need to be cancelled or handled." if n else ""), "ok")
        elif act == "unleave": x("DELETE FROM doctor_leave WHERE id=? AND doctor_id=?", (request.form.get("id"), did)); flash("Leave removed.", "ok")
        return redirect(url_for("doctor_schedule"))
    return render_template("doctor_schedule.html", days=DAYS, mine=g.doc["days"].split(","),
        leave=q("SELECT * FROM doctor_leave WHERE doctor_id=? AND date>=? ORDER BY date", (did, dt.date.today().isoformat())))

@app.route("/doctor/profile", methods=["GET", "POST"])
@doctor_required
def doctor_profile():
    if request.method == "POST":
        f = request.form; name = f["name"].strip()
        try: exp = int(f.get("experience", ""))
        except ValueError: exp = -1
        if not name or f["specialty"] not in _specialties() or not 0 <= exp <= 60: flash("Please check your details.", "error")
        else:
            name = name if name.lower().startswith("dr") else "Dr. " + name
            x("UPDATE doctors SET name=?, specialty=?, experience=? WHERE id=?", (name, f["specialty"], exp, g.doc["id"]))
            x("UPDATE users SET name=?, phone=? WHERE id=?", (name, f.get("phone"), g.user["id"])); flash("Profile updated.", "ok")
        return redirect(url_for("doctor_profile"))
    return render_template("doctor_profile.html", specs=_specialties())

# ------------------------------------------------------------------- demo data
def seed_demo():
    with app.app_context():
        if q("SELECT 1 FROM users WHERE email='demo@health.com'", one=True): return
        random.seed(7)
        uid = x("INSERT INTO users(name,email,password_hash,age,gender,height_cm,phone,emergency_name,emergency_phone) VALUES(?,?,?,?,?,?,?,?,?)",
                ("Demo Patient", "demo@health.com", generate_password_hash("demo123"), 42, "Female", 163, "+91 90000 00000", "Ravi (Husband)", "+91 98888 88888"))
        today = dt.date.today()
        for i in range(20, -1, -1):
            d = today - dt.timedelta(days=i)
            x("INSERT INTO vitals(user_id,ts,systolic,diastolic,heart_rate,glucose,temperature,weight,spo2) VALUES(?,?,?,?,?,?,?,?,?)",
              (uid, f"{d} 08:00", random.randint(120, 142), random.randint(78, 92), random.randint(66, 88), random.randint(95, 135),
               round(random.uniform(36.4, 37.2), 1), round(68 - i * 0.05 + random.uniform(-.3, .3), 1), random.randint(95, 99)))
        x("INSERT INTO records(user_id,date,category,title,notes) VALUES(?,?,?,?,?)", (uid, str(today - dt.timedelta(days=60)), "Diagnosis", "Hypertension (Stage 1)", "Started on amlodipine 5 mg. Review in 3 months."))
        x("INSERT INTO records(user_id,date,category,title,notes) VALUES(?,?,?,?,?)", (uid, str(today - dt.timedelta(days=30)), "Lab report", "HbA1c 6.1%", "Pre-diabetic range. Diet counselling advised."))
        x("INSERT INTO records(user_id,date,category,title,notes) VALUES(?,?,?,?,?)", (uid, str(today - dt.timedelta(days=200)), "Allergy", "Penicillin allergy", "Rash and itching."))
        r1 = x("INSERT INTO reminders(user_id,medicine,dosage,time,start_date,end_date,notes) VALUES(?,?,?,?,?,?,?)", (uid, "Amlodipine", "5 mg", "08:30", str(today - dt.timedelta(days=20)), "", "After breakfast"))
        r2 = x("INSERT INTO reminders(user_id,medicine,dosage,time,start_date,end_date,notes) VALUES(?,?,?,?,?,?,?)", (uid, "Metformin", "500 mg", "20:00", str(today - dt.timedelta(days=20)), "", "After dinner"))
        for i in range(1, 15):
            d = str(today - dt.timedelta(days=i))
            for r in (r1, r2):
                if random.random() < 0.85: x("INSERT INTO reminder_log(reminder_id,user_id,date,taken_at) VALUES(?,?,?,?)", (r, uid, d, d))
        x("INSERT INTO symptom_checks(user_id,ts,text,symptoms,top_disease,confidence,severity,specialty) VALUES(?,?,?,?,?,?,?,?)",
          (uid, f"{today - dt.timedelta(days=5)} 10:00", "headache and dizziness", "headache, dizziness", "Hypertension", 41.0, 3, "Cardiologist"))

def seed_doctor_demo():
    with app.app_context():
        if q("SELECT 1 FROM users WHERE email='doctor@health.com'", one=True): return
        doc = q("SELECT * FROM doctors WHERE name='Dr. Anjali Sharma'", one=True)
        if not doc: return
        x("INSERT INTO users(name,email,password_hash,phone,role,doctor_id) VALUES(?,?,?,?,'doctor',?)",
          (doc["name"], "doctor@health.com", generate_password_hash("doctor123"), "+91 91111 11111", doc["id"]))
        x("UPDATE doctors SET license=? WHERE id=?", ("DEMO-12345", doc["id"]))
        random.seed(11); today = dt.date.today(); days = doc["days"].split(",")
        def workday(offset):
            d = today + dt.timedelta(days=offset)
            while d.strftime("%a") not in days: d += dt.timedelta(days=1)
            return d
        demo = q("SELECT id FROM users WHERE email='demo@health.com'", one=True)
        if demo:
            x("INSERT INTO appointments(user_id,doctor_id,date,time,reason,status,doctor_notes) VALUES(?,?,?,?,?,?,?)",
              (demo["id"], doc["id"], str(today - dt.timedelta(days=12)), "10:00", "BP review", "completed", "BP controlled on amlodipine. Continue; review in 3 months."))
            x("INSERT INTO appointments(user_id,doctor_id,date,time,reason,status) VALUES(?,?,?,?,?,?)", (demo["id"], doc["id"], str(workday(0)), "16:00", "Headache and dizziness", "confirmed"))
        # second demo patient with a critical alert so the doctor dashboard has something to show
        if not q("SELECT 1 FROM users WHERE email='patient2@health.com'", one=True):
            p2 = x("INSERT INTO users(name,email,password_hash,age,gender,height_cm,phone,emergency_name,emergency_phone,role) VALUES(?,?,?,?,?,?,?,?,?,'patient')",
                   ("Ravi Kumar", "patient2@health.com", generate_password_hash("patient123"), 58, "Male", 172, "+91 92222 22222", "Sita (Wife)", "+91 93333 33333"))
            for i in range(14, -1, -1):
                d = today - dt.timedelta(days=i); hi = i < 3
                x("INSERT INTO vitals(user_id,ts,systolic,diastolic,heart_rate,glucose,temperature,weight,spo2) VALUES(?,?,?,?,?,?,?,?,?)",
                  (p2, f"{d} 07:30", random.randint(135, 150), random.randint(85, 95), random.randint(72, 92), random.randint(190, 240) if hi else random.randint(140, 180), 36.8, round(82 - i * 0.1, 1), random.randint(94, 98)))
            x("INSERT INTO records(user_id,date,category,title,notes) VALUES(?,?,?,?,?)", (p2, str(today - dt.timedelta(days=90)), "Diagnosis", "Type 2 Diabetes", "On metformin. Needs HbA1c follow-up."))
            x("INSERT INTO records(user_id,date,category,title,notes) VALUES(?,?,?,?,?)", (p2, str(today - dt.timedelta(days=300)), "Allergy", "Sulfa drug allergy", "Rash."))
            x("INSERT INTO alerts(user_id,ts,level,source,message) VALUES(?,?,?,?,?)", (p2, f"{today} 06:00", "critical", "Vitals monitor", "Blood glucose 312 mg/dL is critically high"))
            x("INSERT INTO appointments(user_id,doctor_id,date,time,reason,status) VALUES(?,?,?,?,?,?)", (p2, doc["id"], str(workday(0)), "15:00", "High sugar readings", "booked"))
            x("INSERT INTO appointments(user_id,doctor_id,date,time,reason,status) VALUES(?,?,?,?,?,?)", (p2, doc["id"], str(workday(1)), "11:30", "Follow-up", "booked"))

seed_demo(); seed_doctor_demo()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
