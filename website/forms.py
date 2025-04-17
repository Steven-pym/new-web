from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, SelectMultipleField, IntegerField, TextAreaField, EmailField
from wtforms.validators import EqualTo, DataRequired, Email, NumberRange, Optional, Length
from flask_wtf.file import FileAllowed, FileSize

class EditProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Email(), DataRequired()])
    contact = StringField('Contact', validators=[DataRequired()])
    department = StringField('Department', validators=[DataRequired()])
    role = StringField('Role', validators=[DataRequired()])
    password = PasswordField('New Password', validators=[Optional()])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[EqualTo('password', message='Passwords must match'),
                                                 Optional()])
    profile_picture = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Only image files allowed'),
        FileSize(max_size=5 * 1024 * 1024, message='File size must be less than 5MB')
    ])
    submit = SubmitField('Save Changes')

class CompanySettingsForm(FlaskForm):
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=100)])
    company_contact = StringField('Company Contact', validators=[DataRequired(), Length(max=20)])
    company_address = TextAreaField('Company Address', validators=[DataRequired(), Length(max=300)])

    work_start_time = StringField('Work Start Time (HH:MM)',
                                  validators=[DataRequired()],
                                  render_kw={"placeholder": "07:30"})
    work_end_time = StringField('Work End Time (HH:MM)',
                                validators=[DataRequired()],
                                render_kw={"placeholder": "16:30"})
    lunch_duration = IntegerField('Lunch Duration (minutes)',
                                  validators=[
                                      DataRequired(),
                                      NumberRange(min=15, max=120,
                                                  message="Must be between 15-120 minutes")
                                  ],
                                  default=60)
    work_days = SelectMultipleField('Work Days',
                                    choices=[
                                        ('0', 'Sunday'),
                                        ('1', 'Monday'),
                                        ('2', 'Tuesday'),
                                        ('3', 'Wednesday'),
                                        ('4', 'Thursday'),
                                        ('5', 'Friday'),
                                        ('6', 'Saturday')
                                    ],
                                    validators=[DataRequired(message="Select at least one work day")],
                                    default=['1', '2', '3', '4', '5'])  # Default: Mon-Fri
    
    logo = FileField('Company Logo', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Only JPEG or PNG images allowed'),
        FileSize(max_size=5 * 1024 * 1024, message='Max size is 5MB')
    ])

    submit = SubmitField('Save Company Settings')

class CompanyRegistrationForm(FlaskForm):
    name = StringField('Company Name', validators=[DataRequired()])
    registration_number = StringField('Registration Number', validators=[DataRequired()])
    contact_email = EmailField('Contact Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    address = TextAreaField('Address')
    submit = SubmitField('Register Company')

    