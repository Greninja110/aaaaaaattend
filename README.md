# College Attendance Management System

A full-stack, role-based web application built with Django and PostgreSQL that digitizes and automates the complete attendance management workflow for an engineering college — covering everything from timetable scheduling and real-time attendance recording to leave approvals, exception handling, department analytics, and student progression decisions.

The system serves five distinct user roles — Admin, HOD, Faculty, Lab Assistant, and Student — each with their own dedicated portal, URL namespace, and access-control decorator. Every action taken in the system is written to a `SystemLog` audit trail, and the 75 % attendance threshold is enforced uniformly across all five portals.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, Django 4.2.10 |
| **Database** | PostgreSQL (psycopg2-binary 2.9.9) |
| **Frontend** | Bootstrap 5.2, jQuery 3.6, Chart.js, Font Awesome 6.4, SweetAlert2, DataTables 1.11 |
| **Auth** | Custom `AbstractBaseUser` with email login + UUID-based password-reset tokens |
| **Image Handling** | Pillow 10.0.0 |
| **Date Utilities** | python-dateutil 2.8.2 |
| **Env Management** | python-dotenv 1.0.0 |
| **Timezone** | `Asia/Kolkata` (IST) |

---

## Quick Start

```bash
# 1. Enter the Django project root
cd attendance_system

# 2. Activate the virtual environment
source .venv/Scripts/activate        # WSL
# .venv\Scripts\activate             # PowerShell / CMD

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. Seed default roles + users
python manage.py create_default_users

# 6. Start the development server
python manage.py runserver
# → http://127.0.0.1:8000/
```

**Default credentials** (password: `password` per setup guide; seeded password via management command is `123`):

| Role | Email |
|---|---|
| Admin | `admin@mbit.edu.in` |
| HOD | `hod@mbit.edu.in` |
| Faculty | `faculty@mbit.edu.in` |
| Lab Assistant | `lab_assistant@mbit.edu.in` |
| Student | `student@mbit.edu.in` |

---

## Detailed Description

### Architecture Overview

The project is a monolithic Django application partitioned into six Django apps under `attendance_system/`:

```
authentication/       Custom User model, login/logout, password reset
core/                 All shared domain models imported by every portal
admin_portal/         System administration
hod_portal/           Department head management
faculty_portal/       Attendance recording and leave management
lab_assistant_portal/ Leave processing, attendance exceptions, lab tracking
student_portal/       Student self-service
```

**Authentication layer** (`authentication/`): A custom `User` model extending `AbstractBaseUser` replaces Django's default. The `USERNAME_FIELD` is `email`. Every user carries a foreign key to a `Role` row (role_name: `admin | hod | faculty | lab_assistant | student`). After login, `redirect_to_portal` reads the role name and redirects the browser to the correct portal. Password reset uses UUID tokens stored in `PasswordResetToken` (24-hour TTL) with a Gmail SMTP email flow.

**Core models** (`core/models.py`): All domain models shared across portals live here. No portal duplicates them.

| Model | Purpose |
|---|---|
| `Department` | Institution departments (CE, IT, ASH …) |
| `AcademicYear` | Year ranges; exactly one `is_current=True` at a time |
| `ClassSection` | e.g. CE1, CE2, IT1 — linked to a Department |
| `Batch` | Lab groups A/B/C/D |
| `Faculty` | OneToOne → User; holds employee_id, designation, weekly_hours_limit |
| `Student` | OneToOne → User; holds roll_number, current_semester (1–8), class_section, batch |
| `Subject` | subject_code, has_theory, has_lab, is_elective flags |
| `ElectiveSubject` | Extends Subject for semesters 5–8; groups subjects into elective pools |
| `FacultySubject` | Pivot: Faculty × Subject × ClassSection × Batch × AcademicYear × is_lab |
| `Timetable` | Slot: FacultySubject × day_of_week × start/end_time × room; unique on (room, time, day) and (faculty_subject, time, day) |
| `Attendance` | Student × FacultySubject × date → status: `present / absent / dont_care`; unique on (student, faculty_subject, date) |
| `LeaveApplication` | Student → `pending → faculty_approved → lab_approved / rejected` |
| `SystemLog` | Audit trail of all significant portal actions with IP address |

**Role-based access**: Each portal defines its own decorator (`admin_required`, `faculty_required`, `hod_required`, `lab_assistant_required`) that checks `user.get_role()` and either proceeds or renders `error.html`. There is no Django permissions/groups integration — role logic is entirely handled in application code.

---

### Complete Request Flow

```
Browser  →  /login/  →  user_login()  →  authenticate()
                                       ↓
                              redirect_to_portal()
                                       ↓
            /admin-portal/  /hod-portal/  /faculty-portal/  /lab-assistant-portal/  /student-portal/
```

Each portal URL namespace is independently mounted in `attendance_system/urls.py`.

---

### Portal-by-Portal Feature Breakdown

#### Admin Portal (`/admin-portal/`)

The admin is the only role that can write to the structural tables (departments, academic years, subjects, faculty assignments, timetable). Every mutation is wrapped in `transaction.atomic()` and logged via `log_admin_action()`.

**Dashboard** — System-wide counters (students, faculty, departments, active users), role distribution pie chart data, recent 10 system logs, current academic year indicator.

**User Management** — Full CRUD with server-side search/filter by role and status, 20-per-page pagination. Creating a faculty or student user triggers a secondary "additional details" form (employee_id / roll_number, department, DOB etc.) which creates the corresponding `Faculty` or `Student` row. Password change is a separate protected view.

**Bulk Import** — CSV upload for students and faculty. `handle_uploaded_csv()` in `admin_portal/utils.py` processes rows individually inside a transaction, creating both the `User` and the role-specific profile row in one shot. Validation catches: duplicate email, duplicate username, duplicate roll/employee_id, missing department code. Results are stored in `BulkImportLog`. Downloadable CSV templates are provided for students, faculty, and lab assistants.

**Department Management** — CRUD for departments; code is forced to uppercase on save.

**Academic Year Management** — CRUD; setting a year as "current" automatically clears the flag from all others (enforced both in the model's `save()` override and the `set_current_academic_year` view).

**Subject Management** — CRUD for subjects. Marking `is_elective=True` dynamically shows an inline `ElectiveSubjectForm` to capture the elective group name. Elective records are cascaded on subject update/delete.

**Faculty Assignment** — CRUD for `FacultySubject`. AJAX endpoints filter subjects and class sections by department for dependent dropdowns. Conflict validation prevents duplicate (faculty, subject, section, batch, year, is_lab) combinations.

**Timetable Management** — CRUD for timetable slots. Room-conflict and faculty-conflict detection is handled via DB unique constraints. AJAX endpoint returns faculty subjects filtered by faculty_id + academic_year_id for the form dropdown.

**Reports** — Attendance report (filter by department/semester/subject/date range, CSV export) and Faculty Workload report (filter by department/faculty/year, CSV export). Note: these views currently return placeholder summary data; the filter infrastructure is complete but aggregation from the `Attendance` table is stubbed.

**System Logs** — Full-text + user + action + date-range filter, 25-per-page pagination, timestamped CSV export.

**Settings** — `AdminSetting` key-value store for: `attendance_threshold` (default 75), `default_password`, `session_timeout`, `enable_email_notifications`. Saved via `update_or_create`.

---

#### HOD Portal (`/hod-portal/`)

A HOD is a `Faculty` row where the matching `Department.hod_id` points to their `faculty_id`. `get_hod_department()` resolves this relationship on every request.

**Dashboard** — Active faculty/student/subject counts; students grouped by semester (1–8); subject-wise attendance percentages for the department's subjects vs the 75 % threshold; top-10 low-attendance students; faculty workload table (assigned subjects, weekly timetable slots, utilisation % vs weekly_hours_limit); last 10 activity log entries scoped to the department.

**Department Reports** — Two report types switchable via `?type=`:
- `attendance`: per-student present/absent/percentage, filterable by semester and subject, CSV export.
- `faculty_workload`: per-faculty hours and utilisation, CSV export.

**Student Progression** — Lists all active department students with their current semester and overall attendance %. Students above 75 % are marked `eligible` and `can_promote` (if semester < 8). HOD selects eligible students via checkboxes and POSTs to promote them, which increments `current_semester` inside `transaction.atomic()` and writes a `SystemLog` entry per student.

**Elective Management** — Lists all `ElectiveSubject` records for the department grouped by semester and elective_group. Enrollment counts are currently placeholders (awaiting `student_elective` model layer).

**Faculty Performance** — Per-faculty composite score: attendance recording rate (recorded sessions / assumed 30 per subject) + average attendance % in their classes. Sorted descending by performance score.

**Attendance Analytics** — Overall department attendance %; semester-wise breakdown (semesters 1–8); subject-wise breakdown with below-threshold flag; 6-month rolling monthly trend using `relativedelta`.

---

#### Faculty Portal (`/faculty-portal/`)

**Dashboard** — Today's classes (from `Timetable` filtered by today's weekday); per-subject attendance stats (avg %, total classes held); pending leave applications from the faculty's department; last 10 attendance records the faculty has entered.

**Timetable** — Weekly schedule organized into a `{day: [entries]}` dict.

**Attendance Recording** — Choose a `FacultySubject` from a list; the system fetches students matching department + semester + (optionally) class section and batch. A POST submits per-student `present/absent` statuses. Existing records for the date are deleted and re-created atomically (`bulk_create`). Re-recording the same session is allowed (acts as an edit).

**Bulk Attendance Upload** — CSV upload (columns: `roll_number, student_name, date, status`). Each row is validated and upserted via `update_or_create` inside a transaction. The first 10 errors are surfaced to the user. A pre-filled downloadable template is generated per `faculty_subject_id` with all enrolled students defaulted to `present`.

**Attendance History** — Paginated list of all attendance records across the faculty's subjects, filterable by subject.

**Leave Management** — Visible: all leave applications from faculty's department students. Approve → sets `status = faculty_approved`, records `faculty_approval = faculty`. Reject → renders a form collecting `rejection_reason`, sets `status = rejected`. Both actions write to `SystemLog`.

**Reports** — Per-subject attendance report: for each student in the subject's class section/batch, counts present/absent, computes percentage, flags below-threshold. CSV export.

---

#### Lab Assistant Portal (`/lab-assistant-portal/`)

Lab assistants are linked to one department via the `LabAssistant` model (`lab_assistant` DB table). They handle the second step of the leave approval pipeline and manage attendance exceptions.

**Dashboard** — Pending leave count (faculty_approved in their dept); today's lab session count; students with low attendance (below 75 %); leaves approved this month by this assistant; today's lab schedule fetched via a **raw SQL query** joining `timetable → faculty_subject → subjects → faculty → users → batches → class_sections`.

**Leave Applications** — Displays `faculty_approved` applications scoped to the lab assistant's department. Filterable by status, department, semester, date range. Statistics: pending/approved/rejected counts and percentages. Per-application: `approve` → `lab_approved` + records `lab_assistant_approval`; `reject` → `rejected`. Both log to `SystemLog`.

**Attendance Exceptions** — Wraps the `AttendanceException` model. When a lab assistant creates an exception it is auto-approved and immediately modifies the underlying `Attendance.status` field. Existing pending exceptions (created by faculty via the `requested_by` Faculty FK) can be approved/rejected, updating `Attendance.status` on approval.

**Low Attendance Monitoring** — Scans all department students, computes attendance % per student, lists those below the configurable threshold (default 75 %). Filterable by department, semester, subject, threshold value.

**Lab Issue Tracking** — `LabIssue` model: lab_name, issue_type (hardware/software/network/environment/other), priority (low/medium/high/critical), status (open/in_progress/resolved). Lab assistants report issues and mark them resolved with resolution notes.

**Scheduled Reports** — `ScheduledReport` model: report type, frequency (daily/weekly/monthly), format (pdf/csv/excel), recipient email list, JSON filters, active/paused status.

---

#### Student Portal (`/student-portal/`)

This is the most feature-complete portal with the deepest view logic.

**Dashboard** — Aggregated overview: overall attendance %, total subjects, subjects below 75 % with warning list, today's classes (from timetable filtered by section + batch + weekday) each annotated with `is_past` and `attended` flags, last 5 notifications with time-ago labels, 6-month monthly attendance trend (data for Chart.js), subject-wise monthly data per subject (up to 5, for a multi-line chart). Supports AJAX refresh (`?refresh=true`) returning the same data as JSON.

**Attendance Summary** — Subject-level table: present/absent/leave/dont_care counts, percentage. Totals row. Filterable by subject, month, status.

**Subject Attendance Detail** — Per-subject breakdown with all individual attendance records (date, faculty, type, status). Computes `classes_needed` — the minimum consecutive future present marks to cross the 75 % line. Monthly chart data for the subject. Attendance correction request: submits `AttendanceCorrectionRequest` with optional evidence file upload (PDF/JPEG/PNG, max 2 MB). Corrections only allowed within 3 days of the attendance record. On submission, a `Notification` is sent to the recording faculty.

**Attendance History** — Semester-wise breakdown. For each semester 1 through `current_semester`, lists subjects and their attendance percentages.

**Timetable** — Three views in one page: (1) **weekly grid** (`generate_weekly_timetable`) — rows are unique time slots, columns are Mon–Sat; (2) **daily list** (`get_daily_classes`) — for a selected or current date; (3) **full list** (`get_list_view_classes`) — all slots across the week. A **faculty contacts** section shows each faculty's email and which subjects they teach the student. A **schedule changes** section currently returns placeholder/hardcoded data (pending a `schedule_changes` table).

**Leave Application** — Submit new applications: leave type (medical/family/event/personal/other), start date, end date, reason (required), optional document attachment (PDF/JPEG/PNG, max 2 MB), and acknowledgment checkbox. Validation: start date ≥ tomorrow, end date ≥ start, duration ≤ leave balance. Default annual leave limit: 15 days. On submission, notifies all faculty teaching that student's class section via the `Notification` model. Cancel: allowed while `pending` or `faculty_approved`.

**Notifications** — Full notification centre: filterable by category (attendance/leave/academics/system), searchable by title/message, paginated 10 per page, mark-read per-item or bulk mark-all-read via AJAX, inline detail modal via AJAX, configurable per-category email and in-app toggles stored in `NotificationSetting`.

**Profile** — Rich student profile: personal info (contact, address, blood_group, DOB), social media links (LinkedIn/GitHub/Twitter/Instagram), parent/guardian info (name, occupation, contact for both parents), emergency contact + relation. Separate skill update (stored as JSON array in `StudentProfile.skills`). Profile photo upload (JPEG/PNG/GIF, max 2 MB, stored in `media/profile_photos/`). UI preferences (light/dark theme, default view, notifications toggle) stored in `UserPreference`. Password change (min 8 chars, current password verification, logs out on success).

---

### Database Design Highlights

The full schema lives in `attendance_system/sql-database.sql` and includes PostgreSQL-specific features that Django's ORM does not replicate:

- **Trigger** `update_modified_column()` — updates `updated_at` on every UPDATE for users, faculty, and students tables.
- **DB-level email constraint** — `CHECK (email LIKE '%@mbit.edu.in')` on the `users` table. This is NOT enforced by Django's forms except in `UserForgotPasswordForm`.
- **DB Views** — `student_attendance_percentage`, `faculty_timetable_view`, `low_attendance_students` — used for reporting queries.
- **Stored Functions** — `get_student_attendance_percentage(student_id, subject_id, year_id)` returns FLOAT; `check_student_semester_attendance_eligibility(student_id, semester, year_id)` returns BOOLEAN — these gate the HOD's progression decisions.

Tables defined in SQL but **not yet backed by Django models**: `student_subject`, `student_elective`, `semester_progression`, `faculty_substitution`. These represent planned features that have DB-level structure but no ORM layer yet.

---

### Known Gaps and Pending Items

| Area | Status |
|---|---|
| `pandas` import in `admin_portal/utils.py` | Disabled — Python 3.12 compatibility issue; bulk import falls back to stdlib `csv` |
| `pandas` import in `student_portal/views.py` | Still imported at top — will raise ImportError if pandas is not installed |
| Admin attendance/workload reports | Filter infrastructure complete; aggregation returns placeholder data |
| Student timetable schedule changes | `get_schedule_changes()` returns hardcoded dummy data |
| HOD elective enrollment counts | Placeholder 0 — awaiting `StudentElective` Django model |
| Attendance history per past semester | Subject data is fetched but faculty name and total_classes are placeholder strings |
| Lab assistant notification settings | Mock dict in profile view — not persisted to DB |
| Faculty substitution workflow | Table exists in DB but no portal flow to create/approve substitutions |
| Student elective selection UI | DB table exists; no Django view or form |
| Email notifications | SMTP configured for Gmail; `EMAIL_HOST_PASSWORD` must be set to a Gmail App Password |

---

### Future Expansion Roadmap

**Near-term (feature completion)**
- Wire `student_subject` and `student_elective` tables to Django models to replace the current semester+department-based subject inference.
- Complete the faculty substitution workflow: faculty requests a substitute → admin approves → attendance recorded by substitute is flagged `is_substitution=True`.
- Connect semester progression to the `semester_progression` DB table and surface HOD decision history.
- Fix the admin attendance and faculty workload report views to query real `Attendance` data.
- Resolve the `pandas`/Python 3.12 compatibility issue (upgrade to pandas 2.x or replace with `openpyxl` for Excel support).

**Medium-term (new features)**
- **REST API layer** (Django REST Framework) to expose attendance, timetable, and leave data for a mobile application.
- **QR Code Attendance**: generate per-session QR codes; students scan to self-mark present (with faculty confirmation toggle).
- **Biometric Integration**: hook into fingerprint/face-recognition hardware via an API bridge.
- **SMS/WhatsApp Notifications**: integrate Twilio or MSG91 alongside the existing email channel.
- **Parent Portal**: read-only portal where parents can view their child's attendance and leave status using a separate login.
- **Student Elective Selection UI**: allow semesters 5–8 students to choose electives within their group before a deadline set by the admin.
- **Lesson Plan Tracking**: let faculty log the topic covered each class; surface it in attendance history and subject detail.
- **Advanced Analytics Dashboard**: subject-wise attendance heatmaps, semester-over-semester trend comparisons, dropout-risk scoring.

**Long-term (institutional integration)**
- **ERP Integration**: two-way sync with university ERP (fee management, exam registration) using student roll numbers as the common key.
- **Exam Eligibility Module**: auto-generate eligibility lists for end-semester exams based on 75 % threshold; export to exam controller.
- **Multi-campus Support**: extend `Department` and `User` models to support a `Campus` dimension for institutions with multiple branches.
- **AI-based Attendance Prediction**: use historical patterns to predict students likely to fall below threshold and trigger early warnings.
- **Offline / PWA Support**: allow faculty to record attendance offline (service worker + local IndexedDB) and sync when connectivity is restored.
- **Audit & Compliance Reports**: auto-generate semester-end compliance reports in the format required by AICTE/university for accreditation.

---

### Project Structure

```
attendance_system/                  ← Django project root (manage.py)
├── attendance_system/              ← Project settings, root URLs, wsgi/asgi
├── authentication/                 ← User, Role, PasswordResetToken; login/logout views
├── core/                           ← All shared domain models + create_default_users command
│   └── migrations/
├── admin_portal/                   ← Admin CRUD, bulk import, reports, settings
├── hod_portal/                     ← Department analytics, progression, electives
├── faculty_portal/                 ← Attendance recording, leave management, reports
├── lab_assistant_portal/           ← Leave processing, exceptions, lab tracking
│   ├── models.py                   ← LabAssistant, AttendanceException, LabIssue, ScheduledReport
│   └── migrations/
├── student_portal/                 ← Self-service portal
│   └── models.py                   ← Notification, StudentProfile, UserPreference,
│                                        NotificationSetting, AttendanceCorrectionRequest
├── templates/                      ← Global base.html, error.html
├── static/                         ← Project-wide CSS, JS, images
├── media/                          ← Uploaded files (profile_photos/, leave_documents/)
├── logs/                           ← lab_assistant_portal.log
├── sql-database.sql                ← Full PostgreSQL schema with views, triggers, functions
└── requirements.txt
```

---

### Configuration Notes

- **Database**: PostgreSQL `attendance_db` on `localhost:5432`, user `postgres`, password `12345`. Change in `settings.py → DATABASES`.
- **Email**: Set `EMAIL_HOST_PASSWORD` in `settings.py` to a Gmail App Password. For local development, switch to `django.core.mail.backends.console.EmailBackend` to print reset links to the terminal instead.
- **Media files**: Served by Django in `DEBUG=True` mode via `settings.MEDIA_URL`. In production, serve via Nginx/Apache and set `MEDIA_ROOT` accordingly.
- **Static files**: Run `python manage.py collectstatic` before deploying to production.
- **Secret key**: `settings.py` contains a hardcoded insecure `SECRET_KEY`. Replace with an environment variable before any production deployment.
