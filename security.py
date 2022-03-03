from setup_app import db, app
from flask import request, redirect, url_for
from models import User, Role, UserRoles

from flask_security import Security, PeeweeUserDatastore, hash_password, current_user

import config

user_datastore = PeeweeUserDatastore(db, User, Role, UserRoles)
security = Security(app, user_datastore)

if config.DEBUG:
    @app.before_first_request
    def create_user():
        if not user_datastore.find_user(email="test@test.com"):
            user_datastore.create_user(email="test@test.com", password=hash_password("password"))

@app.before_request
def check_valid_login():
    """Basic security, must be authenticated to see anything
    Adapted from https://stackoverflow.com/a/52572337/14639652
    """
    if current_user.is_authenticated or \
       request.endpoint == 'static' or \
       request.endpoint == 'security.login' or \
       (request.endpoint in app.view_functions and \
        getattr(app.view_functions[request.endpoint], 'is_public', False)):
        return # Access granted
    else:
        return redirect(url_for('security.login', next=request.path))

def public_route(decorated_function):
    decorated_function.is_public = True
    return decorated_function
