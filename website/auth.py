from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
import re  # Import the re module for regular expressions
from datetime import datetime
from . import db, mail
from .models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message
from twilio.rest import Client  # Import Twilio client

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        
        if user:
            if check_password_hash(user.password_hash, password):
                flash('Logged in successfully!', category='success')
                login_user(user, remember=True)

                # Redirect based on role
                if user.role == 'admin':
                    return redirect(url_for('views.admin_dashboard'))  # Admins go to admin dashboard
                else:
                    return redirect(url_for('views.dashboard'))  # Employees go to home
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Email does not exist.', category='error')

    return render_template('login_sign_up.html', user=current_user)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        # Retrieve and sanitize form data
        email = request.form.get('email', '').strip()
        first_name = request.form.get('firstName', '').strip()
        password1 = request.form.get('password1', '')
        password2 = request.form.get('password2', '')
        role = request.form.get('role', 'worker')  # Default role to worker if not provided
        terms = request.form.get('terms')

        # Validate terms and conditions
        if terms != "on":
            flash('You must agree to the terms and conditions to register.', 'error')
            return render_template('login_sign_up.html', email=email, first_name=first_name, role=role)

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
            return render_template('login_sign_up.html', email=email, first_name=first_name, role=role)

        # Validate inputs
        if len(email) < 4:
            flash('Email must be at least 4 characters long.', 'error')
        elif len(first_name) < 2:
            flash('First name must be at least 2 characters long.', 'error')
        elif password1 != password2:
            flash('Passwords do not match.', 'error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters long.', 'error')
        else:
            # Create new user
            new_user = User(
                email=email,
                first_name=first_name,
                password_hash=generate_password_hash(password1, method='pbkdf2:sha256'),
                role=role
            )
            db.session.add(new_user)
            db.session.commit()

            # Log in user
            login_user(new_user, remember=True)
            flash('Account created successfully!', 'success')

            # Redirect to appropriate dashboard
            return redirect(url_for('views.admin_dashboard' if role == 'admin' else 'views.dashboard'))

        return render_template('login_sign_up.html', email=email, first_name=first_name, role=role)

    return render_template('login_sign_up.html')


@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        contact_info = request.form.get('email_or_phone')

        # Check if input is an email or phone number
        if re.match(r"[^@]+@[^@]+\.[^@]+", contact_info):
            user = User.query.filter_by(email=contact_info).first()
        else:
            user = User.query.filter_by(phone_number=contact_info).first()

        if user:
            # Generate a reset token
            user.generate_reset_token()
            reset_url = url_for('auth.reset_password', token=user.reset_password_token, _external=True)

            if "@" in contact_info:  # If it's an email, send via email
                msg = Message('Password Reset Request',
                              sender='noreply@yourdomain.com',
                              recipients=[user.email])
                msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this message.
'''
                mail.send(msg)
            else:  # If it's a phone number, send via SMS
                twilio_client.messages.create(
                    body=f"Reset your password using this link: {reset_url}",
                    from_=TWILIO_PHONE_NUMBER,
                    to=user.phone_number
                )

            flash('A password reset link has been sent.', 'info')
            return redirect(url_for('auth.login'))

        flash('Email or phone number not found.', 'error')

    return render_template('forgot_password.html')
# Route to reset the password
@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.verify_reset_token(token)

    if not user:
        flash('Invalid or expired token.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        user.set_password(password)
        user.reset_password_token = None  # Clear the reset token
        user.reset_password_expires = None  # Clear the expiration time
        db.session.commit()
        flash('Your password has been reset!', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)

import os

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', 'default_account_sid')  # Replace 'default_account_sid' with a fallback or ensure the environment variable is set
TWILIO_PHONE_NUMBER = '+1234567890'  # Your Twilio phone number

# Initialize Twilio client
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', 'default_auth_token')  # Replace 'default_auth_token' with a fallback or ensure the environment variable is set
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
TWILIO_PHONE_NUMBER=+1234567890  # Your Twilio phone number

@auth.route('/confirm-verification', methods=['POST'])
@login_required
def confirm_verification():
    user = current_user
    code = request.form.get('code')
    
    if (user.sms_verification_code == code and 
        user.sms_verification_code_expires > datetime.utcnow()):
        user.phone_verified = True
        user.sms_verification_code = None
        user.sms_verification_code_expires = None
        db.session.commit()
        return jsonify({'message': 'Phone number verified'}), 200
    
    return jsonify({'error': 'Invalid or expired code'}), 400