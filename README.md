MiniPOS
=======

Small POS (Point of Sale) designed for small, community bike shops.

## Run on Unix

For a quick setup with `venv` :

```bash
# Install dependancies in a virtual env
python3 -m venv venv
. venv/bin/activate # for bash

# Install dependancies :
pip install -r requirements.txt

# Local configuration
cp config.example.py config.py
# SET A SECRET KEY HERE
nano config.py

# Create database
FLASK_ENV=development flask create-db
```

Run with :

```bash
# Dev :
FLASK_ENV=development flask run
# Production : TODO (use gunicorn or something like that to support wsgi)
```

## Run on Windows

```bash
# Install dependancies in a virtual env
py -3 -m venv venv

# Activate the environment on Windows
venv\Scripts\activate

# Install dependancies :
pip install -r requirements.txt

# Local configuration
copy config.example.py config.py

# SET A SECRET KEY HERE : config.py

# Create DB
flask create-db

# RUN with DEV
set FLASK_ENV=development
flask run
```

## Technologies & Design choices

MiniPOS is built with
[Flask](https://flask.palletsprojects.com/en/2.0.x/), using the
[Peewee ORM](http://docs.peewee-orm.com/en/latest/) to manage a small
SQLite database.

The code structure is mostly inspired by [this
article](https://charlesleifer.com/blog/structuring-flask-apps-a-how-to-for-those-coming-from-django/):

- `models.py` : peewee models
- `views.py` : routes and views, most of the application logic is here
- `config.example.py` : configuration example, you should copy this as
  `config.py`
- `app.py` : application entry point, orchestrates the import of other modules
- `setup_app.py` : creates the Flask app and the Peewee [Database
  Wrapper](http://docs.peewee-orm.com/projects/flask-peewee/en/latest/database.html)
- `admin.py` and `security.py` : setup Flask-Admin and Flask-Security
- `create_db.py` and `import_db.py` : database creation with test data
  or imported data
- `test_minipos.py` : tests


Most modifications should occur in `models.py` and `views.py`

## Unit tests

Unit tests use `pytest` :

```bash
$ pytest
# Or with code coverage :
$ pytest --cov --cov-report html
```

## License

MIT License
