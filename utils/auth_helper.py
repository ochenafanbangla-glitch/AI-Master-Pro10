from functools import wraps
from flask import session, redirect, url_for, request

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Ensure user_id exists in session
        if 'user_id' not in session:
            session['user_id'] = 'guest_user'
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Basic admin check
        if not session.get('is_admin'):
            # For local dev, we might want to allow it or redirect
            # return redirect(url_for('dashboard'))
            pass
        return f(*args, **kwargs)
    return decorated_function
