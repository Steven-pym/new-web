from flask import Blueprint, flash, render_template, redirect, request, url_for, send_file, session, current_app, send_from_directory, Response
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from .models import User, WorkSession
from datetime import datetime, timedelta, date
from . import db
import pandas as pd
import io
from .forms import EditProfileForm 
from .decorators import admin_required
from collections import defaultdict
import os, uuid
from sqlalchemy import func
import csv
from openpyxl import Workbook

# Define allowed_file function to validate file extensions
def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

views = Blueprint('views', __name__)

@views.route('/')
@login_required
def home():
    return render_template("home.html", user=current_user)

@views.route('/dashboard')
@login_required
def dashboard():
    """Displays the dashboard with active and archived sessions"""
    today = date.today()

    # Get today's active session (session that has not been signed out yet)
    active_session = WorkSession.query.filter(
        WorkSession.user_id == current_user.id,
        WorkSession.sign_in_time >= datetime(today.year, today.month, today.day),
        WorkSession.sign_out_time.is_(None),  # Session that is not signed out yet
        WorkSession.archived.is_(False)  # Only show unarchived (active) sessions
    ).first()

    # Get archived sessions (past sessions that are archived)
    archived_sessions = WorkSession.query.filter(
        WorkSession.user_id == current_user.id,
        WorkSession.archived.is_(True)  # Show only archived sessions
    ).all()

    # Group archived sessions by week (Monday to Sunday)
    grouped_sessions = defaultdict(list)
    for session in archived_sessions:
        # Get the start of the week (Monday)
        start_of_week = session.sign_out_time - timedelta(days=session.sign_out_time.weekday())  # Monday of the week
        week_str = start_of_week.strftime('%Y-%U')  # Group by year and week number
        grouped_sessions[week_str].append(session)

    # Sort the weeks in descending order (latest week first)
    sorted_weeks = sorted(grouped_sessions.keys(), reverse=True)


    return render_template(
        'dashboard.html', 
        active_session=active_session, 
        archived_sessions=archived_sessions
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
    return render_template('work_sessions.html', work_sessions=work_sessions)


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

    # Calculate daily, weekly, and monthly data
    daily_data = {
        "labels": [],  # Dates for the current day
        "data": []     # Count of sign-ins for each date
    }

    weekly_data = {
        "labels": [],  # Dates for the current week
        "data": []     # Count of sign-ins for each date
    }

    monthly_data = {
        "labels": [],  # Dates for the current month
        "data": []     # Count of sign-ins for each date
    }

    # Helper function to group sessions by date
    def group_sessions_by_date(sessions):
        grouped = {}
        for session in sessions:
            date = session.sign_in_time.date()
            if date in grouped:
                grouped[date] += 1
            else:
                grouped[date] = 1
        return grouped

    # Group sessions by date
    grouped_sessions = group_sessions_by_date(sessions)

    # Populate daily, weekly, and monthly data
    for date, count in grouped_sessions.items():
        # Daily data (today)
        if date == current_date.date():
            daily_data["labels"].append(date.strftime("%Y-%m-%d"))
            daily_data["data"].append(count)

        # Weekly data (this week)
        start_of_week = current_date - timedelta(days=current_date.weekday())  # Start of this week (Monday)
        if date >= start_of_week.date():
            weekly_data["labels"].append(date.strftime("%Y-%m-%d"))
            weekly_data["data"].append(count)

        # Monthly data (this month)
        start_of_month = current_date.replace(day=1)  # First day of the current month
        if date >= start_of_month.date():
            monthly_data["labels"].append(date.strftime("%Y-%m-%d"))
            monthly_data["data"].append(count)

    # Passing the data to the template
    return render_template(
        'attendance.html', 
        user=user, 
        sessions=sessions,
        daily_data=daily_data,
        weekly_data=weekly_data,
        monthly_data=monthly_data
    )

@views.route('/manage-users')
def manage_users():
    return render_template('manage_users.html')

@views.route('/terms')
def terms():
    return render_template('terms.html')


@views.route("/upload_profile", methods=["POST"])
@login_required
def upload_profile():
    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("views.dashboard"))

    file = request.files["file"]

    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("views.dashboard"))

    if file and allowed_file(file.filename):
        # Ensure upload folder exists
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        filepath = os.path.join(upload_folder, filename)

        # Check file size (max 2MB)
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        if file_length > 2 * 1024 * 1024:  # 2MB limit
            flash("File size too large! Max 2MB allowed.", "error")
            return redirect(url_for("views.dashboard"))
        file.seek(0)  # Reset file pointer

        # Save the file
        file.save(filepath)

        # Update user's profile picture in the database
        current_user.profile_picture = filename
        db.session.commit()

        flash("Profile picture updated successfully!", "success")
    else:
        flash("Invalid file format. Only PNG, JPG, JPEG, and GIF allowed.", "error")

    return redirect(url_for("views.dashboard"))


@views.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = EditProfileForm()

    if request.method == 'POST':
        # Handle profile picture deletion
        if 'delete_picture' in request.form:
            if current_user.profile_picture:
                # Delete the file from the uploads folder
                picture_path = os.path.join('website/static/uploads', current_user.profile_picture)
                if os.path.exists(picture_path):
                    os.remove(picture_path)

                # Remove the profile picture reference from the database
                current_user.profile_picture = None
                db.session.commit()
                flash("Profile picture deleted successfully!", "success")
                return redirect(url_for('views.settings'))

        # Handle form submission for other fields
        if form.validate_on_submit():
            # Retrieve values from form
            first_name = form.first_name.data
            email = form.email.data  # Added email
            contact = form.contact.data  # Added contact
            department = form.department.data  # Added department
            role = form.role.data  # Added role
            password = form.password.data
            confirm_password = form.confirm_password.data
            file = form.profile_picture.data

            # Validate password confirmation
            if password and password != confirm_password:
                flash("Passwords do not match!", "danger")
                return redirect(url_for('views.settings'))

            # Update fields if provided
            if first_name:
                current_user.first_name = first_name
            if email:
                current_user.email = email  # Update email
            if contact:
                current_user.contact = contact  # Update contact
            if department:
                current_user.department = department  # Update department
            if role:
                current_user.role = role  # Update role

            # Update password if provided
            if password:
                current_user.set_password(password)

            # Handle profile picture upload
            if file and file.filename:
                filename = secure_filename(file.filename)
                upload_path = os.path.join('website/static/uploads', filename)
                file.save(upload_path)
                current_user.profile_picture = filename

            # Commit changes to the database
            db.session.commit()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('views.settings'))

    # Pre-fill the form with current user data
    form.first_name.data = current_user.first_name
    form.email.data = current_user.email
    form.contact.data = current_user.contact
    form.department.data = current_user.department
    form.role.data = current_user.role

    return render_template('settings.html', form=form, current_user=current_user)

@views.route('/chat')
def chat():
    return render_template('chat.html')
