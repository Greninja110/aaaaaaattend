-- Create Roles table
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

-- Insert default roles
INSERT INTO roles (role_name, description) VALUES 
('admin', 'Full system access'),
('hod', 'Department head with department-wide access'),
('faculty', 'Teacher with subject and class access'),
('lab_assistant', 'Manages attendance exceptions and leave applications'),
('student', 'Student with personal data access only');

-- Create Departments table
CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL,
    department_code VARCHAR(10) NOT NULL UNIQUE,
    hod_id INT NULL
);

-- Insert default departments
INSERT INTO departments (department_name, department_code) VALUES 
('Computer Engineering', 'CE'),
('Information Technology', 'IT'),
('Applied Science and Humanities', 'ASH');

-- Create Users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    enrollment_number VARCHAR(14) UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE CHECK (email LIKE '%@mbit.edu.in'),
    full_name VARCHAR(100) NOT NULL,
    role_id INT NOT NULL REFERENCES roles(role_id),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_modtime
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Create Academic Years table
CREATE TABLE academic_years (
    academic_year_id SERIAL PRIMARY KEY,
    year_start INT NOT NULL,
    year_end INT NOT NULL,
    is_current BOOLEAN DEFAULT FALSE,
    CONSTRAINT valid_year_range CHECK (year_end = year_start + 1),
    CONSTRAINT unique_academic_year UNIQUE (year_start, year_end)
);

-- Create Class Sections table
CREATE TABLE class_sections (
    class_section_id SERIAL PRIMARY KEY,
    section_name VARCHAR(10) NOT NULL,
    department_id INT NOT NULL REFERENCES departments(department_id),
    CONSTRAINT unique_section_dept UNIQUE (section_name, department_id)
);

-- Insert default class sections
INSERT INTO class_sections (section_name, department_id) VALUES 
('CE1', 1),
('CE2', 1),
('CE3', 1),
('IT1', 2),
('IT2', 2);

-- Create Batches table for lab groups
CREATE TABLE batches (
    batch_id SERIAL PRIMARY KEY,
    batch_name CHAR(1) NOT NULL UNIQUE CHECK (batch_name IN ('A', 'B', 'C', 'D'))
);

-- Insert default batches
INSERT INTO batches (batch_name) VALUES ('A'), ('B'), ('C'), ('D');

-- Create Faculty table
CREATE TABLE faculty (
    faculty_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE REFERENCES users(user_id),
    employee_id VARCHAR(20) NOT NULL UNIQUE,
    department_id INT NOT NULL REFERENCES departments(department_id),
    dob DATE NOT NULL,
    joining_year INT NOT NULL,
    designation VARCHAR(100) NOT NULL,
    weekly_hours_limit INT DEFAULT 40,
    current_weekly_hours INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'on_leave'))
);

-- Create trigger for faculty
CREATE TRIGGER update_faculty_modtime
BEFORE UPDATE ON faculty
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Create Lab Assistant table
CREATE TABLE lab_assistant (
    assistant_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE REFERENCES users(user_id),
    department_id INT NOT NULL REFERENCES departments(department_id),
    dob DATE NOT NULL,
    joining_year INT NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'on_leave'))
);

-- Create Students table
CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE REFERENCES users(user_id),
    roll_number VARCHAR(20) NOT NULL UNIQUE,
    admission_year INT NOT NULL,
    dob DATE NOT NULL,
    batch_id INT REFERENCES batches(batch_id),
    class_section_id INT REFERENCES class_sections(class_section_id),
    department_id INT NOT NULL REFERENCES departments(department_id),
    current_semester INT NOT NULL CHECK (current_semester BETWEEN 1 AND 8),
    section VARCHAR(5),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'graduated', 'suspended'))
);

-- Create trigger for students
CREATE TRIGGER update_students_modtime
BEFORE UPDATE ON students
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Update departments table to reference faculty (HOD)
ALTER TABLE departments ADD CONSTRAINT fk_department_hod FOREIGN KEY (hod_id) REFERENCES faculty(faculty_id);

-- Create Subjects table
CREATE TABLE subjects (
    subject_id SERIAL PRIMARY KEY,
    subject_code VARCHAR(20) NOT NULL UNIQUE,
    subject_name VARCHAR(100) NOT NULL,
    department_id INT NOT NULL REFERENCES departments(department_id),
    semester INT NOT NULL CHECK (semester BETWEEN 1 AND 8),
    credits INT NOT NULL,
    has_theory BOOLEAN DEFAULT TRUE,
    has_lab BOOLEAN DEFAULT FALSE,
    is_elective BOOLEAN DEFAULT FALSE
);

-- Create Elective Subjects table
CREATE TABLE elective_subjects (
    elective_id SERIAL PRIMARY KEY,
    subject_id INT NOT NULL REFERENCES subjects(subject_id),
    elective_group VARCHAR(50) NOT NULL,
    semester INT NOT NULL CHECK (semester BETWEEN 5 AND 8),
    CONSTRAINT unique_subject_elective UNIQUE (subject_id)
);

-- Create Faculty-Subject mapping table
CREATE TABLE faculty_subject (
    faculty_subject_id SERIAL PRIMARY KEY,
    faculty_id INT NOT NULL REFERENCES faculty(faculty_id),
    subject_id INT NOT NULL REFERENCES subjects(subject_id),
    class_section_id INT REFERENCES class_sections(class_section_id),
    batch_id INT REFERENCES batches(batch_id),
    is_lab BOOLEAN DEFAULT FALSE,
    academic_year_id INT NOT NULL REFERENCES academic_years(academic_year_id),
    CONSTRAINT unique_faculty_subject_class_batch_year UNIQUE (faculty_id, subject_id, class_section_id, batch_id, academic_year_id, is_lab)
);

-- Create Student-Subject mapping table
CREATE TABLE student_subject (
    student_subject_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    subject_id INT NOT NULL REFERENCES subjects(subject_id),
    academic_year_id INT NOT NULL REFERENCES academic_years(academic_year_id),
    semester INT NOT NULL CHECK (semester BETWEEN 1 AND 8),
    is_repeat BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_student_subject_year UNIQUE (student_id, subject_id, academic_year_id)
);

-- Create Student-Elective mapping table
CREATE TABLE student_elective (
    student_elective_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    elective_id INT NOT NULL REFERENCES elective_subjects(elective_id),
    academic_year_id INT NOT NULL REFERENCES academic_years(academic_year_id),
    CONSTRAINT unique_student_elective_year UNIQUE (student_id, elective_id, academic_year_id)
);

-- Create Timetable table
CREATE TABLE timetable (
    timetable_id SERIAL PRIMARY KEY,
    faculty_subject_id INT NOT NULL REFERENCES faculty_subject(faculty_subject_id),
    day_of_week VARCHAR(10) NOT NULL CHECK (day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    room_number VARCHAR(20) NOT NULL,
    academic_year_id INT NOT NULL REFERENCES academic_years(academic_year_id),
    CONSTRAINT valid_time_range CHECK (end_time > start_time),
    CONSTRAINT unique_room_time_day UNIQUE (room_number, start_time, day_of_week, academic_year_id),
    CONSTRAINT unique_faculty_time_day UNIQUE (faculty_subject_id, start_time, day_of_week, academic_year_id)
);

-- Create Faculty Substitution table
CREATE TABLE faculty_substitution (
    substitution_id SERIAL PRIMARY KEY,
    timetable_id INT NOT NULL REFERENCES timetable(timetable_id),
    original_faculty_id INT NOT NULL REFERENCES faculty(faculty_id),
    substitute_faculty_id INT NOT NULL REFERENCES faculty(faculty_id),
    substitution_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    approved_by INT REFERENCES users(user_id),
    CONSTRAINT unique_substitution UNIQUE (timetable_id, substitution_date)
);

-- Create Attendance table
CREATE TABLE attendance (
    attendance_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    faculty_subject_id INT NOT NULL REFERENCES faculty_subject(faculty_subject_id),
    attendance_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('present', 'absent', 'dont_care')),
    recorded_by INT NOT NULL REFERENCES faculty(faculty_id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_substitution BOOLEAN DEFAULT FALSE,
    substitution_id INT REFERENCES faculty_substitution(substitution_id),
    CONSTRAINT unique_student_subject_date UNIQUE (student_id, faculty_subject_id, attendance_date)
);

-- Create Leave Application table
CREATE TABLE leave_application (
    leave_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT NOT NULL,
    document_path VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'faculty_approved', 'lab_approved', 'rejected')),
    faculty_approval INT REFERENCES faculty(faculty_id),
    lab_assistant_approval INT REFERENCES lab_assistant(assistant_id),
    CONSTRAINT valid_date_range CHECK (end_date >= start_date)
);

-- Create Semester Progression table
CREATE TABLE semester_progression (
    progression_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    from_semester INT NOT NULL CHECK (from_semester BETWEEN 1 AND 8),
    to_semester INT NOT NULL CHECK (to_semester BETWEEN 2 AND 8),
    academic_year_id INT NOT NULL REFERENCES academic_years(academic_year_id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('promoted', 'detained')),
    approved_by INT REFERENCES users(user_id),
    CONSTRAINT valid_semester_progression CHECK (to_semester = from_semester + 1),
    CONSTRAINT unique_student_progression UNIQUE (student_id, from_semester, academic_year_id)
);

-- Create Views for easier reporting

-- View for student attendance percentage by subject
CREATE VIEW student_attendance_percentage AS
SELECT 
    s.student_id, 
    s.full_name,
    s.roll_number,
    sub.subject_id,
    sub.subject_name,
    fs.faculty_subject_id,
    ay.year_start || '-' || ay.year_end AS academic_year,
    COUNT(a.attendance_id) AS total_classes,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS classes_attended,
    ROUND((SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END)::FLOAT / 
          COUNT(CASE WHEN a.status != 'dont_care' THEN 1 ELSE NULL END)::FLOAT) * 100, 2) AS attendance_percentage
FROM 
    attendance a
JOIN 
    faculty_subject fs ON a.faculty_subject_id = fs.faculty_subject_id
JOIN 
    subjects sub ON fs.subject_id = sub.subject_id
JOIN 
    students st ON a.student_id = st.student_id
JOIN 
    users s ON st.user_id = s.user_id
JOIN 
    academic_years ay ON fs.academic_year_id = ay.academic_year_id
WHERE 
    a.status != 'dont_care'
GROUP BY 
    s.student_id, s.full_name, s.roll_number, sub.subject_id, sub.subject_name, 
    fs.faculty_subject_id, ay.year_start, ay.year_end;

-- View for faculty timetable
CREATE VIEW faculty_timetable_view AS
SELECT 
    f.faculty_id,
    u.full_name AS faculty_name,
    s.subject_code,
    s.subject_name,
    cs.section_name AS class,
    b.batch_name AS batch,
    fs.is_lab,
    t.day_of_week,
    t.start_time,
    t.end_time,
    t.room_number,
    ay.year_start || '-' || ay.year_end AS academic_year
FROM 
    timetable t
JOIN 
    faculty_subject fs ON t.faculty_subject_id = fs.faculty_subject_id
JOIN 
    faculty f ON fs.faculty_id = f.faculty_id
JOIN 
    users u ON f.user_id = u.user_id
JOIN 
    subjects s ON fs.subject_id = s.subject_id
LEFT JOIN 
    class_sections cs ON fs.class_section_id = cs.class_section_id
LEFT JOIN 
    batches b ON fs.batch_id = b.batch_id
JOIN 
    academic_years ay ON t.academic_year_id = ay.academic_year_id;

-- View for students with attendance below 75%
CREATE VIEW low_attendance_students AS
SELECT 
    s.student_id,
    u.full_name AS student_name,
    s.roll_number,
    cs.section_name AS class,
    d.department_name,
    sub.subject_name,
    COUNT(a.attendance_id) AS total_classes,
    SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS classes_attended,
    ROUND((SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END)::FLOAT / 
          COUNT(CASE WHEN a.status != 'dont_care' THEN 1 ELSE NULL END)::FLOAT) * 100, 2) AS attendance_percentage
FROM 
    attendance a
JOIN 
    students s ON a.student_id = s.student_id
JOIN 
    users u ON s.user_id = u.user_id
JOIN 
    faculty_subject fs ON a.faculty_subject_id = fs.faculty_subject_id
JOIN 
    subjects sub ON fs.subject_id = sub.subject_id
JOIN 
    departments d ON s.department_id = d.department_id
LEFT JOIN 
    class_sections cs ON s.class_section_id = cs.class_section_id
WHERE 
    a.status != 'dont_care'
GROUP BY 
    s.student_id, u.full_name, s.roll_number, cs.section_name, d.department_name, sub.subject_name
HAVING 
    (SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END)::FLOAT / 
    COUNT(CASE WHEN a.status != 'dont_care' THEN 1 ELSE NULL END)::FLOAT) * 100 < 75;

-- Function to calculate student attendance percentage
CREATE OR REPLACE FUNCTION get_student_attendance_percentage(
    p_student_id INT,
    p_subject_id INT,
    p_academic_year_id INT
)
RETURNS FLOAT AS $$
DECLARE
    total_classes INT;
    classes_attended INT;
    percentage FLOAT;
BEGIN
    SELECT 
        COUNT(a.attendance_id),
        SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END)
    INTO 
        total_classes,
        classes_attended
    FROM 
        attendance a
    JOIN 
        faculty_subject fs ON a.faculty_subject_id = fs.faculty_subject_id
    WHERE 
        a.student_id = p_student_id
        AND fs.subject_id = p_subject_id
        AND fs.academic_year_id = p_academic_year_id
        AND a.status != 'dont_care';
    
    IF total_classes = 0 THEN
        RETURN 0;
    ELSE
        percentage := (classes_attended::FLOAT / total_classes::FLOAT) * 100;
        RETURN ROUND(percentage, 2);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to check if student has attendance >= 75% for all subjects in a semester
CREATE OR REPLACE FUNCTION check_student_semester_attendance_eligibility(
    p_student_id INT,
    p_semester INT,
    p_academic_year_id INT
)
RETURNS BOOLEAN AS $$
DECLARE
    all_subjects_eligible BOOLEAN := TRUE;
    subject_record RECORD;
BEGIN
    FOR subject_record IN (
        SELECT 
            s.subject_id
        FROM 
            student_subject ss
        JOIN 
            subjects s ON ss.subject_id = s.subject_id
        WHERE 
            ss.student_id = p_student_id
            AND ss.semester = p_semester
            AND ss.academic_year_id = p_academic_year_id
    ) LOOP
        IF get_student_attendance_percentage(p_student_id, subject_record.subject_id, p_academic_year_id) < 75 THEN
            all_subjects_eligible := FALSE;
            EXIT;
        END IF;
    END LOOP;
    
    RETURN all_subjects_eligible;
END;
$$ LANGUAGE plpgsql;