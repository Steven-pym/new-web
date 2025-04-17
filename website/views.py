from flask import Blueprint, flash, render_template, redirect, request, url_for, send_file, session, current_app, send_from_directory, Response, abort
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from .models import User, WorkSession, AuditLog, CompanySettings, Company
from datetime import datetime, timedelta, date, time
from . import db
import pandas as pd
import io
from .forms import EditProfileForm, CompanySettingsForm, CompanyRegistrationForm
from .decorators import admin_required
from collections import defaultdict
import os, uuid
from sqlalchemy import func, distinct
import calendar
import csv
from openpyxl import Workbook

# Define allowed_file function to validate file extensions
def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template("home.html", user=current_user)

@views.route('/dashboard')
@login_required
def dashboard():
    """Displays the dashboard with active and archived sessions"""
    today = date.today()
    current_time = datetime.now().time()
    current_month = today.month
    current_year = today.year

    # Get today's active session
    active_session = WorkSession.query.filter(
        WorkSession.user_id == current_user.id,
        WorkSession.sign_in_time >= datetime(today.year, today.month, today.day, 0, 0, 0),
        WorkSession.sign_out_time.is_(None),
        WorkSession.archived.is_(False)
    ).first()

    # Get archived sessions
    archived_sessions = WorkSession.query.filter(
        WorkSession.user_id == current_user.id,
        WorkSession.archived.is_(True)
    ).all()

    # Group archived sessions by week
    grouped_sessions = defaultdict(list)
    for session in archived_sessions:
        start_of_week = session.sign_out_time - timedelta(days=session.sign_out_time.weekday())
        week_str = start_of_week.strftime('%Y-%U')
        grouped_sessions[week_str].append(session)

    # Monthly attendance metrics
    days_attended = db.session.query(
        func.count(distinct(func.date(WorkSession.sign_in_time)))
    ).filter(
        WorkSession.user_id == current_user.id,
        func.extract('month', WorkSession.sign_in_time) == current_month,
        func.extract('year', WorkSession.sign_in_time) == current_year,
        WorkSession.sign_out_time.isnot(None)
    ).scalar() or 0

    total_days = calendar.monthrange(current_year, current_month)[1]
    working_days = sum(1 for day in range(1, total_days + 1) 
                   if datetime(current_year, current_month, day).weekday() < 5)
    
    monthly_attendance = round((days_attended / working_days) * 100) if working_days > 0 else 0

    # Daily progress calculation (7:30 AM to 4:30 PM)
    workday_start = time(7, 30)  # 7:30 AM
    workday_end = time(16, 30)   # 4:30 PM
    daily_progress = 0
    
    if active_session:
        # Calculate based on session time
        time_elapsed = (datetime.now() - active_session.sign_in_time).total_seconds()
        total_work_seconds = (datetime.combine(today, workday_end) - 
                            datetime.combine(today, workday_start)).total_seconds()
        daily_progress = min(round((time_elapsed / total_work_seconds) * 100), 100)
    elif current_time < workday_start:
        daily_progress = 0
    elif current_time >= workday_end:
        daily_progress = 100
    else:
        # During work hours but no active session
        time_elapsed = (datetime.now() - datetime.combine(today, workday_start)).total_seconds()
        total_work_seconds = (datetime.combine(today, workday_end) - 
                            datetime.combine(today, workday_start)).total_seconds()
        daily_progress = min(round((time_elapsed / total_work_seconds) * 100), 100)

    return render_template(
        'dashboard.html', 
        active_session=active_session,
        archived_sessions=archived_sessions,
        grouped_sessions=grouped_sessions,
        days_attended=days_attended,
        working_days=working_days,
        monthly_attendance=monthly_attendance,
        daily_progress=daily_progress,
        workday_start=workday_start.strftime("%I:%M %p"),
        current_time=current_time.strftime("%I:%M %p"),
        workday_end=workday_end.strftime("%I:%M %p"),
        today=today.strftime("%A, %B %d, %Y")
    )

@views.route('/sign-in', methods=['GET', 'POST'])
@login_required
def sign_in():
    """Allows a user to sign in but ensures only one session per day"""
    
    # Check if user already signed in today
    today = date.today()
    existing_session = WorkSession.query.filter(
        WorkSession.user_id == current_user.id,
        WorkSession.sign_in_time >= datetime(today.year, today.month, today.day)
    ).first()

    if existing_session:
        flash('You have already signed in today!', 'warning')
    else:
        new_work_session = WorkSession(user_id=current_user.id)
        db.session.add(new_work_session)
        db.session.commit()
        flash('Signed in for work successfully!', 'success')

    return redirect(url_for('views.dashboard'))

@views.route('/lunch-out/<int:session_id>', methods=['POST'])
@login_required
def lunch_out(session_id):
    work_session = WorkSession.query.get_or_404(session_id)
    if work_session.user_id == current_user.id and not work_session.lunch_out_time:
        work_session.lunch_out_time = datetime.utcnow()
        db.session.commit()
        flash('Signed out for lunch successfully!', 'success')
    return redirect(url_for('views.dashboard'))  

@views.route('/lunch-in/<int:session_id>', methods=['POST'])
@login_required
def lunch_in(session_id):
    work_session = WorkSession.query.get_or_404(session_id)
    if work_session.user_id == current_user.id and work_session.lunch_out_time and not work_session.lunch_in_time:
        work_session.lunch_in_time = datetime.utcnow()
        db.session.commit()
        flash('Signed back in from lunch successfully!', 'success')
    return redirect(url_for('views.dashboard')) 

@views.route('/sign-out', methods=['POST'])
@login_required
def sign_out():
    """Signs out the user and archives the session for the day"""

    today = date.today()
    work_session = WorkSession.query.filter(
        WorkSession.user_id == current_user.id,
        WorkSession.sign_in_time >= datetime(today.year, today.month, today.day),
        WorkSession.sign_out_time.is_(None)  # Ensure they haven’t already signed out
    ).first()

    if work_session:
        work_session.sign_out_time = datetime.utcnow()
        work_session.archived = True  # Archive the session after sign-out
        db.session.commit()
        flash('Signed out successfully! Your session has been archived.', 'success')
    else:
        flash('No active session found to sign out!', 'warning')

    return redirect(url_for('views.dashboard'))

@views.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        report_format = request.form.get('format')

        if not start_date or not end_date:
            return "Please provide both start and end dates.", 400

        # Convert dates to datetime objects
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return "Invalid date format. Please use YYYY-MM-DD.", 400

        # Filter work sessions by date range
        query = WorkSession.query.filter(
            WorkSession.sign_in_time >= start_date,
            WorkSession.sign_in_time <= end_date
        )

        if current_user.role != 'admin':
            query = query.filter(WorkSession.user_id == current_user.id)

        sessions = query.all()

        # Check if any sessions exist
        if not sessions:
            return "No work sessions found for the selected date range.", 400

        # Create a DataFrame from the filtered sessions
        data = []
        for session in sessions:
            employee_name = session.user.first_name if session.user else "Unknown"
            data.append({
                'Employee': employee_name,
                'Sign In Time': session.sign_in_time,
                'Lunch Out Time': session.lunch_out_time or "N/A",
                'Lunch In Time': session.lunch_in_time or "N/A",
                'Sign Out Time': session.sign_out_time or "N/A"
            })
        
        df = pd.DataFrame(data)

        # Generate the report
        if report_format == 'csv':
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name='work_sessions_report.csv'
            )

        elif report_format == 'excel':
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Work Sessions')
            output.seek(0)
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='work_sessions_report.xlsx'
            )

    return render_template('reports.html', user=current_user)

@views.route('/archived-sessions')
@login_required
def archived_sessions():
    """Displays archived work sessions or downloads them as a file."""
    # Get the date range from the query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Fetch archived sessions for the current user
    query = WorkSession.query.filter(
        WorkSession.user_id == current_user.id,
        WorkSession.archived.is_(True)
    )

    # Apply date range filter if provided
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(WorkSession.sign_in_time >= start_date)
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(WorkSession.sign_in_time <= end_date)

    archived_sessions = query.all()

    # Check if the user wants to download the report
    download = request.args.get('download')
    if download:
        # Get the selected format from the query parameter
        report_format = request.args.get('format', 'csv')  # Default to CSV

        # Include the user's name in the file name
        user_name = current_user.first_name.replace(" ", "_")
        file_name = f"archived_sessions_{user_name}.{report_format}"

        if report_format == 'csv':
            # Create a CSV file
            output = io.StringIO()
            writer = csv.writer(output)
            # Write headers
            writer.writerow(['User Name', 'Session ID', 'Sign In Date', 'Sign In Time', 'Lunch Out Date', 'Lunch Out Time', 'Lunch In Date', 'Lunch In Time', 'Sign Out Date', 'Sign Out Time'])
            # Write data
            for session in archived_sessions:
                writer.writerow([
                    current_user.first_name,
                    session.id,
                    session.sign_in_time.strftime('%Y-%m-%d') if session.sign_in_time else 'N/A',
                    session.sign_in_time.strftime('%H:%M:%S') if session.sign_in_time else 'N/A',
                    session.lunch_out_time.strftime('%Y-%m-%d') if session.lunch_out_time else 'N/A',
                    session.lunch_out_time.strftime('%H:%M:%S') if session.lunch_out_time else 'N/A',
                    session.lunch_in_time.strftime('%Y-%m-%d') if session.lunch_in_time else 'N/A',
                    session.lunch_in_time.strftime('%H:%M:%S') if session.lunch_in_time else 'N/A',
                    session.sign_out_time.strftime('%Y-%m-%d') if session.sign_out_time else 'N/A',
                    session.sign_out_time.strftime('%H:%M:%S') if session.sign_out_time else 'N/A'
                ])
            output.seek(0)

            # Return the CSV file as a downloadable response
            return Response(
                output,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={file_name}'}
            )

        elif report_format == 'excel':
            # Create an Excel file
            wb = Workbook()
            ws = wb.active
            ws.title = "Archived Sessions"
            # Write headers
            ws.append(['User Name', 'Session ID', 'Sign In Date', 'Sign In Time', 'Lunch Out Date', 'Lunch Out Time', 'Lunch In Date', 'Lunch In Time', 'Sign Out Date', 'Sign Out Time'])
            # Write data
            for session in archived_sessions:
                ws.append([
                    current_user.first_name,
                    session.id,
                    session.sign_in_time.strftime('%Y-%m-%d') if session.sign_in_time else 'N/A',
                    session.sign_in_time.strftime('%H:%M:%S') if session.sign_in_time else 'N/A',
                    session.lunch_out_time.strftime('%Y-%m-%d') if session.lunch_out_time else 'N/A',
                    session.lunch_out_time.strftime('%H:%M:%S') if session.lunch_out_time else 'N/A',
                    session.lunch_in_time.strftime('%Y-%m-%d') if session.lunch_in_time else 'N/A',
                    session.lunch_in_time.strftime('%H:%M:%S') if session.lunch_in_time else 'N/A',
                    session.sign_out_time.strftime('%Y-%m-%d') if session.sign_out_time else 'N/A',
                    session.sign_out_time.strftime('%H:%M:%S') if session.sign_out_time else 'N/A'
                ])

            # Save the Excel file to a BytesIO object
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)

            # Return the Excel file as a downloadable response
            return Response(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': f'attachment; filename={file_name}'}
            )

        # If the format is invalid, return an error
        return "Invalid format selected.", 400

    # Render the template for viewing archived sessions
    return render_template('archived_sessions.html', archived_sessions=archived_sessions)

@views.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    employees = User.query.filter_by(role='employee').all()
    work_sessions = WorkSession.query.all()
    session['user_id'] = current_user.first_name  # Store first_name instead of username
    return render_template('admin_dashboard.html', employees=employees, work_sessions=work_sessions, user=current_user)

@views.route('/session/<int:session_id>')
@login_required
@admin_required
def view_session(session_id):
    session = WorkSession.query.get_or_404(session_id)
    return render_template('view_session.html', session=session)

@views.route('/edit_session/<int:session_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_session(session_id):
    # Retrieve the session from the database using the session_id
    session = WorkSession.query.get_or_404(session_id)

    if request.method == 'POST':
        # Get the updated data from the form
        session_name = request.form.get('session_name')
        session_description = request.form.get('session_description')
        
        # Validate the data (you can add more validation as needed)
        if not session_name or not session_description:
            flash('All fields are required!', 'danger')
            return redirect(url_for('views.edit_session', session_id=session.id))

        # Update the session object with new data
        session.session_name = session_name
        session.session_description = session_description
        
        # Commit the changes to the database
        db.session.commit()

        # Flash a success message and redirect to the session view page
        flash('Session updated successfully!', 'success')
        return redirect(url_for('views.view_session', session_id=session.id))

    # If the request method is GET, render the edit form with the current session data
    return render_template('edit_session.html', session=session)

@views.route('/admin/audit-logs', methods=['GET'])
@login_required
@admin_required
def audit_logs():
    # Fetch all audit logs ordered by timestamp (most recent first)
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template('audit_logs.html', logs=logs)

@views.route('/admin/toggle_user_status/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active  # Toggle the user's active status
    db.session.commit()
    return redirect(url_for('views.manage_users'))  # Redirect back to the manage users page


@views.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_employee(user_id):
    user = User.query.get_or_404(user_id)
    # Fetch the user data from the database using the provided user_id
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        # Get data from the form
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        department = request.form.get('department')
        role = request.form.get('role')
        
        # Optionally handle profile picture upload
        if 'profile_picture' in request.files:
            profile_picture = request.files['profile_picture']
            if profile_picture:
                filename = secure_filename(profile_picture.filename)
                profile_picture.save(os.path.join('static/uploads', filename))
                user.profile_picture = filename
        
        # Update the user's fields with the new data
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.department = department
        user.role = role
        
        # Commit the changes to the database
        db.session.commit()

        flash('User details updated successfully!', 'success')
        return redirect(url_for('views.manage_users'))

    return render_template('edit_user.html', user=user)

# Add Employee
@views.route('/admin/add-employee', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the username already exists
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists', 'error')
        else:
            # Create a new employee
            new_user = User(username=username, role='employee')
            new_user.set_password(password)  # Hash the password
            db.session.add(new_user)
            db.session.commit()
            flash('Employee added successfully!', 'success')
            return redirect(url_for('views.admin_dashboard'))

    return render_template('add_employee.html')


# Remove Employee
@views.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
@admin_required
def delete_session(session_id):
    # Logic for deleting a session
    session = WorkSession.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    flash('Session deleted successfully!', 'success')
    return redirect(url_for('views.admin_dashboard'))

# View Work Session Logs
@views.route('/admin/work-sessions')
@login_required
@admin_required
def view_work_sessions():
    work_sessions = WorkSession.query.all()

    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Get sessions only from this week
    weekly_sessions = WorkSession.query.filter(
        WorkSession.sign_in_time >= start_of_week,
        WorkSession.sign_in_time <= end_of_week
    ).all()

    # Total work hours this week
    total_seconds = 0
    for session in weekly_sessions:
        duration = session.get_duration()
        if duration:
            total_seconds += duration.total_seconds()
    total_hours = round(total_seconds / 3600, 2)

    # Most active employees (by number of sessions this week)
    most_active = db.session.query(
        User.first_name, User.email, func.count(WorkSession.id).label("session_count")
    ).join(WorkSession).filter(
        WorkSession.sign_in_time >= start_of_week,
        WorkSession.sign_in_time <= end_of_week
    ).group_by(User.id).order_by(func.count(WorkSession.id).desc()).limit(5).all()

    # Late logins (after 9:05 AM this week)
    late_threshold = datetime.strptime("09:05", "%H:%M").time()
    late_logins = db.session.query(WorkSession).filter(
        func.time(WorkSession.sign_in_time) > late_threshold,
        WorkSession.sign_in_time >= start_of_week,
        WorkSession.sign_in_time <= end_of_week
    ).count()

    # Prepare data for charts
    daily_hours_data = [session.get_duration().total_seconds() / 3600 if session.get_duration() else 0 for session in weekly_sessions]
    daily_hours_labels = [session.sign_in_time.strftime('%Y-%m-%d') for session in weekly_sessions]

    top_employees_data = [user.session_count for user in most_active]
    top_employees_labels = [f"{user.first_name} ({user.session_count} sessions)" for user in most_active]

    return render_template(
        'work_sessions.html',
        work_sessions=work_sessions,
        total_hours=total_hours,
        most_active=most_active,
        late_logins=late_logins,
        daily_hours_data=daily_hours_data,
        daily_hours_labels=daily_hours_labels,
        top_employees_data=top_employees_data,
        top_employees_labels=top_employees_labels
    )

@views.route('/about')
def about():
    return render_template('about.html')

@views.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        # Here, you can process the form data, such as sending an email or saving it to the database
        print(f"Message received from {name} ({email}): {message}")

        # Optionally, display a success message or redirect to another page
        return render_template('contact.html', success=True)

    # Handle GET request (initial form rendering)
    return render_template('contact.html')

@views.route('/privacy')
def privacy():
    return render_template('privacy.html')


@views.route('/attendance')
@login_required
def attendance():
    """Display the logged-in user's attendance history with dynamic charts."""
    user = current_user

    # Fetch all work sessions for the user, ordered by sign-in time
    sessions = WorkSession.query.filter_by(user_id=user.id).order_by(WorkSession.sign_in_time.desc()).all()

    # Get the current date and time
    current_date = datetime.utcnow()

    # Initialize data structures
    daily_data = {"labels": [], "data": []}
    weekly_data = {"labels": [], "data": []}
    monthly_data = {"labels": [], "data": []}
    
    # For calculating average hours and most active day
    total_hours = 0
    valid_sessions_count = 0
    day_counts = {}

    # Helper function to calculate hours worked
    def calculate_hours(session):
        if session.sign_in_time and session.sign_out_time:
            return (session.sign_out_time - session.sign_in_time).total_seconds() / 3600
        return 0

    # Process each session
    for session in sessions:
        date = session.sign_in_time.date()
        
        # Count sessions per day
        day_counts[date] = day_counts.get(date, 0) + 1
        
        # Calculate hours for valid sessions
        hours = calculate_hours(session)
        if hours > 0:
            total_hours += hours
            valid_sessions_count += 1

        # Populate daily data (today)
        if date == current_date.date():
            daily_data["labels"].append(date.strftime("%Y-%m-%d"))
            daily_data["data"].append(day_counts[date])

        # Populate weekly data (this week)
        start_of_week = current_date - timedelta(days=current_date.weekday())
        if date >= start_of_week.date():
            weekly_data["labels"].append(date.strftime("%Y-%m-%d"))
            weekly_data["data"].append(day_counts[date])

        # Populate monthly data (this month)
        start_of_month = current_date.replace(day=1)
        if date >= start_of_month.date():
            monthly_data["labels"].append(date.strftime("%Y-%m-%d"))
            monthly_data["data"].append(day_counts[date])

    # Calculate average hours (handle division by zero)
    average_hours = total_hours / valid_sessions_count if valid_sessions_count > 0 else 0

    # Find most active day
    most_active_day = max(day_counts.items(), key=lambda x: x[1])[0].strftime("%A") if day_counts else "N/A"

    # Remove duplicate dates from the data (since we're appending each time we see a date)
    def deduplicate_data(data):
        unique_data = {}
        for label, value in zip(data["labels"], data["data"]):
            unique_data[label] = value
        return {
            "labels": list(unique_data.keys()),
            "data": list(unique_data.values())
        }

    daily_data = deduplicate_data(daily_data)
    weekly_data = deduplicate_data(weekly_data)
    monthly_data = deduplicate_data(monthly_data)

    # Sort data by date (newest first)
    def sort_data(data):
        combined = sorted(zip(data["labels"], data["data"]), reverse=True)
        if combined:
            data["labels"], data["data"] = zip(*combined)
            data["labels"] = list(data["labels"])
            data["data"] = list(data["data"])
        return data

    daily_data = sort_data(daily_data)
    weekly_data = sort_data(weekly_data)
    monthly_data = sort_data(monthly_data)

    return render_template(
        'attendance.html', 
        user=user, 
        sessions=sessions,
        daily_data=daily_data,
        weekly_data=weekly_data,
        monthly_data=monthly_data,
        average_hours=average_hours,
        most_active_day=most_active_day,
        total_hours=total_hours
    )

@views.route('/manage-users')
@login_required
@admin_required
def manage_users():
    """Display a management interface for all system users"""
    # Get all users sorted by their status (active first) and then by name
    users = User.query.order_by(
        User.is_active.desc(),
        User.first_name.asc()
    ).all()
    
    # Count active/inactive users for stats
    active_count = sum(1 for user in users if user.is_active)
    inactive_count = len(users) - active_count
    
    return render_template(
        'manage_users.html',
        users=users,
        active_count=active_count,
        inactive_count=inactive_count,
        current_time=datetime.utcnow()
    )

@views.route('/terms')
def terms():
    return render_template('terms.html')


@views.route("/upload_profile", methods=["POST"])
@login_required
def upload_profile():
    if "file" not in request.files:
        flash("No file selected", "error")
        return redirect(request.referrer or url_for("views.dashboard"))

    file = request.files["file"]

    if file.filename == "":
        flash("No file selected", "error")
        return redirect(request.referrer or url_for("views.dashboard"))

    if not allowed_file(file.filename):
        flash("Invalid file type. Only PNG, JPG, JPEG, and GIF allowed.", "error")
        return redirect(request.referrer or url_for("views.dashboard"))

    try:
        # Check file size without saving
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        if file_size > 2 * 1024 * 1024:  # 2MB limit
            flash("File too large (max 2MB)", "error")
            return redirect(request.referrer or url_for("views.dashboard"))

        # Ensure upload folder exists
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_folder, exist_ok=True)

        # Generate secure filename
        ext = os.path.splitext(file.filename)[1].lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(upload_folder, filename)

        # Save the file
        file.save(filepath)

        # Delete old profile picture if exists
        if current_user.profile_picture:
            old_filepath = os.path.join(upload_folder, current_user.profile_picture)
            try:
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
            except Exception as e:
                current_app.logger.error(f"Error deleting old profile picture: {str(e)}")

        # Update database
        current_user.profile_picture = filename
        db.session.commit()

        flash("Profile picture updated successfully!", "success")
    except Exception as e:
        current_app.logger.error(f"Error uploading profile picture: {str(e)}")
        flash("Error updating profile picture", "error")
        db.session.rollback()

    return redirect(request.referrer or url_for("views.dashboard"))


@views.route('/uploads/<filename>')
@login_required  # Ensure the user is logged in
def uploaded_file(filename):
    # Only allow the user to access their own profile picture
    if current_user.profile_picture != filename:
        abort(403)  # Forbidden, the user cannot access this file

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

# views.py
@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    profile_form = EditProfileForm()
    company_form = CompanySettingsForm()
    
    # Load company settings if they exist
    company_settings = CompanySettings.query.filter_by(
        company_id=current_user.company_id
    ).first()
    
    if request.method == 'POST':
        # Handle profile picture deletion
        if 'delete_picture' in request.form:
            if current_user.profile_picture:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.profile_picture))
                    current_user.profile_picture = None
                    db.session.commit()
                    flash('Profile picture deleted!', 'success')
                except Exception as e:
                    flash('Error deleting picture', 'danger')
            return redirect(url_for('views.settings'))
        
        # Handle profile update
        if profile_form.validate_on_submit():
            current_user.first_name = profile_form.first_name.data
            current_user.email = profile_form.email.data
            current_user.contact = profile_form.contact.data
            current_user.department = profile_form.department.data
            current_user.role = profile_form.role.data
            
            if profile_form.password.data:
                current_user.set_password(profile_form.password.data)
            
            if profile_form.profile_picture.data:
                filename = secure_filename(profile_form.profile_picture.data.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                profile_form.profile_picture.data.save(filepath)
                current_user.profile_picture = filename
            
            db.session.commit()
            flash('Profile updated!', 'success')
            return redirect(url_for('views.settings'))
        
        # Handle company settings update
        if company_form.validate_on_submit():
            if not company_settings:
                company_settings = CompanySettings(company_id=current_user.company_id)
            
            try:
                # Convert string times to time objects
                start_h, start_m = map(int, company_form.work_start_time.data.split(':'))
                end_h, end_m = map(int, company_form.work_end_time.data.split(':'))
                
                company_settings.work_start_time = time(start_h, start_m)
                company_settings.work_end_time = time(end_h, end_m)
                company_settings.lunch_duration = company_form.lunch_duration.data
                company_settings.work_days = ','.join(company_form.work_days.data)
                
                # Handle logo upload
                if company_form.logo.data:
                    filename = secure_filename(company_form.logo.data.filename)
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    company_form.logo.data.save(filepath)
                    company_settings.logo = filename

                db.session.add(company_settings)
                db.session.commit()
                flash('Company settings updated!', 'success')
            except ValueError:
                flash('Invalid time format. Use HH:MM', 'danger')
            
            return redirect(url_for('views.settings'))
    
    # Pre-fill forms
    profile_form.first_name.data = current_user.first_name
    profile_form.email.data = current_user.email
    profile_form.contact.data = current_user.contact
    profile_form.department.data = current_user.department
    profile_form.role.data = current_user.role
    
    if company_settings:
        company_form.work_start_time.data = company_settings.work_start_time.strftime('%H:%M')
        company_form.work_end_time.data = company_settings.work_end_time.strftime('%H:%M')
        company_form.lunch_duration.data = company_settings.lunch_duration
        company_form.work_days.data = company_settings.work_days.split(',')
        company_form.logo.data = company_settings.logo  # Assign logo to form if exists
    
    return render_template('settings.html', form=profile_form, company_form=company_form, current_company=company_settings)

@views.route('/chat')
def chat():
    return render_template('chat.html')

@views.route('/register_company', methods=['GET', 'POST'])
@login_required
def register_company():
    # Check if user already has a company
    if current_user.company:
        flash('You are already associated with a company.', 'info')
        return redirect(url_for('views.dashboard'))

    form = CompanyRegistrationForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Check if company with this registration number already exists
                existing_company = Company.query.filter_by(
                    registration_number=form.registration_number.data
                ).first()
                
                if existing_company:
                    flash('A company with this registration number already exists.', 'danger')
                    return render_template('admin_dashboard.html', form=form)

                # Create new company
                company = Company(
                    name=form.name.data,
                    registration_number=form.registration_number.data,
                    contact_email=form.contact_email.data,
                    phone=form.phone.data,
                    address=form.address.data,
                    created_by=current_user.id
                )
                
                db.session.add(company)
                db.session.commit()

                # Associate user with company
                current_user.company_id = company.id
                current_user.role = 'company_admin'  # Optional: set user role
                db.session.commit()

                flash('Company registered successfully!', 'success')
                return redirect(url_for('views.company_dashboard'))

            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred while registering your company: {str(e)}', 'danger')
                return render_template('admin_dashboard.html', form=form)

        else:
            # Form validation failed
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{getattr(form, field).label.text}: {error}")
            
            flash('Please correct the following errors:', 'danger')
            for message in error_messages:
                flash(message, 'danger')

    # For GET requests or when form validation fails
    return render_template('admin_dashboard.html', form=form)


@views.route('/manage_companies', methods=['GET', 'POST'])
@login_required
def manage_company():
    form = CompanySettingsForm()

    if request.method == 'POST' and form.validate_on_submit():
        # Update the company settings
        company = Company.query.get(current_user.company_id)
        if company:
            company.name = form.company_name.data
            company.contact_email = form.company_contact.data
            company.address = form.company_address.data
            company.phone = form.company_phone.data

            db.session.commit()
            flash('Company settings updated successfully!', 'success')
            return redirect(url_for('views.dashboard'))
        else:
            flash('Company not found!', 'danger')
    elif request.method == 'POST':
        flash('There were errors with your update. Please check the form.', 'danger')   

        return render_template('manage_companies.html', form=form)
    
@views.route('/views.manage_companies', methods=['GET', 'POST'])
@login_required
def manage_companies():
    form = CompanySettingsForm()

    if request.method == 'POST' and form.validate_on_submit():
        # Update the company settings
        company = Company.query.get(current_user.company_id)
        if company:
            company.name = form.company_name.data
            company.contact_email = form.company_contact.data
            company.address = form.company_address.data
            company.phone = form.company_phone.data

            db.session.commit()
            flash('Company settings updated successfully!', 'success')
            return redirect(url_for('views.dashboard'))
        else:
            flash('Company not found!', 'danger')
    elif request.method == 'POST':
        flash('There were errors with your update. Please check the form.', 'danger')   

    return render_template('manage_companies.html', form=form)

@views.route('/company_dasboard', methods=['GET', 'POST'])
@login_required
def company_dashboard():
    form = CompanySettingsForm()

    if request.method == 'POST' and form.validate_on_submit():
        # Update the company settings
        company = Company.query.get(current_user.company_id)
        if company:
            company.name = form.company_name.data
            company.contact_email = form.company_contact.data
            company.address = form.company_address.data
            company.phone = form.company_phone.data

            db.session.commit()
            flash('Company settings updated successfully!', 'success')
            return redirect(url_for('views.dashboard'))
        else:
            flash('Company not found!', 'danger')
    elif request.method == 'POST':
        flash('There were errors with your update. Please check the form.', 'danger')   

    return render_template('company_dashboard.html', form=form)

@views.route('/company_employees', methods=['GET', 'POST'])
@login_required
def company_employees():
    form = CompanySettingsForm()

    if request.method == 'POST' and form.validate_on_submit():
        # Update the company settings
        company = Company.query.get(current_user.company_id)
        if company:
            company.name = form.company_name.data
            company.contact_email = form.company_contact.data
            company.address = form.company_address.data
            company.phone = form.company_phone.data

            db.session.commit()
            flash('Company settings updated successfully!', 'success')
            return redirect(url_for('views.dashboard'))
        else:
            flash('Company not found!', 'danger')
    elif request.method == 'POST':
        flash('There were errors with your update. Please check the form.', 'danger')   

    return render_template('company_employees.html', form=form)

