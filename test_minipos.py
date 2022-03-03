import json
import pytest
import tempfile
import os
from decimal import Decimal

@pytest.fixture(scope="module")
def app():
    import config
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    os.unlink(db_path)

    config.DATABASE['name'] = db_path
    config.DATABASE['engine'] = 'peewee.SqliteDatabase'
    config.WTF_CSRF_ENABLED = False
    config.MAIL_SUPPRESS_SEND = True

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

    assert b'Logout' in rv.data

    rv = client.get('/logout', follow_redirects=True)
    assert b'Login' in rv.data

def test_no_500_errors(client, login):
    """There should be no 500 errors"""
    from models import Workorder, Client

    sample_workorder = Workorder.select().where(~Workorder.paid).get()
    sample_paid_workorder = Workorder.select().where(Workorder.paid).get()
    sample_client = Client.get()

    for path in [
            '/',
            '/clients/',
            '/workorders/',
            '/admin/',
            '/reports/',
            '/static/favicon.ico',
            f'/workorder/{sample_paid_workorder.id}',
            f'/workorder/{sample_workorder.id}',
            f'/workorder/refund/{sample_paid_workorder.id}',
            f'/workorder/receipt/{sample_paid_workorder.id}',
            f'/workorder/email-receipt/{sample_paid_workorder.id}',
            f'/client/{sample_client.id}']:

        rv = client.get(path, follow_redirects=True)

        print(path)
        assert rv.status_code == 200


def most_recent_workorder():
    from models import Workorder

    return Workorder.select().order_by(Workorder.id.desc()).get()

def test_mail(client, login):
    from models import Client, Workorder, InventoryItem, WorkorderItem

    rv = client.get('/workorder/new/direct', follow_redirects=True)

    # New invoice, without a client
    workorder = most_recent_workorder()

    rv = client.get(f'/workorder/email-receipt/{workorder.id}', follow_redirects=False)
    assert rv.status_code == 403


    # With a client, without an email
    workorder = Workorder.select().where(Workorder.paid_date).order_by(Workorder.id.desc()).get()

    w_client = Client.select().get()
    workorder.client_id = w_client.id
    workorder.save()

    w_client.email = ''
    w_client.email_consent = True
    w_client.save()

    rv = client.get(f'/workorder/email-receipt/{workorder.id}', follow_redirects=False)
    assert rv.status_code == 403

    # With a client, with an email, without consent
    w_client.email = 'test@example.com'
    w_client.email_consent = False
    w_client.save()

    rv = client.get(f'/workorder/email-receipt/{workorder.id}', follow_redirects=False)
    assert rv.status_code == 403

    # All is good
    w_client.email = 'test@example.com'
    w_client.email_consent = True
    w_client.save()

    rv = client.get(f'/workorder/email-receipt/{workorder.id}', follow_redirects=True)
    assert rv.status_code == 200
    assert b'alert-success' in rv.data

def test_delete_workorder(client, login):
    from models import Workorder, InventoryItem, WorkorderItem

    # Simple create/delete of an empty workorder
    orig_count = Workorder.select().count()

    rv = client.get('/workorder/new/direct', follow_redirects=True)
    assert rv.status_code == 200

    assert Workorder.select().count() == orig_count + 1

    id = most_recent_workorder().id

    rv = client.get('/workorder/delete/' + str(id), follow_redirects=True)

    assert rv.status_code == 200
    assert Workorder.select().count() == orig_count


def test_refund_simple(client, login):
    from models import Workorder, WorkorderItem

    workorder = Workorder.select().order_by(Workorder.id.asc()).get()
    workorder_count = Workorder.select().count()

    refunded_items = []
    for item in workorder.items:
        refunded_items.append(item.id)

    data = {
        'refunded_items_id':refunded_items,
        'workorder_id':workorder.id
    }

    json_data = json.dumps(data)
    rv = client.post('/api/refund/', data=dict(items=json_data), follow_redirects=True)
    refunded_workorder = most_recent_workorder()

    assert Workorder.select().count() == workorder_count + 1

    assert workorder.client_id == refunded_workorder.client_id
    assert workorder.bike_description == refunded_workorder.bike_description
    assert workorder.bike_serial_number == refunded_workorder.bike_serial_number

    for i in range(len(workorder.items)):
        assert workorder.items[i].nb == -refunded_workorder.items[i].nb


def test_refund_cornercases(client, login):
    from models import Workorder, WorkorderItem

    # Creates workorder with 2 items
    rv = client.get('/workorder/new/direct', follow_redirects=True)
    workorder = most_recent_workorder()
    rv = client.get(f'/api/add-item/{workorder.id}/1', follow_redirects=True)
    rv = client.get(f'/api/add-item/{workorder.id}/2', follow_redirects=True)

    # Redirected if workorder is not paid
    rv = client.get(f'/workorder/refund/{workorder.id}', follow_redirects=False)
    assert not workorder.paid and rv.status_code == 302

    rv = client.post(f'/workorder/pay/{workorder.id}', data=dict(payment_method='cash'), follow_redirects=True)
    workorder = Workorder.get(workorder.id)

    rv = client.get(f'/workorder/refund/{workorder.id}', follow_redirects=False)
    assert workorder.paid and rv.status_code == 200


    # Cannot refund an item twice
    data = {
        'refunded_items_id': [workorder.items[0].id],
        'workorder_id':workorder.id
    }
    json_data = json.dumps(data)

    rv = client.post('/api/refund/', data=dict(items=json_data), follow_redirects=True)
    workorder_count =  Workorder.select().count()
    workorderitem_count = WorkorderItem.select().count()

    rv = client.post('/api/refund/', data=dict(items=json_data), follow_redirects=True)
    assert workorder_count == Workorder.select().count()
    assert workorderitem_count == WorkorderItem.select().count()


    # Cannnot refund a refund
    refund_workorder = most_recent_workorder()
    rv = client.post(f'/workorder/pay/{refund_workorder.id}', data={'payment_method': 'cash'}, follow_redirects=True)

    data = {
        'refunded_items_id':[refund_workorder.items[0].id],
        'workorder_id':refund_workorder.id
    }
    json_data = json.dumps(data)
    workorder_count = Workorder.select().count()
    workorderitem_count = WorkorderItem.select().count()

    rv = client.post('/api/refund/', data=dict(items=json_data), follow_redirects=True)
    assert workorder_count == Workorder.select().count()
    assert workorderitem_count == WorkorderItem.select().count()


    # Refund button is only available is workorder is not fully refunded
    rv = client.get(f'/workorder/{workorder.id}', follow_redirects=True)
    assert b'id="refund-button"' in rv.data

    data = {
        'refunded_items_id':[workorder.items[1].id],
        'workorder_id':workorder.id
    }
    json_data = json.dumps(data)
    rv = client.post('/api/refund/', data=dict(items=json_data), follow_redirects=True)

    rv = client.get(f'/workorder/{workorder.id}', follow_redirects=True)
    assert b'id="refund-button"' not in rv.data

    # 4b. Redirected if workorder is fully refunded
    rv = client.get(f'/workorder/refund/{workorder.id}', follow_redirects=False)
    for item in workorder.items:
        serialized_item = item.serialized()
        assert serialized_item['refunded_in_workorder_id'] and rv.status_code == 302

def test_payment(client, login):
    from models import Workorder, Transaction, InventoryItem
    import config

    payment_methods = ['cash', 'interac', 'visa']

    for payment_method in payment_methods:
        rv = client.get('/workorder/new/direct', follow_redirects=True)
        workorder_id = most_recent_workorder().id

        inventory_item = InventoryItem.select().order_by(InventoryItem.id.asc()).where(InventoryItem.taxable).get()

        rv = client.get(f'/api/add-item/{workorder_id}/{inventory_item.id}', follow_redirects=True)

        rv = client.post(f'/workorder/pay/{workorder_id}', data=dict(payment_method=payment_method), follow_redirects=True)

        workorder = Workorder.get(workorder_id)

        assert workorder.paid_subtotal == inventory_item.price
        assert workorder.paid_tax1_rate == Decimal(config.taxes[0][1])
        assert workorder.paid_tax2_rate == Decimal(config.taxes[1][1])
        assert workorder.paid_taxes1 == round(workorder.paid_subtotal * Decimal(config.taxes[0][1]), 2)
        assert workorder.paid_taxes2 == round(workorder.paid_subtotal * Decimal(config.taxes[1][1]), 2)
        assert workorder.paid_total == workorder.paid_subtotal + workorder.paid_taxes1 + workorder.paid_taxes2
        assert workorder.paid

        assert Transaction.select().where(Transaction.workorder_id == workorder_id).count() == 1

    # TODO : Payment for workorders with weird taxes (eg.: two taxable
    # items, one non-taxable)

def test_payment_zero_dollar(client, login):
    from models import Workorder, Transaction, InventoryItem

    rv = client.get('/workorder/new/direct', follow_redirects=True)
    workorder = most_recent_workorder()

    assert workorder.transactions.count() == 0
    assert workorder.items.count() == 0

    # Empty workorders should not be payable
    rv = client.post(f'/workorder/pay/{workorder.id}', data=dict(payment_method='visa'), follow_redirects=True)
    assert rv.status_code != 200


    # 0$ total workorders should be payable
    InventoryItem.insert(name='Testing', keywords='',
                         price=0.00, cost=0.0, msrp=0,
                         taxable=True, avg_time_spent=0).execute()


    inventory_item = InventoryItem.select().order_by(InventoryItem.id.desc()).get()

    rv = client.get(f'/api/add-item/{workorder.id}/{inventory_item.id}', follow_redirects=True)
    assert rv.status_code == 200

    rv = client.post(f'/workorder/pay/{workorder.id}', data=dict(payment_method='cash'), follow_redirects=True)
    assert rv.status_code == 200

    workorder = Workorder.get(workorder.id) # Reload
    assert workorder.paid

    # 0$ workorders should not create a transaction
    assert workorder.transactions.count() == 0

    # Don't repay the same workorder twice
    rv = client.post(f'/workorder/pay/{workorder.id}', data=dict(payment_method='visa'), follow_redirects=True)
    assert rv.status_code != 200

    # Items from a paid workorder should not be editable via the api
    rv = client.get(f'/api/add-item/{workorder.id}/{inventory_item.id}', follow_redirects=True)
    assert rv.status_code != 200


"""
TODO :

- Any action done to the "Transaction" table should not affect Sales
  shown in /reports/

- Add tests for the auto-complete searches
"""
