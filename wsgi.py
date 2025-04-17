
import eventlet
eventlet.monkey_patch()

from main import app as application  
from main import socketio          

if __name__ == '__main__':
    socketio.run(application)       