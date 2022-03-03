from setup_app import app, db

# from auth import *
from security import *
from admin import admin
# from api import api
from models import *
from views import *

import click

@app.cli.command("create-db")
@click.option('--import-data/--no-import-data', default=False)
def click_create_db(import_data):
    from create_db import create_db
    from import_db import validate_db

    create_db(import_data)

    if import_data:
        validate_db()

    print('DB created')

@app.cli.command("validate-db")
def click_validate_db():
    from import_db import validate_db

    validate_db()

    print('DB validated')

@app.cli.command("anonymize-db")
def click_create_db():
    from create_db import anonymize

    assert app.config['DEBUG']

    anonymize()

    print('Done')
