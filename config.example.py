# TODO : Copy this file as `config.py`

# Fill the blanks here to configure your installation :

COMPANY_NAME = 'Example Company'
COMPANY_ADDRESS = '123 Fake Street'

# Secrets : these should be kept secret and must not change once the
# website is live
SECRET_KEY = '' # TODO: Choose something long and random, eg.: *HSD*un2moienuduijk2...
SECURITY_PASSWORD_SALT = '' # TODO: Choose something long and random

# Taxes
taxes = [
    # Note : keep the '' around taxes to avoid rounding problems
    ('TPS', '0.05'), # Tax 1
    ('TVQ', '0.09975'), # Tax 2
]

# Email setup
MAIL_USERNAME = 'test@email.com'
MAIL_PASSWORD = '*****'
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 465
MAIL_DEFAULT_SENDER = MAIL_USERNAME # Usually the same as your username
MAIL_USE_TLS = False
MAIL_USE_SSL = True

# You'll probably want to set this
import time
import os

os.environ['TZ'] = 'America/Montreal'
time.tzset()

# --------------------------------------------------
# These should be sensible defaults

DATABASE = {
    'name': os.path.dirname(os.path.abspath(__file__)) + '/database.db',
    # SqliteQueueDatabase is a cute hack to prevent bugs when using
    # multiple threads to access the same database. It comes with the
    # caveat of *never* using SQL TRANSACTIONs
    # https://docs.peewee-orm.com/en/latest/peewee/playhouse.html
    # 'engine': 'peewee.SqliteDatabase',
    'engine': 'playhouse.sqliteq.SqliteQueueDatabase',
    'pragmas': {'foreign_keys': 1}
}

DEBUG = False

# To get fuzzy strings search, ex.: Josca -> Joska, add the
# `spellfix.so` extension to the project root and set this to True
use_spellfix = False
