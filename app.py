from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import sqlite3
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"
DB = os.path.join(os.path.dirname(__file__), "attendance.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','lecturer','student')),
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        student_number TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT,
        class_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS lecturers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        employee_number TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT
    );

    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        lecturer_id INTEGER,
        FOREIGN KEY(lecturer_id) REFERENCES lecturers(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        class_id INTEGER NOT NULL,
        lecturer_id INTEGER NOT NULL,
        session_date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(subject_id, class_id, session_date),
        FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
        FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
        FOREIGN KEY(lecturer_id) REFERENCES lecturers(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        session_id INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present','Absent','Late','Excused')),
        recorded_at TEXT NOT NULL,
        UNIQUE(student_id, session_id),
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );
    """)
    seed(conn)
    conn.commit()
    conn.close()

def seed(conn):
    now = datetime.now().isoformat(timespec="seconds")
    users = [
        ("admin", "admin123", "admin"),
        ("lecturer1", "lecturer123", "lecturer"),
        ("student1", "student123", "student"),
        ("student2", "student123", "student"),
        ("student3", "student123", "student"),
    ]
    for username, password, role in users:
        conn.execute(
            "INSERT OR IGNORE INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
            (username, generate_password_hash(password), role, now)
        )

    conn.execute("INSERT OR IGNORE INTO classes(name,description) VALUES(?,?)",
                 ("DIT3A", "Diploma in Information Technology - Year 3"))
    class_id = conn.execute("SELECT id FROM classes WHERE name='DIT3A'").fetchone()["id"]

    lecturer_user = conn.execute("SELECT id FROM users WHERE username='lecturer1'").fetchone()["id"]
    conn.execute("""INSERT OR IGNORE INTO lecturers
                    (user_id,employee_number,first_name,last_name,email)
                    VALUES(?,?,?,?,?)""",
                 (lecturer_user, "LEC001", "John", "Mokoena", "john@example.com"))
    lecturer_id = conn.execute("SELECT id FROM lecturers WHERE employee_number='LEC001'").fetchone()["id"]

    for username, number, first, last in [
        ("student1","STU001","Ladie","Basosila"),
        ("student2","STU002","Thabo","Mokoena"),
        ("student3","STU003","Aisha","Naidoo"),
    ]:
        uid = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]
        conn.execute("""INSERT OR IGNORE INTO students
                        (user_id,student_number,first_name,last_name,email,class_id)
                        VALUES(?,?,?,?,?,?)""",
                     (uid, number, first, last, f"{username}@example.com", class_id))

    conn.execute("""INSERT OR IGNORE INTO subjects(code,name,lecturer_id)
                    VALUES(?,?,?)""", ("PRG301","Programming 3", lecturer_id))
    conn.execute("""INSERT OR IGNORE INTO subjects(code,name,lecturer_id)
                    VALUES(?,?,?)""", ("DBS301","Database Systems 3", lecturer_id))

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.context_processor
def inject_user():
    return {"current_user": session}

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    role = session["role"]
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "lecturer":
        return redirect(url_for("lecturer_dashboard"))
    return redirect(url_for("student_dashboard"))

@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    conn = get_db()
    counts = {
        "students": conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"],
        "lecturers": conn.execute("SELECT COUNT(*) c FROM lecturers").fetchone()["c"],
        "classes": conn.execute("SELECT COUNT(*) c FROM classes").fetchone()["c"],
        "subjects": conn.execute("SELECT COUNT(*) c FROM subjects").fetchone()["c"],
        "sessions": conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"],
    }
    recent_sessions = conn.execute("""SELECT se.*, su.code, su.name subject_name, c.name class_name,
        l.first_name || ' ' || l.last_name lecturer_name
        FROM sessions se
        JOIN subjects su ON su.id=se.subject_id
        JOIN classes c ON c.id=se.class_id
        JOIN lecturers l ON l.id=se.lecturer_id
        ORDER BY se.session_date DESC, se.id DESC LIMIT 5""").fetchall()
    attention_students = conn.execute("""SELECT s.student_number, s.first_name, s.last_name, c.name class_name,
        ROUND(CASE WHEN COUNT(a.id)=0 THEN 0.0 ELSE
        (SUM(CASE WHEN a.status IN ('Present','Late','Excused') THEN 1 ELSE 0 END) * 100.0 / COUNT(a.id)) END, 1) percentage
        FROM students s
        LEFT JOIN classes c ON c.id=s.class_id
        LEFT JOIN attendance a ON a.student_id=s.id
        GROUP BY s.id
        HAVING COUNT(a.id) > 0 AND percentage < 75
        ORDER BY percentage ASC, s.last_name LIMIT 5""").fetchall()
    conn.close()
    return render_template("admin_dashboard.html", counts=counts, recent_sessions=recent_sessions, attention_students=attention_students)

@app.route("/admin/sessions")
@role_required("admin")
def admin_sessions():
    conn = get_db()
    rows = conn.execute("""SELECT se.*, su.code, su.name subject_name, c.name class_name,
        l.first_name || ' ' || l.last_name lecturer_name,
        COUNT(a.id) student_count
        FROM sessions se
        JOIN subjects su ON su.id=se.subject_id
        JOIN classes c ON c.id=se.class_id
        JOIN lecturers l ON l.id=se.lecturer_id
        LEFT JOIN attendance a ON a.session_id=se.id
        GROUP BY se.id
        ORDER BY se.session_date DESC, se.id DESC""").fetchall()
    conn.close()
    return render_template("admin_sessions.html", sessions=rows)

@app.route("/admin/users")
@role_required("admin")
def users():
    conn = get_db()
    rows = conn.execute("SELECT username, role FROM users ORDER BY role, username").fetchall()
    conn.close()
    return render_template("users.html", users=rows)

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")

@app.route("/admin/students", methods=["GET","POST"])
@role_required("admin")
def students():
    conn = get_db()
    if request.method == "POST":
        try:
            username = request.form["username"].strip()
            password = request.form["password"]
            student_number = request.form["student_number"].strip()
            first = request.form["first_name"].strip()
            last = request.form["last_name"].strip()
            email = request.form.get("email","").strip()
            class_id = request.form.get("class_id") or None
            cur = conn.execute("""INSERT INTO users(username,password_hash,role,created_at)
                                  VALUES(?,?,?,?)""",
                               (username, generate_password_hash(password), "student",
                                datetime.now().isoformat(timespec="seconds")))
            uid = cur.lastrowid
            conn.execute("""INSERT INTO students
                            (user_id,student_number,first_name,last_name,email,class_id)
                            VALUES(?,?,?,?,?,?)""",
                         (uid,student_number,first,last,email,class_id))
            conn.commit()
            flash("Student added successfully.", "success")
        except sqlite3.IntegrityError as e:
            conn.rollback()
            flash("Could not add student. Username or student number may already exist.", "danger")
    rows = conn.execute("""SELECT s.*, c.name class_name FROM students s
                           LEFT JOIN classes c ON c.id=s.class_id ORDER BY s.last_name""").fetchall()
    classes = conn.execute("SELECT * FROM classes ORDER BY name").fetchall()
    conn.close()
    return render_template("students.html", students=rows, classes=classes)

@app.route("/admin/classes", methods=["GET","POST"])
@role_required("admin")
def classes():
    conn = get_db()
    if request.method == "POST":
        try:
            conn.execute("INSERT INTO classes(name,description) VALUES(?,?)",
                         (request.form["name"].strip(), request.form.get("description","").strip()))
            conn.commit()
            flash("Class added.", "success")
        except sqlite3.IntegrityError:
            flash("Class name already exists.", "danger")
    rows = conn.execute("SELECT * FROM classes ORDER BY name").fetchall()
    conn.close()
    return render_template("classes.html", classes=rows)

@app.route("/admin/subjects", methods=["GET","POST"])
@role_required("admin")
def subjects():
    conn = get_db()
    if request.method == "POST":
        try:
            conn.execute("INSERT INTO subjects(code,name,lecturer_id) VALUES(?,?,?)",
                         (request.form["code"].strip(), request.form["name"].strip(),
                          request.form.get("lecturer_id") or None))
            conn.commit()
            flash("Subject added.", "success")
        except sqlite3.IntegrityError:
            flash("Subject code already exists.", "danger")
    rows = conn.execute("""SELECT s.*, l.first_name || ' ' || l.last_name lecturer
                           FROM subjects s LEFT JOIN lecturers l ON l.id=s.lecturer_id
                           ORDER BY s.code""").fetchall()
    lecturers = conn.execute("SELECT * FROM lecturers ORDER BY last_name").fetchall()
    conn.close()
    return render_template("subjects.html", subjects=rows, lecturers=lecturers)

@app.route("/admin/lecturers", methods=["GET","POST"])
@role_required("admin")
def lecturers():
    conn = get_db()
    if request.method == "POST":
        try:
            username = request.form["username"].strip()
            password = request.form["password"]
            employee_number = request.form["employee_number"].strip()
            first = request.form["first_name"].strip()
            last = request.form["last_name"].strip()
            email = request.form.get("email","").strip()
            cur = conn.execute("""INSERT INTO users(username,password_hash,role,created_at)
                                  VALUES(?,?,?,?)""",
                               (username, generate_password_hash(password), "lecturer",
                                datetime.now().isoformat(timespec="seconds")))
            uid = cur.lastrowid
            conn.execute("""INSERT INTO lecturers
                            (user_id,employee_number,first_name,last_name,email)
                            VALUES(?,?,?,?,?)""",
                         (uid,employee_number,first,last,email))
            conn.commit()
            flash("Lecturer added.", "success")
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Could not add lecturer. Username or employee number may already exist.", "danger")
    rows = conn.execute("SELECT * FROM lecturers ORDER BY last_name").fetchall()
    conn.close()
    return render_template("lecturers.html", lecturers=rows)

@app.route("/lecturer")
@role_required("lecturer")
def lecturer_dashboard():
    conn = get_db()
    lecturer = conn.execute("""SELECT * FROM lecturers WHERE user_id=?""",
                            (session["user_id"],)).fetchone()
    sessions = conn.execute("""SELECT se.*, su.code, su.name subject_name, c.name class_name
                               FROM sessions se
                               JOIN subjects su ON su.id=se.subject_id
                               JOIN classes c ON c.id=se.class_id
                               WHERE se.lecturer_id=?
                               ORDER BY se.session_date DESC""",
                            (lecturer["id"],)).fetchall()
    conn.close()
    return render_template("lecturer_dashboard.html", lecturer=lecturer, sessions=sessions)

@app.route("/lecturer/session/new", methods=["GET","POST"])
@role_required("lecturer")
def new_session():
    conn = get_db()
    lecturer = conn.execute("SELECT * FROM lecturers WHERE user_id=?", (session["user_id"],)).fetchone()
    subjects = conn.execute("SELECT * FROM subjects WHERE lecturer_id=? ORDER BY code", (lecturer["id"],)).fetchall()
    classes = conn.execute("SELECT * FROM classes ORDER BY name").fetchall()
    if request.method == "POST":
        try:
            cur = conn.execute("""INSERT INTO sessions
                (subject_id,class_id,lecturer_id,session_date,created_at)
                VALUES(?,?,?,?,?)""",
                (request.form["subject_id"],request.form["class_id"],lecturer["id"],
                 request.form["session_date"],datetime.now().isoformat(timespec="seconds")))
            session_id = cur.lastrowid
            students = conn.execute("SELECT id FROM students WHERE class_id=?", (request.form["class_id"],)).fetchall()
            for st in students:
                conn.execute("""INSERT INTO attendance(student_id,session_id,status,recorded_at)
                                VALUES(?,?,?,?)""",
                             (st["id"],session_id,"Absent",datetime.now().isoformat(timespec="seconds")))
            conn.commit()
            flash("Session created. Mark attendance below.", "success")
            return redirect(url_for("mark_attendance", session_id=session_id))
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("A session for this subject, class and date already exists.", "danger")
    conn.close()
    return render_template("new_session.html", subjects=subjects, classes=classes)

@app.route("/lecturer/session/<int:session_id>/attendance", methods=["GET","POST"])
@role_required("lecturer")
def mark_attendance(session_id):
    conn = get_db()
    lec = conn.execute("SELECT id FROM lecturers WHERE user_id=?", (session["user_id"],)).fetchone()
    info = conn.execute("""SELECT se.*, su.code, su.name subject_name, c.name class_name
                           FROM sessions se
                           JOIN subjects su ON su.id=se.subject_id
                           JOIN classes c ON c.id=se.class_id
                           WHERE se.id=? AND se.lecturer_id=?""", (session_id,lec["id"])).fetchone()
    if not info:
        conn.close()
        abort(404)
    if request.method == "POST":
        for key, value in request.form.items():
            if key.startswith("status_"):
                student_id = key.split("_",1)[1]
                if value in ("Present","Absent","Late","Excused"):
                    conn.execute("""UPDATE attendance SET status=?, recorded_at=?
                                    WHERE student_id=? AND session_id=?""",
                                 (value,datetime.now().isoformat(timespec="seconds"),student_id,session_id))
        conn.commit()
        flash("Attendance saved successfully.", "success")
    records = conn.execute("""SELECT a.*, s.student_number, s.first_name, s.last_name
                              FROM attendance a JOIN students s ON s.id=a.student_id
                              WHERE a.session_id=? ORDER BY s.last_name""", (session_id,)).fetchall()
    conn.close()
    return render_template("attendance.html", info=info, records=records)

@app.route("/student")
@role_required("student")
def student_dashboard():
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE user_id=?", (session["user_id"],)).fetchone()
    stats = conn.execute("""SELECT
        COUNT(a.id) total,
        SUM(CASE WHEN a.status IN ('Present','Late','Excused') THEN 1 ELSE 0 END) attended,
        SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) absent
        FROM attendance a WHERE a.student_id=?""", (student["id"],)).fetchone()
    total = stats["total"] or 0
    attended = stats["attended"] or 0
    percentage = round(attended / total * 100, 1) if total else 0
    records = conn.execute("""SELECT a.status, se.session_date, su.code, su.name subject_name
                              FROM attendance a
                              JOIN sessions se ON se.id=a.session_id
                              JOIN subjects su ON su.id=se.subject_id
                              WHERE a.student_id=?
                              ORDER BY se.session_date DESC""", (student["id"],)).fetchall()
    conn.close()
    return render_template("student_dashboard.html", student=student, stats=stats,
                           percentage=percentage, records=records)

@app.route("/reports")
@role_required("admin","lecturer")
def reports():
    conn = get_db()
    rows = conn.execute("""SELECT s.student_number, s.first_name, s.last_name,
                           c.name class_name,
                           COUNT(a.id) total,
                           SUM(CASE WHEN a.status IN ('Present','Late','Excused') THEN 1 ELSE 0 END) attended
                           FROM students s
                           LEFT JOIN classes c ON c.id=s.class_id
                           LEFT JOIN attendance a ON a.student_id=s.id
                           GROUP BY s.id ORDER BY s.last_name""").fetchall()
    report = []
    for r in rows:
        total = r["total"] or 0
        attended = r["attended"] or 0
        report.append({**dict(r), "percentage": round(attended/total*100,1) if total else 0})
    conn.close()
    return render_template("reports.html", report=report)

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You do not have permission to access this page."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="The requested page was not found."), 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
