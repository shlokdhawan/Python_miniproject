
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, send_from_directory
from flask import Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    user_type = db.Column(db.String(20))  # 'student' or 'company'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class StudentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    college = db.Column(db.String(200), nullable=False)
    cgpa = db.Column(db.Float, nullable=False)
    skills = db.Column(db.Text)  # JSON string of skills
    courses = db.Column(db.Text)  # JSON string of completed courses
    projects = db.Column(db.Text)  # JSON string of projects
    resume_path = db.Column(db.String(300))
    photo_path = db.Column(db.String(300))
    
    user = db.relationship('User', backref=db.backref('student_profile', uselist=False))

class CompanyProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    required_skills = db.Column(db.Text)  # JSON string
    min_cgpa = db.Column(db.Float)
    required_courses = db.Column(db.Text)  # JSON string
    
    user = db.relationship('User', backref=db.backref('company_profile', uselist=False))

class CourseSuggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    platform = db.Column(db.String(100))  # Coursera, Udemy, etc.
    url = db.Column(db.String(300))
    skills_covered = db.Column(db.Text)  # JSON string

class CompanyPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_profile.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    domain = db.Column(db.String(150))
    description = db.Column(db.Text)
    required_skills = db.Column(db.Text)  # JSON list
    required_courses = db.Column(db.Text)  # JSON list
    min_cgpa = db.Column(db.Float)
    
    company = db.relationship('CompanyProfile', backref=db.backref('positions', lazy=True))

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('company_position.id'), nullable=False)
    status = db.Column(db.String(50), default='applied')  # applied, reviewed, shortlisted, rejected, accepted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    match_percentage = db.Column(db.Float)
    matched_skills = db.Column(db.Text)  # JSON list
    missing_skills = db.Column(db.Text)  # JSON list

    __table_args__ = (
        db.UniqueConstraint('student_id', 'position_id', name='uq_student_position'),
    )

# --- Enhanced Matching Utilities ---
def safe_set_from_json(json_text):
    """Safely convert JSON string to set, return empty set if error"""
    try:
        return set(json.loads(json_text)) if json_text else set()
    except Exception:
        return set()

def compute_position_match(student_skills_set, student_courses_set, position: CompanyPosition):
    """Enhanced matching algorithm with detailed analysis"""
    required_skills = safe_set_from_json(position.required_skills)
    required_courses = safe_set_from_json(position.required_courses)

    matched_skills = student_skills_set.intersection(required_skills)
    missing_skills = required_skills - student_skills_set

    matched_courses = student_courses_set.intersection(required_courses)
    missing_courses = required_courses - student_courses_set

    # Calculate individual scores
    skills_den = len(required_skills)
    courses_den = len(required_courses)
    skills_score = (len(matched_skills) / skills_den) if skills_den > 0 else 1.0
    courses_score = (len(matched_courses) / courses_den) if courses_den > 0 else 1.0

    # Weighted overall score (skills are more important)
    overall = (0.8 * skills_score) + (0.2 * courses_score)
    match_percentage = round(overall * 100, 1)
    
    # Eligibility check
    is_eligible = match_percentage >= 100

    return {
        'match_percentage': match_percentage,
        'matched_skills': matched_skills,
        'missing_skills': missing_skills,
        'matched_courses': matched_courses,
        'missing_courses': missing_courses,
        'is_eligible': is_eligible,
        'skills_score': round(skills_score * 100, 1),
        'courses_score': round(courses_score * 100, 1)
    }

def calculate_student_company_match(student, company):
    """Calculate match between a student and company requirements"""
    student_skills = safe_set_from_json(student.skills)
    student_courses = safe_set_from_json(student.courses)
    company_skills = safe_set_from_json(company.required_skills)
    company_courses = safe_set_from_json(company.required_courses)
    
    # Calculate matches
    matched_skills = student_skills.intersection(company_skills)
    missing_skills = company_skills - student_skills
    matched_courses = student_courses.intersection(company_courses)
    missing_courses = company_courses - student_courses
    
    # Calculate percentages
    total_required_skills = len(company_skills)
    total_required_courses = len(company_courses)
    
    skills_percentage = (len(matched_skills) / total_required_skills * 100) if total_required_skills > 0 else 100
    courses_percentage = (len(matched_courses) / total_required_courses * 100) if total_required_courses > 0 else 100
    
    # Overall match percentage (weighted: 80% skills, 20% courses)
    overall_percentage = round((0.8 * skills_percentage) + (0.2 * courses_percentage), 1)
    
    # Eligibility check
    is_eligible = overall_percentage >= 100
    
    return {
        'student': student,
        'company': company,
        'match_percentage': overall_percentage,
        'skills_percentage': round(skills_percentage, 1),
        'courses_percentage': round(courses_percentage, 1),
        'matched_skills': list(matched_skills),
        'missing_skills': list(missing_skills),
        'matched_courses': list(matched_courses),
        'missing_courses': list(missing_courses),
        'is_eligible': is_eligible,
        'total_required_skills': total_required_skills,
        'total_required_courses': total_required_courses
    }


def get_company_candidate_analysis(company_id):
    """Get detailed analysis of all candidates for a specific company"""
    company = CompanyProfile.query.get(company_id)
    if not company:
        return None
    
    students = StudentProfile.query.all()
    candidates = []
    
    for student in students:
        match_data = calculate_student_company_match(student, company)
        candidates.append(match_data)
    
    # Sort by match percentage (highest first)
    candidates.sort(key=lambda x: x['match_percentage'], reverse=True)
    
    return {
        'company': company,
        'candidates': candidates,
        'total_candidates': len(candidates),
        'eligible_candidates': len([c for c in candidates if c['is_eligible']]),
        'average_match': round(sum(c['match_percentage'] for c in candidates) / len(candidates), 1) if candidates else 0
    }

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, user_type=user_type)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            if user.user_type == 'student':
                return redirect(next_page or url_for('student_dashboard'))
            else:
                return redirect(next_page or url_for('company_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
def student_profile():
    if current_user.user_type != 'student':
        flash('Access denied')
        return redirect(url_for('index'))
    
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        name = request.form['name']
        college = request.form['college']
        cgpa = float(request.form['cgpa'])
        skills = request.form.getlist('skills[]')
        courses = request.form.getlist('courses[]')
        projects = request.form.getlist('projects[]')
        
        # Handle resume upload
        resume = request.files.get('resume')
        resume_path = None
        if resume and resume.filename:
            filename = secure_filename(f"{current_user.id}_{resume.filename}")
            resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume.save(resume_path)

        # Handle profile photo upload (png/jpg/jpeg)
        photo = request.files.get('photo')
        photo_path = None
        if photo and photo.filename:
            photo_filename = secure_filename(f"{current_user.id}_photo_{photo.filename}")
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
            photo.save(photo_path)
        
        if profile:
            profile.name = name
            profile.college = college
            profile.cgpa = cgpa
            profile.skills = json.dumps(skills)
            profile.courses = json.dumps(courses)
            profile.projects = json.dumps(projects)
            if resume_path:
                profile.resume_path = resume_path
            if photo_path:
                profile.photo_path = photo_path
        else:
            profile = StudentProfile(
                user_id=current_user.id,
                name=name,
                college=college,
                cgpa=cgpa,
                skills=json.dumps(skills),
                courses=json.dumps(courses),
                projects=json.dumps(projects),
                resume_path=resume_path,
                photo_path=photo_path
            )
            db.session.add(profile)
        
        db.session.commit()
        flash('Profile updated successfully')
        return redirect(url_for('student_dashboard'))
    
    # Prepopulate form data
    form_data = {
        'name': profile.name if profile else '',
        'college': profile.college if profile else '',
        'cgpa': profile.cgpa if profile else '',
        'skills': json.loads(profile.skills) if profile and profile.skills else [],
        'courses': json.loads(profile.courses) if profile and profile.courses else [],
        'projects': json.loads(profile.projects) if profile and profile.projects else [],
        'photo_filename': os.path.basename(profile.photo_path) if profile and profile.photo_path else None
    }
    
    return render_template('student_profile.html', form_data=form_data)

@app.route('/company/profile', methods=['GET', 'POST'])
@login_required
def company_profile():
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))
    
    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        min_cgpa = float(request.form['min_cgpa']) if request.form['min_cgpa'] else None
        required_skills = request.form.getlist('required_skills[]')
        required_courses = request.form.getlist('required_courses[]')
        
        if profile:
            profile.name = name
            profile.description = description
            profile.min_cgpa = min_cgpa
            profile.required_skills = json.dumps(required_skills)
            profile.required_courses = json.dumps(required_courses)
        else:
            profile = CompanyProfile(
                user_id=current_user.id,
                name=name,
                description=description,
                min_cgpa=min_cgpa,
                required_skills=json.dumps(required_skills),
                required_courses=json.dumps(required_courses)
            )
            db.session.add(profile)
        
        db.session.commit()
        flash('Profile updated successfully')
        return redirect(url_for('company_dashboard'))
    
    # Prepopulate form data
    form_data = {
        'name': profile.name if profile else '',
        'description': profile.description if profile else '',
        'min_cgpa': profile.min_cgpa if profile else '',
        'required_skills': json.loads(profile.required_skills) if profile and profile.required_skills else [],
        'required_courses': json.loads(profile.required_courses) if profile and profile.required_courses else []
    }
    
    return render_template('company_profile.html', form_data=form_data)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.user_type != 'student':
        flash('Access denied')
        return redirect(url_for('index'))
    
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash('Please complete your profile first')
        return redirect(url_for('student_profile'))
    
    # Get all companies and positions
    companies = CompanyProfile.query.all()
    positions = CompanyPosition.query.all()
    
    # Calculate matches using enhanced matching
    matches = []
    student_skills = set(json.loads(profile.skills)) if profile.skills else set()
    student_courses = set(json.loads(profile.courses)) if profile.courses else set()
    
    for pos in positions:
        company = pos.company
        # Check if student meets minimum CGPA requirement for position (fallback to company if position not set)
        min_required = pos.min_cgpa if pos.min_cgpa is not None else (company.min_cgpa if company else None)
        if min_required and profile.cgpa < min_required:
            continue

        # Use enhanced matching function
        metrics = compute_position_match(student_skills, student_courses, pos)
        matched_skills = metrics['matched_skills']
        missing_skills = metrics['missing_skills']
        match_percentage = metrics['match_percentage']
        is_eligible = metrics['is_eligible']
        skills_score = metrics['skills_score']
        courses_score = metrics['courses_score']

        applications = []
        try:
            applications = Application.query.filter_by(student_id=profile.id, position_id=pos.id).all()
        except Exception:
            applications = []

        has_applied = len(applications) > 0

        if match_percentage >= 30:  # show reasonable matches
            matches.append({
                'company': company,
                'position': pos,
                'match_percentage': round(match_percentage),
                'missing_skills': list(missing_skills),
                'matched_skills': list(matched_skills),
                'has_applied': has_applied,
                'is_eligible': is_eligible,
                'skills_score': skills_score,
                'courses_score': courses_score
            })
    
    # Sort by match percentage (highest first)
    matches.sort(key=lambda x: x['match_percentage'], reverse=True)
    
    # Get course suggestions based on missing skills
    all_missing_skills = set()
    for match in matches:
        all_missing_skills.update(match['missing_skills'])
    
    # Fetch and filter suggestions in Python to match any missing skill
    suggested_courses = []
    if all_missing_skills:
        all_courses = CourseSuggestion.query.all()
        for course in all_courses:
            try:
                covered = set(json.loads(course.skills_covered)) if course.skills_covered else set()
            except Exception:
                covered = set()
            if covered.intersection(all_missing_skills):
                suggested_courses.append(course)
    
    return render_template('student_dashboard.html', profile=profile, matches=matches, suggested_courses=suggested_courses, json=json)

@app.route('/company/dashboard')
@login_required
def company_dashboard():
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))
    
    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash('Please complete your profile first')
        return redirect(url_for('company_profile'))
    
    # Get positions for this company
    positions = CompanyProfile.query.filter_by(user_id=current_user.id).first().positions if profile else []

    # Get all students
    students = StudentProfile.query.all()
    
    # Find eligible students using enhanced matching
    eligible_students = []
    
    for student in students:
        # Check if student meets minimum CGPA requirement
        if profile.min_cgpa and student.cgpa < profile.min_cgpa:
            continue
        
        # Use enhanced matching function
        match_data = calculate_student_company_match(student, profile)
        
        if match_data['match_percentage'] >= 50:  # Only show students with at least 50% match (for display purposes)
            eligible_students.append({
                'student': student,
                'match_percentage': match_data['match_percentage'],
                'matched_skills': match_data['matched_skills'],
                'matched_courses': match_data['matched_courses'],
                'missing_skills': match_data['missing_skills'],
                'is_eligible': match_data['is_eligible'],
                'skills_percentage': match_data['skills_percentage'],
                'courses_percentage': match_data['courses_percentage']
            })
    
    # Sort by match percentage (highest first)
    eligible_students.sort(key=lambda x: x['match_percentage'], reverse=True)
    
    # Analytics data
    skill_distribution = {}
    for student in students:
        if student.skills:
            skills = json.loads(student.skills)
            for skill in skills:
                skill_distribution[skill] = skill_distribution.get(skill, 0) + 1
    
    return render_template('company_dashboard.html', profile=profile, 
                          eligible_students=eligible_students, skill_distribution=skill_distribution, positions=positions, json=json)

@app.route('/company/positions', methods=['GET', 'POST'])
@login_required
def company_positions():
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))

    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash('Please complete your profile first')
        return redirect(url_for('company_profile'))

    if request.method == 'POST':
        title = request.form['title']
        domain = request.form.get('domain', '')
        description = request.form.get('description', '')
        min_cgpa = float(request.form['min_cgpa']) if request.form.get('min_cgpa') else None
        required_skills = request.form.getlist('required_skills[]')
        required_courses = request.form.getlist('required_courses[]')

        position = CompanyPosition(
            company_id=profile.id,
            title=title,
            domain=domain,
            description=description,
            required_skills=json.dumps(required_skills),
            required_courses=json.dumps(required_courses),
            min_cgpa=min_cgpa
        )
        db.session.add(position)
        db.session.commit()
        flash('Position saved')
        return redirect(url_for('company_positions'))

    positions = CompanyPosition.query.filter_by(company_id=profile.id).all()
    return render_template('company_positions.html', profile=profile, positions=positions, json=json)

@app.route('/apply/<int:position_id>', methods=['POST'])
@login_required
def apply_position(position_id):
    if current_user.user_type != 'student':
        flash('Access denied')
        return redirect(url_for('index'))

    position = CompanyPosition.query.get_or_404(position_id)
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash('Please complete your profile first')
        return redirect(url_for('student_profile'))

    student_skills = set(json.loads(profile.skills)) if profile.skills else set()
    student_courses = set(json.loads(profile.courses)) if profile.courses else set()
    metrics = compute_position_match(student_skills, student_courses, position)
    matched_skills = list(metrics['matched_skills'])
    missing_skills = list(metrics['missing_skills'])
    match_percentage = metrics['match_percentage']

    existing = Application.query.filter_by(student_id=profile.id, position_id=position.id).first()
    if existing:
        flash('You have already applied for this position')
        return redirect(url_for('student_dashboard'))

    app_row = Application(
        student_id=profile.id,
        position_id=position.id,
        status='applied',
        match_percentage=match_percentage,
        matched_skills=json.dumps(matched_skills),
        missing_skills=json.dumps(missing_skills)
    )
    db.session.add(app_row)
    db.session.commit()
    flash('Application submitted')
    return redirect(url_for('student_dashboard'))

@app.route('/company/students')
@login_required
def company_students():
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))
    students = StudentProfile.query.all()
    rows = []
    for s in students:
        try:
            skills = ', '.join(json.loads(s.skills)) if s.skills else ''
        except Exception:
            skills = ''
        try:
            courses = ', '.join(json.loads(s.courses)) if s.courses else ''
        except Exception:
            courses = ''
        try:
            projects = ', '.join(json.loads(s.projects)) if s.projects else ''
        except Exception:
            projects = ''

        rows.append({
            'id': s.id,
            'username': s.user.username if s.user else '',
            'email': s.user.email if s.user else '',
            'name': s.name,
            'college': s.college,
            'cgpa': s.cgpa,
            'skills': skills,
            'courses': courses,
            'projects': projects,
            'has_profile': bool(s.resume_path or skills or courses or projects),
        })
    return render_template('students_list.html', rows=rows)

@app.route('/company/students/export')
@login_required
def company_students_export():
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))

    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'username', 'email', 'name', 'college', 'cgpa', 'skills', 'courses', 'projects'])

    for s in StudentProfile.query.all():
        skills = ', '.join(json.loads(s.skills)) if s.skills else ''
        courses = ', '.join(json.loads(s.courses)) if s.courses else ''
        projects = ', '.join(json.loads(s.projects)) if s.projects else ''
        username = s.user.username if s.user else ''
        email = s.user.email if s.user else ''
        writer.writerow([s.id, username, email, s.name, s.college, s.cgpa, skills, courses, projects])

    resp = Response(output.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename=students.csv'
    return resp

@app.route('/company/positions/delete/<int:position_id>', methods=['POST'])
@login_required
def delete_company_position(position_id):
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))
    position = CompanyPosition.query.get_or_404(position_id)
    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or position.company_id != profile.id:
        flash('Not authorized')
        return redirect(url_for('company_positions'))
    db.session.delete(position)
    db.session.commit()
    flash('Position deleted')
    return redirect(url_for('company_positions'))

@app.route('/student/resume/generate')
@login_required
def generate_resume():
    if current_user.user_type != 'student':
        flash('Access denied')
        return redirect(url_for('index'))

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash('Please complete your profile first')
        return redirect(url_for('student_profile'))

    skills = json.loads(profile.skills) if profile.skills else []
    courses = json.loads(profile.courses) if profile.courses else []
    projects = json.loads(profile.projects) if profile.projects else []

    # Simple AI-like summary generation
    summary_parts = []
    if skills:
        summary_parts.append(f"Skilled in {', '.join(skills[:6])}.")
    if projects:
        summary_parts.append(f"Completed {len(projects)} project(s) demonstrating practical experience.")
    if courses:
        summary_parts.append(f"Finished {len(courses)} relevant course(s).")
    summary = ' '.join(summary_parts) or 'Motivated student seeking opportunities to apply and grow skills.'

    form_data = {
        'photo_filename': os.path.basename(profile.photo_path) if profile and profile.photo_path else None
    }
    return render_template('resume.html', profile=profile, skills=skills, courses=courses, projects=projects, summary=summary, form_data=form_data)

@app.route('/student/resume/view/<int:student_id>')
@login_required
def student_resume_view(student_id):
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))

    profile = StudentProfile.query.get_or_404(student_id)
    skills = json.loads(profile.skills) if profile.skills else []
    courses = json.loads(profile.courses) if profile.courses else []
    projects = json.loads(profile.projects) if profile.projects else []

    summary_parts = []
    if skills:
        summary_parts.append(f"Skilled in {', '.join(skills[:6])}.")
    if projects:
        summary_parts.append(f"Completed {len(projects)} project(s) demonstrating practical experience.")
    if courses:
        summary_parts.append(f"Finished {len(courses)} relevant course(s).")
    summary = ' '.join(summary_parts) or 'Motivated student seeking opportunities to apply and grow skills.'

    form_data = {
        'photo_filename': os.path.basename(profile.photo_path) if profile and profile.photo_path else None
    }
    return render_template('resume.html', profile=profile, skills=skills, courses=courses, projects=projects, summary=summary, form_data=form_data)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/student/resume/<int:student_id>')
@login_required
def view_resume(student_id):
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))
    
    student = StudentProfile.query.get_or_404(student_id)
    if student.resume_path and os.path.exists(student.resume_path):
        return send_file(student.resume_path)
    else:
        flash('Resume not available')
        return redirect(url_for('company_dashboard'))

@app.route('/position/<int:position_id>')
@login_required
def view_position_details(position_id):
    """Display detailed information about a specific position including required skills"""
    position = CompanyPosition.query.get_or_404(position_id)
    company = position.company
    
    # Parse required skills and courses
    required_skills = json.loads(position.required_skills) if position.required_skills else []
    required_courses = json.loads(position.required_courses) if position.required_courses else []
    
    # If user is a student, calculate their match with this position
    match_info = None
    if current_user.user_type == 'student':
        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        if profile:
            student_skills = set(json.loads(profile.skills)) if profile.skills else set()
            student_courses = set(json.loads(profile.courses)) if profile.courses else set()
            match_info = compute_position_match(student_skills, student_courses, position)
            
            # Check if student has already applied
            existing_application = Application.query.filter_by(
                student_id=profile.id, 
                position_id=position.id
            ).first()
            match_info['has_applied'] = existing_application is not None
    
    return render_template('position_details.html', 
                         position=position, 
                         company=company,
                         required_skills=required_skills,
                         required_courses=required_courses,
                         match_info=match_info,
                         json=json)


@app.route('/company/<int:company_id>/candidates')
@login_required
def company_candidates_analysis(company_id):
    """Detailed candidate analysis for a specific company"""
    if current_user.user_type != 'company':
        flash('Access denied')
        return redirect(url_for('index'))
    
    analysis = get_company_candidate_analysis(company_id)
    if not analysis:
        flash('Company not found')
        return redirect(url_for('company_dashboard'))
    
    return render_template('company_candidates.html', 
                         analysis=analysis,
                         json=json)

@app.route('/student/matches/export')
@login_required
def export_student_matches():
    """Export student's matches to CSV file"""
    if current_user.user_type != 'student':
        flash('Access denied')
        return redirect(url_for('index'))
    
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash('Please complete your profile first')
        return redirect(url_for('student_profile'))
    
    import csv
    from io import StringIO
    
    # Get all companies and positions
    companies = CompanyProfile.query.all()
    positions = CompanyPosition.query.all()
    
    # Calculate matches using enhanced matching
    matches = []
    student_skills = set(json.loads(profile.skills)) if profile.skills else set()
    student_courses = set(json.loads(profile.courses)) if profile.courses else set()
    
    for pos in positions:
        company = pos.company
        # Check if student meets minimum CGPA requirement for position (fallback to company if position not set)
        min_required = pos.min_cgpa if pos.min_cgpa is not None else (company.min_cgpa if company else None)
        if min_required and profile.cgpa < min_required:
            continue

        # Use enhanced matching function
        metrics = compute_position_match(student_skills, student_courses, pos)
        matched_skills = metrics['matched_skills']
        missing_skills = metrics['missing_skills']
        match_percentage = metrics['match_percentage']
        is_eligible = metrics['is_eligible']
        skills_score = metrics['skills_score']
        courses_score = metrics['courses_score']

        applications = []
        try:
            applications = Application.query.filter_by(student_id=profile.id, position_id=pos.id).all()
        except Exception:
            applications = []

        has_applied = len(applications) > 0

        if match_percentage >= 30:  # show reasonable matches
            matches.append({
                'company': company,
                'position': pos,
                'match_percentage': round(match_percentage),
                'missing_skills': list(missing_skills),
                'matched_skills': list(matched_skills),
                'has_applied': has_applied,
                'is_eligible': is_eligible,
                'skills_score': skills_score,
                'courses_score': courses_score
            })
    
    # Sort by match percentage (highest first)
    matches.sort(key=lambda x: x['match_percentage'], reverse=True)
    
    # Create CSV content
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Company Name', 'Position Title', 'Domain', 'Match Percentage', 
        'Skills Score', 'Courses Score', 'Eligible', 'Applied', 
        'Matched Skills', 'Missing Skills', 'Company Description'
    ])
    
    # Write data rows
    for match in matches:
        writer.writerow([
            match['company'].name,
            match['position'].title,
            match['position'].domain or '',
            f"{match['match_percentage']}%",
            f"{match['skills_score']}%",
            f"{match['courses_score']}%",
            'Yes' if match['is_eligible'] else 'No',
            'Yes' if match['has_applied'] else 'No',
            ', '.join(match['matched_skills']),
            ', '.join(match['missing_skills']),
            match['company'].description or ''
        ])
    
    # Create response
    resp = Response(output.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = f'attachment; filename=student_matches_{profile.name.replace(" ", "_")}.csv'
    return resp


if __name__ == '__main__':
    with app.app_context():
        # Lightweight migration: ensure photo_path column exists for StudentProfile
        try:
            result = db.session.execute(db.text("PRAGMA table_info('student_profile')"))
            columns = [row[1] for row in result]
            if 'photo_path' not in columns:
                db.session.execute(db.text("ALTER TABLE student_profile ADD COLUMN photo_path VARCHAR(300)"))
                db.session.commit()
        except Exception:
            pass

        db.create_all()
        
        # Add some sample course suggestions
        if not CourseSuggestion.query.first():
            courses = [
                CourseSuggestion(
                    name='Python for Data Science',
                    platform='Coursera',
                    url='https://www.coursera.org/learn/python-data-science',
                    skills_covered=json.dumps(['Python', 'Data Analysis', 'Pandas'])
                ),
                CourseSuggestion(
                    name='Machine Learning A-Z',
                    platform='Udemy',
                    url='https://www.udemy.com/course/machinelearning/',
                    skills_covered=json.dumps(['Machine Learning', 'Python', 'Data Science'])
                ),
                CourseSuggestion(
                    name='Web Development Bootcamp',
                    platform='Udemy',
                    url='https://www.udemy.com/course/web-developer-bootcamp/',
                    skills_covered=json.dumps(['HTML', 'CSS', 'JavaScript', 'React'])
                ),
                CourseSuggestion(
                    name='Java Programming Masterclass',
                    platform='Udemy',
                    url='https://www.udemy.com/course/java-the-complete-java-developer-course/',
                    skills_covered=json.dumps(['Java', 'OOP', 'Software Development'])
                )
            ]
            db.session.add_all(courses)
            db.session.commit()
    
    app.run(debug=True)