from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint
from . import db  
import secrets

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) 
    first_name = db.Column(db.String(150), nullable=True)
    last_name = db.Column(db.String(150), nullable=True)
    contact = db.Column(db.String(15), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='employee')
    profile_picture = db.Column(db.String(255), default="default.png")
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    reset_password_token = db.Column(db.String(64), unique=True, nullable=True)
    reset_password_expires = db.Column(db.DateTime, nullable=True)

    work_sessions = db.relationship('WorkSession', backref='user', lazy=True)
    sent_messages = db.relationship('Message', 
                                  foreign_keys='Message.sender_id',
                                  back_populates='sender',
                                  lazy=True)
    received_messages = db.relationship('Message',
                                      foreign_keys='Message.recipient_id',
                                      back_populates='sender',
                                      lazy=True)
    
    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self, expires_in=3600):
        self.reset_password_token = secrets.token_urlsafe(32)
        self.reset_password_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        db.session.commit()

    @staticmethod
    def verify_reset_token(token):
        user = User.query.filter_by(reset_password_token=token).first()
        if user and user.reset_password_expires > datetime.utcnow():
            return user
        return None

    def get_full_name(self):
        names = [n for n in [self.first_name, self.last_name] if n]
        return " ".join(names) if names else "Unknown"

class WorkSession(db.Model):
    __tablename__ = 'work_sessions'  
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sign_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    lunch_out_time = db.Column(db.DateTime, nullable=True)
    lunch_in_time = db.Column(db.DateTime, nullable=True)
    sign_out_time = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    archived = db.Column(db.Boolean, default=False) 

    __table_args__ = (
        UniqueConstraint('user_id', 'sign_in_time', name='_user_daily_session'),
    )

    def __repr__(self):
        return f'<WorkSession {self.user_id} {self.sign_in_time.date()}>'

    def sign_out(self):
        if not self.sign_out_time:
            self.sign_out_time = datetime.utcnow()
            db.session.commit()

    def archive_session(self):
        self.archived = True
        db.session.commit()

    def lunch_out(self):
        if not self.lunch_out_time and not self.sign_out_time:
            self.lunch_out_time = datetime.utcnow()
            db.session.commit()

    def lunch_in(self):
        if self.lunch_out_time and not self.lunch_in_time and not self.sign_out_time:
            self.lunch_in_time = datetime.utcnow()
            db.session.commit()

    def get_duration(self):
        if not self.sign_out_time:
            return None

        total_time = (self.sign_out_time - self.sign_in_time).total_seconds()
        
        if self.lunch_out_time and self.lunch_in_time:
            lunch_duration = (self.lunch_in_time - self.lunch_out_time).total_seconds()
            total_time -= lunch_duration
        
        return timedelta(seconds=total_time)

    def get_lunch_duration(self):
        if self.lunch_out_time and self.lunch_in_time:
            return self.lunch_in_time - self.lunch_out_time
        return None

    def is_active(self):
        return self.sign_out_time is None

    def is_on_lunch(self):
        return self.lunch_out_time is not None and self.lunch_in_time is None

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    # Relationships using back_populates
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_messages')