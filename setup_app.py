#!/usr/bin/env python3

from flask import Flask
from flask_peewee.db import Database
from flask_mail import Mail

import config
from config import email, password, email_service

app = Flask(__name__)
app.config.from_object(config)

# gmail
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = email
app.config['MAIL_DEFAULT_SENDER'] = email
app.config['MAIL_PASSWORD'] = password
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

# mailtrap.io
# app.config['MAIL_SERVER']='smtp.mailtrap.io'
# app.config['MAIL_PORT'] = 2525
# app.config['MAIL_USERNAME'] = email
# app.config['MAIL_DEFAULT_SENDER'] = email
# app.config['MAIL_PASSWORD'] = password
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USE_SSL'] = False
mail = Mail(app)

# instantiate the db wrapper
db = Database(app)

# For editdist3()
if config.use_spellfix:
    db.database.load_extension('spellfix')

assert list(db.database.execute_sql('pragma foreign_keys'))[0][0] == 1
