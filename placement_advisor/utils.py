"""
Utility functions for the Placement Advisor application
"""
import json
from datetime import datetime
from models import db, Notification, Analytics


def safe_set_from_json(json_text):
    """Safely convert JSON string to set, return empty set if error"""
    try:
        return set(json.loads(json_text)) if json_text else set()
    except Exception:
        return set()


def safe_list_from_json(json_text):
    """Safely convert JSON string to list, return empty list if error"""
    try:
        return json.loads(json_text) if json_text else []
    except Exception:
        return []


def compute_position_match(student_skills_set, student_courses_set, position):
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


def create_notification(user_id, title, message, notification_type, related_id=None):
    """Create a notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        related_id=related_id
    )
    db.session.add(notification)
    db.session.commit()
    return notification


def track_analytics(user_id, metric_type, value=1, metadata=None):
    """Track analytics for a user"""
    analytics = Analytics(
        user_id=user_id,
        metric_type=metric_type,
        value=value,
        metadata=json.dumps(metadata) if metadata else None
    )
    db.session.add(analytics)
    db.session.commit()
    return analytics


def get_unread_notification_count(user_id):
    """Get count of unread notifications for a user"""
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def get_unread_message_count(user_id):
    """Get count of unread messages for a user"""
    from models import Message
    return Message.query.filter_by(receiver_id=user_id, is_read=False).count()


def get_application_status_display(status):
    """Get human-readable display for application status"""
    status_map = {
        'submitted': {'text': 'Submitted', 'class': 'info', 'icon': 'fa-paper-plane'},
        'under_review': {'text': 'Under Review', 'class': 'primary', 'icon': 'fa-eye'},
        'shortlisted': {'text': 'Shortlisted', 'class': 'warning', 'icon': 'fa-star'},
        'interview_scheduled': {'text': 'Interview Scheduled', 'class': 'success', 'icon': 'fa-calendar-check'},
        'rejected': {'text': 'Rejected', 'class': 'danger', 'icon': 'fa-times-circle'},
        'accepted': {'text': 'Accepted', 'class': 'success', 'icon': 'fa-check-circle'}
    }
    return status_map.get(status, {'text': status, 'class': 'secondary', 'icon': 'fa-info-circle'})


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def validate_file_size(file, max_size_mb=16):
    """Validate file size"""
    file.seek(0, 2)  # Seek to end of file
    size = file.tell()
    file.seek(0)  # Reset file pointer
    max_size_bytes = max_size_mb * 1024 * 1024
    return size <= max_size_bytes


def calculate_profile_completeness(profile, user_type='student'):
    """Calculate how complete a profile is (percentage)"""
    if user_type == 'student':
        fields = [
            profile.name, profile.college, profile.cgpa, profile.skills,
            profile.courses, profile.projects, profile.resume_path,
            profile.photo_path, profile.location, profile.phone,
            profile.linkedin_url, profile.bio
        ]
    else:  # company
        fields = [
            profile.name, profile.description, profile.required_skills,
            profile.required_courses, profile.location, profile.company_size,
            profile.industry, profile.website_url
        ]

    filled = sum(1 for field in fields if field)
    return round((filled / len(fields)) * 100)


def get_skill_recommendations(missing_skills):
    """Get course recommendations based on missing skills"""
    from models import CourseSuggestion
    if not missing_skills:
        return []

    all_courses = CourseSuggestion.query.all()
    recommended = []

    for course in all_courses:
        covered_skills = safe_set_from_json(course.skills_covered)
        if covered_skills.intersection(missing_skills):
            recommended.append({
                'course': course,
                'matching_skills': list(covered_skills.intersection(missing_skills))
            })

    return recommended


def format_date_relative(date):
    """Format date as relative time (e.g., '2 hours ago')"""
    if not date:
        return ''

    now = datetime.utcnow()
    diff = now - date

    seconds = diff.total_seconds()

    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days} day{"s" if days != 1 else ""} ago'
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    elif seconds < 31536000:
        months = int(seconds / 2592000)
        return f'{months} month{"s" if months != 1 else ""} ago'
    else:
        years = int(seconds / 31536000)
        return f'{years} year{"s" if years != 1 else ""} ago'
