import os
import jwt
import datetime
from functools import wraps
from flask import request, jsonify

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-primer-key")

def generate_token(user_id, role):
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
        'iat': datetime.datetime.utcnow(),
        'sub': str(user_id),  # Force string conversion for safety
        'role': role
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Safely get the header, ignoring case
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        
        if not token:
            print("AUTH ERROR: Token is missing from headers (CORS might be stripping it).")
            return jsonify({'error': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user_id = data['sub']
        except jwt.ExpiredSignatureError:
            print("AUTH ERROR: Token expired.")
            return jsonify({'error': 'Token has expired!'}), 401
        except jwt.InvalidTokenError as e:
            print(f"AUTH ERROR: Invalid token - {str(e)}")
            return jsonify({'error': f'Token is invalid: {str(e)}'}), 401
            
        return f(current_user_id, *args, **kwargs)
    return decorated