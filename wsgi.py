# This must be the very first import
import eventlet
eventlet.monkey_patch()

from main import application  # Import the Flask app
from main import socketio    # Import SocketIO instance

if __name__ == '__main__':
    socketio.run(application)