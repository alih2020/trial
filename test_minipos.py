import pytest
import tempfile
import os

@pytest.fixture(scope="module")
def app():
    import config
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    os.unlink(db_path)

    config.DATABASE['name'] = db_path
    config.DATABASE['engine'] = 'peewee.SqliteDatabase'
    config.WTF_CSRF_ENABLED = False

    from app import app

    yield app

    os.unlink(db_path)

@pytest.fixture(scope="module")
def client(app):
    from security import user_datastore
    from flask_security import hash_password
    from create_db import create_db
    from models import Client
    import config

    with app.test_client() as client:

        with app.app_context():

            create_db()

            if not user_datastore.find_user(email="pytest@pytest.com"):
                user_datastore.create_user(email="pytest@pytest.com", password=hash_password("pytest"))

        yield client

@pytest.fixture(scope="function")
def login(client):

    rv = client.post('/login', data=dict(
        email='pytest@pytest.com',
        password='pytest'
    ), follow_redirects=True)

    yield True

    rv = client.get('/logout', follow_redirects=True)

def test_no_login(client):
    """Nothing should be reachable except /login"""

    for path in [
            '/',
            '/clients/',
            '/workorders/',
            '/whatever/',
            '/admin/',
            '/client/1']:

        rv = client.get(path, follow_redirects=False)
        assert rv.status_code != 200

        rv = client.get(path, follow_redirects=True)
        assert b'Login' in rv.data

def test_login(client):
    rv = client.post('/login', data=dict(
        email='pytest@pytest.com',
        password='pytest'
    ), follow_redirects=True)

    assert b'Current orders' in rv.data

    rv = client.get('/logout', follow_redirects=True)
    assert b'Login' in rv.data

def test_no_500_errors(client, login):
    """There should be no 500 errors"""
    from models import Workorder, Client

    sample_workorder = Workorder.get()
    sample_client = Client.get()

    for path in [
            '/',
            '/clients/',
            '/reports/',
            '/static/favicon.ico',
            '/workorders/',
            f'/workorder/{sample_workorder.id}',
            '/admin/',
            f'/client/{sample_client.id}']:

        rv = client.get(path, follow_redirects=True)
        assert rv.status_code == 200

def test_delete_workorder(client, login):
    from models import Workorder, InventoryItem, WorkorderItem

    # Simple create/delete of an empty workorder
    orig_count = Workorder.select().count()

    rv = client.get('/workorder/new/direct', follow_redirects=True)
    assert rv.status_code == 200

    assert Workorder.select().count() == orig_count + 1

    id = Workorder.select().order_by(Workorder.id.desc()).get().id

    rv = client.get('/workorder/delete/' + str(id), follow_redirects=True)

    assert rv.status_code == 200
    assert Workorder.select().count() == orig_count

    # Deleting non-empty workorders should be forbidden
    rv = client.get('/workorder/new/direct', follow_redirects=True)
    workorder_with_item = Workorder.select().order_by(Workorder.id.desc()).get()
    item = InventoryItem.get()

    new_item = client.get(f'/api/add-item/{workorder_with_item.id}/{item.id}').get_json()

    rv = client.get(f'/workorder/delete/{workorder_with_item.id}', follow_redirects=False)
    assert rv.status_code != 200

    rv = client.get(f'/workorder/delete/{workorder_with_item.id}', follow_redirects=True)
    assert b'alert-danger' in rv.data
    assert Workorder.get(workorder_with_item.id).id == workorder_with_item.id

"""
TODO :

- Any action done to the "Transaction" table should not affect Sales
  shown in /reports/

"""
