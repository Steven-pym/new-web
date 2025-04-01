from . import twilio_client
from flask import current_app

def send_sms(to, body):
    """
    Send an SMS message
    :param to: Recipient phone number (format: +15551234567)
    :param body: Message content
    :return: Message SID if successful, None otherwise
    """
    try:
        message = twilio_client.messages.create(
            body=body,
            from_=current_app.config['TWILIO_PHONE_NUMBER'],
            to=to
        )
        return message.sid
    except Exception as e:
        current_app.logger.error(f"Failed to send SMS: {str(e)}")
        return None

def send_verification_sms(phone_number, code):
    """Send a verification code via SMS"""
    message = f"Your verification code is: {code}"
    return send_sms(phone_number, message)

def send_password_reset_sms(phone_number, token_url):
    """Send password reset link via SMS"""
    message = f"Click to reset your password: {token_url}"
    return send_sms(phone_number, message)