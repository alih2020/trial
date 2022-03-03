#!/usr/bin/env python3

from flask import Flask
from flask_peewee.db import Database
from flask_mail import Mail

import config

app = Flask(__name__)
app.config.from_object(config)
mail = Mail(app)

# instantiate the db wrapper
db = Database(app)

# For editdist3()
if config.use_spellfix:
    db.database.load_extension('spellfix')

assert list(db.database.execute_sql('pragma foreign_keys'))[0][0] == 1

# Uncomment this to dump all SQL queries
# import logging
# logger = logging.getLogger('peewee')
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler())
