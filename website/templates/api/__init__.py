import os
from os import path, getenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_socketio import SocketIO
from dotenv import load_dotenv

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
socketio = SocketIO()
DB_NAME = "database.db"

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Secret Key & Database Configuration
    app.config['SECRET_KEY'] = getenv('FLASK_SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    
    db.init_app(app)

    # Email Configuration
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = getenv('MAIL_PASSWORD') 
    mail.init_app(app)

    # Socket.IO Configuration
    app.config['SOCKETIO_MESSAGE_QUEUE'] = getenv('REDIS_URL', None)
    
    # Initialize Socket.IO with the app
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='eventlet'
    )

    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.getcwd(), "website", "static", "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

    # Ensure the upload folder exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    # Import models using absolute path based on your structure
    from website.models import User  # Changed from website.templates.api.models

    # Login Manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)  

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    # Register Blueprints
    from website.views import views  # Added absolute import
    from website.auth import auth    # Added absolute import

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    # Create database tables
    with app.app_context():
        db.create_all()
        print("✅ Database tables created!")

    return app