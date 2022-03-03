import email
from pydoc import cli
from xmlrpc.client import DateTime
from setup_app import app, db, mail
import config
from models import *

from flask import render_template, request, redirect, url_for, \
    session, abort, jsonify, g, send_from_directory, flash
from flask_mail import Message

import os
import re
import json
import datetime
from math import ceil
from functools import reduce

import peewee
from peewee import fn

from playhouse.flask_utils import get_object_or_404, PaginatedQuery

from security import public_route

# ---------- Basic profiling ----------
import time
import functools

def timefunc(func):
    @functools.wraps(func)
    def time_closure(*args, **kwargs):
        """time_wrapper's doc string"""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        time_elapsed = time.perf_counter() - start
        print(f"Function: {func.__name__}, Time: {time_elapsed}")
        return result

    return time_closure


def or_where_conds(lst):
    return reduce(peewee.operator.or_, lst)

# ---------- Templates ----------
@app.template_filter()
def humandate(value, format="%d %b %Y"):
    """Format a date time to (Default): d Mon YYYY"""

    if type(value) is int:
        value = datetime.date.fromtimestamp(value)
    elif type(value) is str:
        value = datetime.datetime.fromisoformat(value)

    return value.strftime(format)

@app.template_filter()
def format_currency(value):
    return "${:,.2f}".format(round(value, 2))

@app.template_test('future')
def test_future(value):
    return value > datetime.datetime.now()

@app.template_test('past')
def test_past(value):
    return value < datetime.datetime.now()

@app.context_processor
def inject_debug():
    return dict(debug=app.debug)

# ---------- Routes ----------

@public_route
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/')
def index():

    open_workorders = Workorder.select() \
                               .where(Workorder.paid == False) \
                               .where(Workorder.calendar_date > datetime.date.today() - datetime.timedelta(days=31)) \
                               .order_by(Workorder.calendar_date)


    for w in open_workorders:
        w.group = w.calendar_date.date()

    recent_workorders = Workorder.select().where(Workorder.paid).order_by(Workorder.created.desc()).limit(10)

    return render_template('index.html',
                           open_workorders=open_workorders,
                           recent_workorders=recent_workorders,
                           today=datetime.date.today())


# ---------- Clients ----------
@app.route('/clients/')
def list_clients():

    clients = Client.select().order_by(Client.created.desc())

    query = ''

    if 'query' in request.args:
        query = ' '.join(request.args['query'].split())
        terms = extract_terms(query)

        conditions = []

        for t in terms:
            if config.use_spellfix:
                conditions.append(fn.editdist3(fn.lower(Client.first_name), t) <= 300)
                conditions.append(fn.editdist3(fn.lower(Client.last_name), t) <= 300)
            else:
                conditions.append(Client.first_name.contains(t))
                conditions.append(Client.last_name.contains(t))

        if conditions:
            clients = clients.where(or_where_conds(conditions))

    print(clients)
    clients = PaginatedQuery(clients, 25)

    return render_template('list-clients.html',
                           clients=clients.get_object_list(),
                           query=query,
                           page=clients.get_page(), total_pages=clients.get_page_count())

# ---------- Duplicates ----------
@app.route('/duplicates/')
def duplicates_clients():

    # Prototype email service
    msg = Message("Now we know",
                recipients=["justgoandthrow@gmail.com"])

    msg.body = "Example Receipt"
    msg.html = "<h1>Example Receipt</h1>"
    mail.send(msg)

    # Lists that will contain groups of the same duplicate information
    phone_list = []
    email_list = []
    name_list = []
    
    # Requests all clients who have duplicate information
    client_dup_email = Client.select().group_by(Client.email).having(fn.COUNT(Client.email) > 1)
    client_dup_phone = Client.select().group_by(Client.phone).having(fn.COUNT(Client.phone) > 1)
    client_dup_name = (Client.select().group_by(Client.first_name).having(fn.COUNT(Client.first_name) > 1)) & (Client.select().group_by(Client.last_name).having(fn.COUNT(Client.last_name) > 1))


    # Groups together clients who have the same information
    for client in client_dup_phone:
        phone_list.append(Client.select().where(Client.phone == client.phone ))
    for client in client_dup_email:
        email_list.append(Client.select().where(Client.email == client.email ))
    for client in client_dup_name:
        name_list.append(Client.select().where((Client.last_name == client.last_name) & (Client.first_name == client.first_name) ))

    query = ''

    # if 'query' in request.args:
    #     query = ' '.join(request.args['query'].split())
    #     terms = extract_terms(query)

    #     conditions = []

    #     for t in terms:
    #         print("hello there")
    #         if config.use_spellfix:
    #             conditions.append(fn.editdist3(fn.lower(Client.first_name), t) <= 300)
    #             conditions.append(fn.editdist3(fn.lower(Client.last_name), t) <= 300)
    #         else:
    #             conditions.append(Client.first_name.contains(t))
    #             conditions.append(Client.last_name.contains(t))

    #     if conditions:
    #         clients = clients.where(or_where_conds(conditions))

    missing_names = Client.select().where((Client.first_name == '') | (Client.last_name == ''))
    suspicious_date = Client.select().where( Client.created >= (datetime.datetime.now() - datetime.timedelta(days=3*365)) )

    for client in suspicious_date:
        # print("its")
        print(client)
        
        # print(client.created.truncate_date('day', DateTimeField))
        # if(client.created)
    # for thing in error:
    #     print(thing)

    # select * from client where first_name like '' or last_name like '' 

    return render_template('duplicates.html',
                           client_dup_phone=phone_list,
                           client_dup_email=email_list,
                           client_dup_name=name_list,
                           missing_names=missing_names,
                           suspicious_date=suspicious_date,
                           query=query,)


@app.route('/client/new/', methods=['POST', 'GET'])
@app.route('/client/new/<int:workorder_id>', methods=['POST', 'GET'])
def new_client(workorder_id=None):

    client = Client()

    error = False

    if request.method == 'POST':

        if workorder_id is not None:
            workorder = get_object_or_404(Workorder, (Workorder.id == workorder_id))

        cols = Client.editable_cols()

        try:
            for col in cols:
                if col in request.form:
                    client.__setattr__(col, request.form[col])
            client.save()

            if workorder_id is None:
                return redirect('/workorder/new/' + str(client.id))
            else:
                workorder.client_id = client.id
                workorder.save()
                return redirect('/workorder/' + str(workorder.id))

        except Exception as e:
            print(e)
            error = e

    return render_template('client.html',
                           new=True, error=error,
                           client=client,
                           workorder_id=workorder_id)

@app.route('/client/<int:id>')
def get_client(id):

    client = get_object_or_404(Client, (Client.id==id))

    return render_template('client.html',
                           client=client, new=False,
                           workorders=client.workorders.order_by(Workorder.created.desc()))


# ---------- Workorders/invoices ----------
@app.route('/workorders/')
@app.route('/workorders/<int:page>')
def list_workorders(page=1):

    per_page = 25

    workorders = Workorder.select().order_by(Workorder.created.desc()).paginate(page, per_page)

    total_pages = ceil(Workorder.select().count() / per_page)

    if page > total_pages:
        return redirect('/workorders/' + str(total_pages))

    return render_template('list-workorders.html', workorders=workorders, page=page, total_pages=total_pages)

@app.route('/workorder/delete/<int:id>')
def delete_workorder(id):

    try:
        # TODO : pragma checks are not always working
        assert list(db.database.execute_sql('pragma foreign_keys'))[0][0] == 1

        Workorder.delete().where(Workorder.id==id).execute()

        flash('Workorder deleted', 'info')
    except Exception as e:
        print(e)
        flash('This workorder cannot be deleted', 'danger')

    return redirect("/")

@app.route('/workorder/new/direct')
@app.route('/workorder/new/<int:client_id>')
def new_workorder(client_id=None):

    # TODO : Check for empty workorders?
    workorder = Workorder.create(client_id=client_id)

    return redirect('/workorder/' + str(workorder.id))

@app.route('/workorder/<int:id>')
def get_workorder(id):

    workorder = get_object_or_404(Workorder, (Workorder.id==id))

    # Propose to use most recent bike if no bike is set yet
    last_bike = {}
    if not workorder.bike_description and not workorder.bike_serial_number and workorder.client:
        last_workorder = workorder.client.workorders \
                                         .where((Workorder.id != id) & ((Workorder.bike_description != '') | (Workorder.bike_serial_number != ''))) \
                                         .order_by(Workorder.created.desc()).limit(1)

        if last_workorder.count() > 0:
            last_workorder = last_workorder.get()
            last_bike['bike_description'] = last_workorder.bike_description
            last_bike['bike_serial_number'] = last_workorder.bike_serial_number

    items = []

    for i in workorder.items:
        items.append(i.serialized())

    quick_items = InventoryItem.select().where(InventoryItem.quick_add).dicts()

    # FIXME : customized code
    membership_item = InventoryItem.select().where(InventoryItem.special_meaning=='membership').dicts()[0]
    propose_membership = workorder.client is not None and \
        (workorder.client.membership_paid_until is None or \
         test_past(workorder.client.membership_paid_until)) and \
         not workorder.items.where(WorkorderItem.inventory_item_id == membership_item['id']).exists()

    return render_template('workorder.html',
                           workorder=workorder,
                           last_bike=last_bike,
                           items=items,
                           quick_items=quick_items,
                           membership_item=membership_item,
                           propose_membership=propose_membership,
                           tax1_name=config.taxes[0][0],
                           tax2_name=config.taxes[1][0])

@app.route('/workorder/set_client/<int:workorder_id>')
@app.route('/workorder/set_client/<int:workorder_id>/<int:client_id>')
def set_workorder_client(workorder_id, client_id=None):

    workorder = get_object_or_404(Workorder, (Workorder.id==workorder_id))

    if client_id is not None:
        # Assert the client exists
        get_object_or_404(Client, (Client.id==client_id))

    workorder.client_id = client_id
    workorder.save()

    return redirect('/workorder/' + str(workorder.id))

# ---------- Admin ----------
@app.route('/manage/', methods=['POST', 'GET'])
def manage():
    return render_template('todo.html', msg='Edit items, edit taxes')

@app.route('/reports/', methods=['POST', 'GET'])
@timefunc
def reports():
    date_start = datetime.date.today() - datetime.timedelta(days=365)
    date_end = datetime.date.today()

    if 'date_start' in request.args:
        date_start = datetime.date.fromisoformat(request.args['date_start'])

    if 'date_end' in request.args:
        date_end = datetime.date.fromisoformat(request.args['date_end'])


    postal_code_query =  Client.select(
        fn.UPPER(fn.SUBSTR(Client.postal_code, 1, 3)).alias('pc'),
        fn.COUNT(peewee.SQL('*')).alias('nb')
    ).where(Client.postal_code != '') \
     .group_by(peewee.SQL('pc')) \
     .order_by(peewee.SQL('nb').desc())

    # TOP 5
    postal_codes_stats = list(postal_code_query.limit(5).dicts())
    postal_codes_keys = [line['pc'] for line in postal_codes_stats]
    postal_codes_vals = [line['nb'] for line in postal_codes_stats]

    # Others (known)
    postal_codes_others = Client.select().where(
        fn.UPPER(fn.SUBSTR(Client.postal_code, 1, 3)).not_in(postal_codes_keys) & (Client.postal_code != '')
    ).count()

    # Unknown
    postal_codes_unknown = Client.select().where(Client.postal_code == '').count()

    if Client.select().count() != sum(postal_codes_vals + [postal_codes_others, postal_codes_unknown]):
        print('ERROR: ', Client.select().count(), '!=', sum(postal_codes_vals + [postal_codes_others, postal_codes_unknown]))

    for i in range(len(postal_codes_keys)):
        key = postal_codes_keys[i]

        if key in postal_codes:
            postal_codes_keys[i] = key + ' (' + postal_codes[key] + ')'

    paid_workorders = Workorder.select() \
                               .where((Workorder.paid) & (fn.DATE(Workorder.paid_date).between(date_start, date_end)))

    workorder_stats = {
        'subtotal': Decimal(0),
        'total': Decimal(0),
        'taxes1': Decimal(0),
        'taxes2': Decimal(0),
        'taxes': Decimal(0),
        'total_discounts': Decimal(0),
    }

    print(paid_workorders.count())

    for workorder in paid_workorders:
        workorder_stats['subtotal'] += workorder.subtotal()
        workorder_stats['total'] += workorder.total()
        workorder_stats['taxes1'] += workorder.taxes1()
        workorder_stats['taxes2'] += workorder.taxes2()
        workorder_stats['taxes'] += workorder.taxes()
        workorder_stats['total_discounts'] += workorder.total_discounts()

    print(workorder_stats)

    return render_template('reports.html',
                           postal_codes_keys=postal_codes_keys + ['Others', 'Unknown'],
                           postal_codes_vals=postal_codes_vals + [postal_codes_others, postal_codes_unknown],
                           date_start=date_start,
                           date_end=date_end,
                           workorder_stats=workorder_stats,
                           tax1_name=config.taxes[0][0],
                           tax2_name=config.taxes[1][0])

# ---------- API ----------
@app.route('/api/edit/<model>/<int:id>', methods=['POST'])
def edit_model(model, id):

    authorized_models = {'client': Client, 'workorderitem': WorkorderItem, 'workorder': Workorder}

    klass = authorized_models[model]

    form = request.json
    column = form['column']
    value = form['value']

    if klass == WorkorderItem:
        workorderitem = klass.get(id)
        if workorderitem.workorder.paid:
            abort(403)

    if klass == Workorder and column == 'calendar_date':
        value = datetime.datetime.fromisoformat(value)

    allowed_columns = klass.editable_cols()

    if column not in allowed_columns:
        abort(403)

    klass.update({column: value}).where(klass.id == id).execute()

    return jsonify(True)

@app.route('/api/total/<int:workorder_id>')
def get_workorder_total_infos(workorder_id):
    workorder = get_object_or_404(Workorder, (Workorder.id==workorder_id))

    print('TODO : no force_calc here, just to debug')

    return jsonify({
        'subtotal': round(workorder.subtotal(force_calc=True), 2),
        'discount': round(workorder.total_discounts(), 2),
        'taxes1': round(workorder.taxes1(force_calc=True), 2),
        'taxes2': round(workorder.taxes2(force_calc=True), 2),
        'taxes': round(workorder.taxes(force_calc=True), 2),
        'total': round(workorder.total(force_calc=True), 2),
    })

@app.route('/api/add-item/<int:workorder_id>/<int:inventory_item_id>')
def add_item(workorder_id, inventory_item_id):

    workorder = get_object_or_404(Workorder, (Workorder.id==workorder_id))
    inventory_item = get_object_or_404(InventoryItem, (InventoryItem.id==inventory_item_id))

    # TODO : assert la facture est pas déjà payée
    if workorder.paid:
        abort(403)

    item = WorkorderItem.create(
        name=inventory_item.name,
        price=inventory_item.price,
        orig_price=inventory_item.price,
        taxable=inventory_item.taxable,
        workorder_id=workorder_id, inventory_item_id=inventory_item_id
    )

    return jsonify(item.serialized())

@app.route('/api/delete-workorderitem/<int:workorderitem_id>')
def remove_item(workorderitem_id):

    workorderitem = get_object_or_404(WorkorderItem, (WorkorderItem.id==workorderitem_id))

    if workorderitem.workorder.paid:
        abort(403)

    WorkorderItem.delete().where(WorkorderItem.id==workorderitem_id).execute()

    return jsonify(True)


def extract_terms(s):
    terms = [term.strip() for term in s.split()]
    terms = set([t.lower() for t in terms if t and len(t) > 1])
    return set(terms)

# https://stackoverflow.com/a/17741165/14639652
import difflib

def fuzzy_matches(large_string, query_string, threshold):
    words = large_string.split()
    for word in words:
        s = difflib.SequenceMatcher(None, word, query_string)
        match = ''.join(word[i:i+n] for i, j, n in s.get_matching_blocks() if n)

        score = len(match) / float(len(query_string))

        if score >= threshold:
            yield match, len(match)

def does_match(needle, haystack):
    if len(needle) < 2:
        return 0
    if len(needle) <= 3:
        return (needle.lower() in haystack.lower()) * 0.5
    else:
        all_matches = list(fuzzy_matches(haystack.lower(), needle.lower(), 0.8))
        nb = len(all_matches)

        if not nb:
            return 0

        return sum([x[1] for x in all_matches])


@app.route('/api/search/inventory_items/', methods=['GET'])
@timefunc
def api_get_inventory_items():
    query = ' '.join(request.args['query'].split())

    # TODO : Normalize accents
    # " is stored as '' in the actual data
    # . and , should mean the same thing for numbers

    terms = list(extract_terms(query))[:3]

    if not terms:
        return jsonify([])

    # TODO : Select only relevant data
    q = InventoryItem.select()

    hard_constraints = None
    or_where = None

    for t in terms:
        # Les mots sont cherchés un peu fuzzy, les chiffres et
        # caractères correspondent à des codes/contraintes
        if re.search('[^a-zA-Z]{2,}', t) or len(t) < 2:
            cond = (InventoryItem.name.contains(t) | InventoryItem.sku_code.contains(t))
            hard_constraints = cond if hard_constraints is None else hard_constraints & cond
        else:
            cond = InventoryItem.name.contains(t)
            or_where = cond if or_where is None else or_where | cond

    if hard_constraints is not None and or_where is not None:
        q = q.where(hard_constraints & or_where)
    elif hard_constraints is not None:
        q = q.where(hard_constraints)
    elif or_where is not None:
        q = q.where(or_where)

    q = q.where(InventoryItem.archived==False)

    print(q)

    q.limit(50)

    q = q.dicts()

    results = []

    for item in q:
        score = 0

        score_name = does_match(query, item['name'])
        score_keywords = does_match(query, item['keywords'])

        score += score_name * 2 + score_keywords * 2 * 0.5

        for t in terms:
            score_name = does_match(t, item['name'])
            score_keywords = does_match(t, item['keywords'])

            score += score_name + 0.5 * score_keywords

        item['score'] = score
        results.append((item, score))

    sorted_results = [
        item
        for item, score in sorted(results, key=lambda x: x[1], reverse=True)
    ]

    return jsonify(sorted_results)


@app.route('/api/search/clients/', methods=['GET'])
@timefunc
def api_get_clients():
    query = ' '.join(request.args['query'].split())
    terms = list(extract_terms(query))[:3]

    if not terms:
        return jsonify([])

    q = Client.select(Client.id, Client.first_name, Client.last_name, Client.phone)

    conditions = []

    for t in terms:
        conditions.append(Client.first_name.startswith(t))
        conditions.append(Client.last_name.startswith(t))

    conditions = or_where_conds(conditions)

    q = q.where(conditions)

    print(q)
    q = q.dicts()

    results = []

    for item in q:

        score = 0

        full_match = query in item['first_name'] + ' ' + item['last_name']

        score_fullname = does_match(query, item['first_name'] + ' ' + item['last_name'])
        score_firstname = does_match(query, item['first_name'])
        score_lastname = does_match(query, item['last_name'])

        score += (3 * score_fullname + score_firstname + score_lastname) * 3 + 10 if full_match else 0

        for t in terms:
            score_fullname = does_match(t, item['first_name'] + ' ' + item['last_name'])
            score_firstname = does_match(t, item['first_name'])
            score_lastname = does_match(t, item['last_name'])

            score += 3 * score_fullname + score_firstname + score_lastname

        item['score'] = score
        results.append((item, score))

    sorted_results = [
        item
        for item, score in sorted(results, key=lambda x: x[1], reverse=True)
    ]

    return jsonify(sorted_results)
