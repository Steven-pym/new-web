from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField
from wtforms.validators import EqualTo, DataRequired, Email
from flask_wtf.file import FileAllowed

class EditProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Email(), DataRequired()])
    contact = StringField('Contact', validators=[DataRequired()])  # Contact field
    department = StringField('Department', validators=[DataRequired()])
    role = StringField('Role', validators=[DataRequired()])
    password = PasswordField('New Password')
    confirm_password = PasswordField('Confirm Password', validators=[EqualTo('password')])
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png'])])
    submit = SubmitField('Save Changes')
