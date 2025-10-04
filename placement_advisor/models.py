"""
Database models for the Placement Advisor application
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    user_type = db.Column(db.String(20))  # 'student' or 'company'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

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
    certifications = db.Column(db.Text)  # JSON string of certifications
    experience = db.Column(db.Text)  # JSON string of work experience
    resume_path = db.Column(db.String(300))
    photo_path = db.Column(db.String(300))
    location = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    linkedin_url = db.Column(db.String(300))
    github_url = db.Column(db.String(300))
    portfolio_url = db.Column(db.String(300))
    bio = db.Column(db.Text)
    profile_views = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('student_profile', uselist=False))


class CompanyProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    required_skills = db.Column(db.Text)  # JSON string
    min_cgpa = db.Column(db.Float)
    required_courses = db.Column(db.Text)  # JSON string
    location = db.Column(db.String(200))
    company_size = db.Column(db.String(50))  # e.g., "1-50", "51-200", "201-500", etc.
    industry = db.Column(db.String(100))
    website_url = db.Column(db.String(300))
    logo_path = db.Column(db.String(300))
    rating = db.Column(db.Float, default=0.0)
    total_reviews = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('company_profile', uselist=False))


class CourseSuggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    platform = db.Column(db.String(100))  # Coursera, Udemy, etc.
    url = db.Column(db.String(300))
    skills_covered = db.Column(db.Text)  # JSON string
    duration = db.Column(db.String(50))
    difficulty = db.Column(db.String(50))  # Beginner, Intermediate, Advanced
    rating = db.Column(db.Float)


class CompanyPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_profile.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    domain = db.Column(db.String(150))
    description = db.Column(db.Text)
    required_skills = db.Column(db.Text)  # JSON list
    required_courses = db.Column(db.Text)  # JSON list
    min_cgpa = db.Column(db.Float)
    location = db.Column(db.String(200))
    job_type = db.Column(db.String(50))  # Full-time, Part-time, Internship, Contract
    salary_range = db.Column(db.String(100))
    experience_required = db.Column(db.String(100))
    deadline = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')  # active, closed, draft
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship('CompanyProfile', backref=db.backref('positions', lazy=True))


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('company_position.id'), nullable=False)
    status = db.Column(db.String(50), default='submitted')  # submitted, under_review, shortlisted, interview_scheduled, rejected, accepted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    match_percentage = db.Column(db.Float)
    matched_skills = db.Column(db.Text)  # JSON list
    missing_skills = db.Column(db.Text)  # JSON list
    cover_letter = db.Column(db.Text)
    notes = db.Column(db.Text)  # Company notes about the candidate

    student = db.relationship('StudentProfile', backref=db.backref('applications', lazy=True))
    position = db.relationship('CompanyPosition', backref=db.backref('applications', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'position_id', name='uq_student_position'),
    )


class Notification(db.Model):
    """Notifications for users about application status changes, new matches, etc."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50))  # application_update, new_match, interview_scheduled, message_received
    related_id = db.Column(db.Integer)  # ID of related object (application, message, etc.)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('notifications', lazy=True))


class Message(db.Model):
    """Direct messages between students and companies"""
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'))  # Optional: link to specific application
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('sent_messages', lazy=True))
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref=db.backref('received_messages', lazy=True))
    application = db.relationship('Application', backref=db.backref('messages', lazy=True))


class Interview(db.Model):
    """Interview scheduling for applications"""
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    location = db.Column(db.String(300))  # Physical address or video call link
    type = db.Column(db.String(50))  # video, phone, in_person
    status = db.Column(db.String(50), default='scheduled')  # scheduled, completed, cancelled, rescheduled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = db.relationship('Application', backref=db.backref('interviews', lazy=True))


class CompanyReview(db.Model):
    """Student reviews and ratings for companies"""
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_profile.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'), nullable=False)
    rating = db.Column(db.Float, nullable=False)  # 1-5 stars
    review_text = db.Column(db.Text)
    work_culture_rating = db.Column(db.Float)
    growth_opportunities_rating = db.Column(db.Float)
    work_life_balance_rating = db.Column(db.Float)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)  # Verified if student actually worked there
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship('CompanyProfile', backref=db.backref('reviews', lazy=True))
    student = db.relationship('StudentProfile', backref=db.backref('reviews', lazy=True))


class Analytics(db.Model):
    """Track analytics for students and companies"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    metric_type = db.Column(db.String(100))  # profile_view, application_sent, message_sent, etc.
    value = db.Column(db.Float)
    metadata = db.Column(db.Text)  # JSON string for additional data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('analytics', lazy=True))


class SavedJob(db.Model):
    """Jobs saved/bookmarked by students"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.id'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('company_position.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('StudentProfile', backref=db.backref('saved_jobs', lazy=True))
    position = db.relationship('CompanyPosition', backref=db.backref('saved_by', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'position_id', name='uq_saved_job'),
    )
