# TODO : Rename as `config.py`
import time
import os

# configure our database
DATABASE = {
    'name': os.path.dirname(os.path.abspath(__file__)) + '/database.db',
    # 'engine': 'peewee.SqliteDatabase',
    'engine': 'playhouse.sqliteq.SqliteQueueDatabase',
    'pragmas': {'foreign_keys': 1}
}

DEBUG = True
SECRET_KEY = '' # TODO: Choose something long and random
SECURITY_PASSWORD_SALT = '' # TODO: Choose something long and random

use_spellfix = False

# TPS
taxes = [
    ('TPS', '0.05'), # Tax 1
    ('TVQ', '0.09975'), # Tax 2
]

import_data = False

email_service = 'smtp'
email = 'test@email.com'
password = '*****'

# You'll probably want to set this
os.environ['TZ'] = 'America/Montreal'
time.tzset()
