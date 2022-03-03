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

    create_db(import_data)
    print('DB created')
