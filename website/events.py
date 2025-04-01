from flask_socketio import emit
from flask import request
from datetime import datetime
from . import socketio, db
from .models import Message  # Your message model
from flask_login import current_user

# Store active connections (optional)
active_connections = {}

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        active_connections[request.sid] = current_user.id
        print(f"User {current_user.id} connected")
    else:
        # Handle unauthenticated connections (reject or limit functionality)
        print("Anonymous user connected")

@socketio.on('disconnect')
def handle_disconnect():
    user_id = active_connections.pop(request.sid, None)
    if user_id:
        print(f"User {user_id} disconnected")

@socketio.on('send_message')
def handle_send_message(data):
    if not current_user.is_authenticated:
        return emit('error', {'message': 'Authentication required'})
    
    # Create and save message to database
    message = Message(
        content=data['content'],
        user_id=current_user.id,
        timestamp=datetime.utcnow()
    )
    db.session.add(message)
    db.session.commit()
    
    # Prepare response data
    response = {
        'content': message.content,
        'sender_id': current_user.id,
        'sender_name': current_user.username,  # Adjust based on your User model
        'timestamp': message.timestamp.isoformat(),
        'temp_id': data.get('temp_id')
    }
    
    # Broadcast to all connected clients
    emit('receive_message', response, broadcast=True)
    
    # Send delivery confirmation to sender
    emit('message_status', {
        'temp_id': data.get('temp_id'),
        'status': 'delivered',
        'message_id': message.id
    }, room=request.sid)