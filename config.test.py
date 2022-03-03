import time
import os

# configure our database
DATABASE = {
    'name': os.path.dirname(os.path.abspath(__file__)) + '/database.db',
    # 'engine': 'peewee.SqliteDatabase',
    'engine': 'playhouse.sqliteq.SqliteQueueDatabase',
    'pragmas': {'foreign_keys': 1}
}

DEBUG = False
SECRET_KEY = 'Test secret key'
SECURITY_PASSWORD_SALT = 'Test password salt'

use_spellfix = False

# TPS
taxes = [
    ('TPS', '0.05'), # Tax 1
    ('TVQ', '0.09975'), # Tax 2
]

import_data = False

# You'll probably want to set this
os.environ['TZ'] = 'America/Montreal'
time.tzset()
