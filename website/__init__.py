import os
from os import path, getenv
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_socketio import SocketIO
from dotenv import load_dotenv

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
DB_NAME = "database.db"

# Initialize SocketIO separately
socketio = SocketIO(async_mode='eventlet')  # Moved initialization here

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    configure_app(app)
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Setup database
    setup_database(app)
    
    # Configure upload folder
    configure_upload_folder(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Initialize SocketIO with app
    socketio.init_app(
        app,
        cors_allowed_origins="*"
    )
    
    return app, socketio  # Return both objects

def configure_app(app):
    """Configure application settings"""
    app.config.update(
        SECRET_KEY=getenv('FLASK_SECRET_KEY', 'dev-secret-key'),
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{DB_NAME}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=getenv('MAIL_PASSWORD'),
        SOCKETIO_MESSAGE_QUEUE=getenv('REDIS_URL', None),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'}
    )

def initialize_extensions(app):
    """Initialize Flask extensions"""
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    
    # Add user loader
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User  # Import inside to avoid circular imports
        return User.query.get(int(user_id))
    
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='eventlet'
    )

def setup_database(app):
    """Initialize database"""
    from .models import User, WorkSession, Message  # Avoid circular imports
    
    with app.app_context():
        if not path.exists(os.path.join('website', DB_NAME)):
            db.create_all()
            print("✅ Created Database!")

def configure_upload_folder(app):
    """Ensure upload folder exists"""
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
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']