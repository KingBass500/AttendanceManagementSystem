# Attendance Management System

A Flask + SQLite web-based Attendance Management System with role-based access for administrators, lecturers and students.

## Visual redesign
The interface has been redesigned to closely follow the supplied reference: a dark navy sidebar, orange active navigation, clean white cards, compact dashboard statistics, recent lecture sessions, student attention alerts and responsive tables.

## Run in VS Code
1. Open this folder in VS Code.
2. Open a PowerShell terminal in the project folder.
3. If PowerShell blocks virtual-environment activation, you can skip activation and use the venv Python directly:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe app.py
```

4. Open `http://127.0.0.1:5000`.

## Demo accounts
- Admin: `admin` / `admin123`
- Lecturer: `lecturer1` / `lecturer123`
- Student: `student1` / `student123`

## Main features
- Role-based login
- Administrator dashboard
- Student and lecturer management
- Course and class management
- Lecture session creation
- Attendance marking: Present, Absent, Late, Excused
- Duplicate session protection
- Duplicate attendance protection
- Student attendance dashboard
- Attendance reports
- Password hashing
- SQLite database

For a production deployment, change the Flask secret key and use stronger account credentials.
