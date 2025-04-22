import eventlet
eventlet.monkey_patch()

# Regular imports
import os
from os import path, getenv
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_socketio import SocketIO
from dotenv import load_dotenv
from markupsafe import Markup
import re
import psycopg2  # PostgreSQL connection
from psycopg2 import pool  # For connection pooling

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
socketio = SocketIO()

# Load environment variables
load_dotenv()

def configure_app(app):
    """Configure application settings with PostgreSQL"""
    app.config.update(
        SECRET_KEY=getenv('FLASK_SECRET_KEY', 'dev-secret-key'),
        # PostgreSQL configuration with connection pooling
        SQLALCHEMY_DATABASE_URI=getenv('DATABASE_URL', 'postgresql://user:password@localhost/dbname'),
        SQLALCHEMY_ENGINE_OPTIONS={
            'pool_size': 10,
            'max_overflow': 20,
            'pool_pre_ping': True,
            'pool_recycle': 300,
        },
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # SSL configuration for PostgreSQL (remove if not needed)
        SQLALCHEMY_ENGINE_OPTIONS_SSL={
            'sslmode': 'require',
            'sslrootcert': 'path/to/root-cert.pem',
            'sslcert': 'path/to/client-cert.pem',
            'sslkey': 'path/to/client-key.pem'
        },
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=getenv('MAIL_PASSWORD'),
        SOCKETIO_MESSAGE_QUEUE=getenv('REDIS_URL', None),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'}
    )

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Configuration
    configure_app(app)
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Initialize SocketIO with the app
    socketio.init_app(app)
    
    # Setup the database
    setup_database(app)
    
    # Configure upload folder
    configure_upload_folder(app)
    
    # Register blueprints
    register_blueprints(app)

    # Custom Jinja filter for highlighting text
    def highlight(text, search):
        if not text or not search:
            return text
        pattern = re.escape(search)
        highlighted = re.sub(f'({pattern})', r'<mark>\1</mark>', text, flags=re.IGNORECASE)
        return Markup(highlighted)

    app.jinja_env.filters['highlight'] = highlight
    
    return app, socketio  # Return both objects


def initialize_extensions(app):
    """Initialize Flask extensions"""
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)  # Initialize SocketIO here

    # Add user loader for login
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User  # Import inside to avoid circular imports
        return User.query.get(int(user_id))
    
def setup_database(app):
    """Initialize the database and create tables"""
    from .models import User, WorkSession, Message  # Import models
    
    with app.app_context():
        db.create_all()  # Creates all tables defined in the models
        print("✅ Initialized Database!")

def configure_upload_folder(app):
    """Ensure the upload folder exists"""
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

def register_blueprints(app):
    """Register Flask blueprints"""
    from .views import views
    from .auth import auth
    from . import events  # Socket.IO events
    
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

def allowed_file(filename):
    """Check if the file extension is allowed for upload"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
