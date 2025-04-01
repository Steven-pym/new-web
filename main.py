from website import create_app

app, socketio = create_app()  # Now properly unpacks both objects

if __name__ == '__main__':
    socketio.run(app, debug=True)  # Add debug=True for development