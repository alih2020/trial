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

@app.errorhandler(403)
def page_not_found(e):
    return render_template('403.html', e=e), 403

@app.route('/')
def index():
    open_workorders = Workorder.select() \
                               .where(Workorder.paid == False) \
                               .where(Workorder.calendar_date > datetime.date.today() - datetime.timedelta(days=62)) \
                               .order_by(Workorder.calendar_date)


    for w in open_workorders:
        w.group = w.calendar_date.date()

    recent_workorders = Workorder.select().where(Workorder.paid).order_by(Workorder.paid_date.desc()).limit(10)

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
    from itertools import groupby

    def find_duplicates_query(field):
        """Returns clients with a duplicate field, ordered by that field"""
        return Client.select() \
                     .where(field.in_( \
                        Client.select(field) \
                        .where(fn.LENGTH(field) > 0) \
                        .group_by(field) \
                        .having(fn.COUNT(field) > 1))) \
                     .order_by(field)

    # Requests all clients who have duplicate information

    # TODO : add ICU SQLite extension to use regex_replace() to keep only numbers
    client_dup_phone = find_duplicates_query(Client.phone)

    client_dup_email = find_duplicates_query(Client.email)

    full_name = Client.first_name + Client.last_name
    client_dup_name = Client.select() \
                            .where(full_name.in_( \
                               Client.select(full_name) \
                               .where((fn.LENGTH(Client.first_name) > 0) & (fn.LENGTH(Client.last_name) > 0)) \
                               .group_by(full_name) \
                               .having(fn.COUNT(full_name) > 1))) \
                            .order_by(full_name)

    # Groups together clients who have the same information
    phone_list = groupby(client_dup_phone, lambda x: x.phone)
    email_list = groupby(client_dup_email, lambda x: x.email)
    name_list = groupby(client_dup_name, lambda x: x.name())

    # Requests and section of erroneous info
    current_date = datetime.datetime.now()
    db_column = Client.first_name + Client.last_name + Client.address + Client.postal_code + Client.year_of_birth

    missing_names = Client.select().where((Client.first_name == '') | (Client.last_name == ''))
    suspicious_date = Client.select().where(Client.year_of_birth >= (current_date.year - 3))
    wrong_character = Client.select().where(db_column.contains("@"))

    return render_template('duplicates.html',
                           client_dup_phone=phone_list,
                           client_dup_email=email_list,
                           client_dup_name=name_list,
                           missing_names=missing_names,
                           suspicious_date=suspicious_date,
                           wrong_character=wrong_character)


@app.route('/client/new/', methods=['POST', 'GET'])
@app.route('/client/new/<int:workorder_id>', methods=['POST', 'GET'])
def new_client(workorder_id=None):
    """Create a new client, then redirect to a new or existing
    workorder"""
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
        
        WorkorderItem.delete().where(WorkorderItem.workorder_id==id).execute()
        Workorder.delete().where(Workorder.id==id).execute()

        flash('Workorder deleted', 'info')
    except Exception as e:
        print(e)
        flash('This workorder cannot be deleted', 'danger')

    return redirect("/")

@app.route('/workorder/new/direct')
@app.route('/workorder/new/<int:client_id>')
def new_workorder(client_id=None):

    # TODO : Check for empty workorders?  Empty workorders can be
    # created by mistake, we should have a way to delete those to
    # avoid polluting the database

    workorder = Workorder.create(client_id=client_id)

    return redirect('/workorder/' + str(workorder.id))

@app.route('/workorder/refund/<int:id>')
def refund_workorder(id):

    workorder = get_object_or_404(Workorder, (Workorder.id==id))

    # Checks if all items are either refunded or refunds of other items
    total_workorder_items = workorder.items.count()
    refund_items = workorder.items.where(WorkorderItem.refund_item_id.is_null(False)).count()
    refunded_items = workorder.items.where(WorkorderItem.id << WorkorderItem.select(WorkorderItem.refund_item_id).where(WorkorderItem.refund_item_id.is_null(False))).count()
    refunded = (refund_items + refunded_items) == total_workorder_items

    if refunded or not workorder.paid:
        return redirect('/workorder/' + str(workorder.id))

    items = []

    for i in workorder.items.where(WorkorderItem.refund_item_id.is_null(True)):
        item = i.serialized()
        # if not item['refunded_in_workorder_id']:
        items.append(item)

    quick_items = InventoryItem.select().where(InventoryItem.quick_add).dicts()
    return render_template('refund.html',
                           workorder=workorder,
                           items=items,
                           quick_items=quick_items,
                           tax1_name=config.taxes[0][0],
                           tax2_name=config.taxes[1][0])

@app.route('/workorder/<int:id>')
def get_workorder(id):

    workorder = get_object_or_404(Workorder, (Workorder.id==id))
    client = workorder.client

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

    # Checks if all items are either refunded or refunds of other items
    total_workorder_items = workorder.items.count()
    refund_items = workorder.items.where(WorkorderItem.refund_item_id.is_null(False)).count()
    refunded_items = workorder.items \
                              .where(
                                  WorkorderItem.id.in_(
                                      WorkorderItem.select(WorkorderItem.refund_item_id) \
                                                   .where(WorkorderItem.refund_item_id.is_null(False)))
                              ).count()
    refunded = (refund_items + refunded_items) == total_workorder_items

    quick_items = InventoryItem.select().where(InventoryItem.quick_add).dicts()
    statuses = WorkorderStatus.select().where(WorkorderStatus.archived==False).order_by(WorkorderStatus.display_order)

    # FIXME : membership logic will probably not be usefull to
    # everyone, there should be a way to define instance-specific
    # hooks instead of hardcoding that kind of logic here
    membership_item = InventoryItem.select().where(InventoryItem.special_meaning=='membership').dicts()[0]
    propose_membership = workorder.client is not None and \
        (workorder.client.membership_paid_until is None or \
         test_past(workorder.client.membership_paid_until)) and \
         not workorder.items.where(WorkorderItem.inventory_item_id == membership_item['id']).exists()

    # Hide bike infos for direct sales (client_id IS NULL), unless the info has been
    # filled
    show_bike_infos = workorder.client is not None or \
        workorder.bike_description or workorder.bike_serial_number or \
        workorder.invoice_notes or workorder.internal_notes
    # TODO : Also show if the status is not a default one?

    return render_template('workorder.html',
                           workorder=workorder,
                           show_bike_infos=show_bike_infos,
                           last_bike=last_bike,
                           items=items,
                           statuses=statuses,
                           refunded=refunded,
                           quick_items=quick_items,
                           membership_item=membership_item,
                           propose_membership=propose_membership,
                           tax1_name=config.taxes[0][0],
                           tax2_name=config.taxes[1][0],
                           client=client)

@app.route('/workorder/receipt/<int:workorder_id>')
def workorder_receipt(workorder_id):

    workorder = Workorder.select().where(Workorder.id == workorder_id).get()

    return render_template('receipt.html',
                            workorder=workorder)

@app.route('/workorder/email-receipt/<int:workorder_id>')
def workorder_email_receipt(workorder_id):
    workorder = get_object_or_404(Workorder, (Workorder.id==workorder_id))
    client = workorder.client

    if client is None:
        abort(403)

    if client.email == "":
        abort(403)

    if not client.email_consent:
        abort(403)

    recipient = client.email

    msg = Message("Receipt",
        recipients=[recipient])

    contenu = render_template('email-receipt.html',
                            workorder=workorder,
                            client=client)
    msg.html = contenu
    mail.send(msg)
    flash(f'The email was send to {client.email}', 'success')
    return redirect("/")


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

@app.route('/workorder/pay/<int:workorder_id>', methods=['POST'])
def pay_workorder(workorder_id):

    # TODO : handle multiple transactions at once

    # Partial payments might not be authorized, to avoid corner cases
    # where someone would have partially paid more than the final
    # total price
    #
    # Deposits could be handled as a separate process that is not
    # attached to a specific workorder, only to a client account

    payment_method = request.form['payment_method']

    workorder = get_object_or_404(Workorder, (Workorder.id==workorder_id))

    # Don't re-pay the same workorder twice and don't allow empty
    # workorders to be paid
    if workorder.paid:
        abort(403, "This workorder has already been paid.")

    if not workorder.items.count():
        abort(403, "This workorder is empty.")


    workorder.set_paid()
    workorder.save()

    # Note : 0$ workorders are allowed (as long as there is at least
    # one item), but no transaction should be recorded
    #
    # A "paid" 0$ workorder is a closed free workorder
    if workorder.paid_total != 0:
        Transaction.create(
            amount=workorder.paid_total,
            payment_method=payment_method,
            workorder_id=workorder_id,
        )

    flash(f'Payment successful : {workorder.paid_total}$ ({payment_method})', 'success')

    return redirect(f'/workorder/{workorder_id}')

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

    items_sold = InventoryItem.select(InventoryItem.name, fn.sum(WorkorderItem.nb).alias("total_sold"))\
                            .join(WorkorderItem, on=(InventoryItem.id == WorkorderItem.inventory_item_id))\
                            .join(Workorder, on=(WorkorderItem.workorder_id == Workorder.id))\
                            .where((InventoryItem.type == "article") & (Workorder.paid) & (fn.DATE(Workorder.paid_date).between(date_start, date_end)))\
                            .group_by(InventoryItem.id)\
                            .order_by(fn.sum(WorkorderItem.nb).desc())

    print(items_sold)

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
                           tax2_name=config.taxes[1][0],
                           tax1_rate=Decimal(config.taxes[0][1]),
                           tax2_rate=Decimal(config.taxes[1][1]),
                           items_sold=items_sold)

@app.route('/cash-register/', methods=['POST', 'GET'])
def cash_register():
    payment_methods = {'cash': Decimal(0), 'interac': Decimal(0), 'visa': Decimal(0)}
    last_cash_open = CashRegisterState.select().order_by(CashRegisterState.id.desc()).get()

    for method in payment_methods.keys():
        transactions = Transaction.select().where((Transaction.payment_method == method) & \
                                                (Transaction.created > (last_cash_open.state_time)))
        for t in transactions:
            payment_methods[method] += t.amount

    if request.method == 'POST':
        form = request.form
        register = CashRegisterState()

        if 'cash_fund' in form.keys():
            for method in payment_methods.keys():
                register.__setattr__(f'expected_{method}', payment_methods[method])
                register.__setattr__(f'confirmed_{method}', form[method])

            register.comment = form['comment'] if len(form['comment'].strip()) > 0 else None
            register.save()

            Transaction.create(
                amount=form['cash_fund'],
                payment_method='cash',
                comment="Cash fund"
            )

            flash("Cash register closed successfully", 'info')

        else:
            amount = round(Decimal(form['amount']), 2)

            if form['deposit'] == 'withdrawal':
                amount = -amount

            Transaction.create(
                amount=amount,
                payment_method='cash',
                comment=form['comment']
            )

            flash(f"Cash {form['deposit'].capitalize()} of {format_currency(abs(amount))} recorded", 'success')

        return redirect('/cash-register/')

    last_cash_open = humandate(last_cash_open.state_time, "%d %b %Y %H:%M")

    return render_template('cash-register.html',
                             date=last_cash_open,
                             payment_methods = payment_methods,
                             )


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
        try:
            value = datetime.datetime.fromisoformat(value)
        except:
            print('ERROR', model, id, column, value)
            abort(403)
    

    allowed_columns = klass.editable_cols()

    if column not in allowed_columns:
        abort(403)

    klass.update({column: value}).where(klass.id == id).execute()

    return jsonify(True)

@app.route('/api/total/<int:workorder_id>')
def get_workorder_total_infos(workorder_id):

    workorder = get_object_or_404(Workorder, (Workorder.id==workorder_id))
    total_workorder_items = workorder.items.count()

    return jsonify({
        'subtotal': round(workorder.subtotal(), 2),
        'discount': round(workorder.total_discounts(), 2),
        'taxes1': round(workorder.taxes1(), 2),
        'taxes2': round(workorder.taxes2(), 2),
        'taxes': round(workorder.taxes(), 2),
        'total': round(workorder.total(), 2),
        'nb_items': total_workorder_items,
        'workorder_paid': workorder.paid,
    })

@app.route('/api/add-item/<int:workorder_id>/<int:inventory_item_id>')
def add_item(workorder_id, inventory_item_id):


    workorder = get_object_or_404(Workorder, (Workorder.id==workorder_id))
    inventory_item = get_object_or_404(InventoryItem, (InventoryItem.id==inventory_item_id))

    # We shouldn't modify an invoice once it's paid
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

    # XXX DUPLICATED IN TEMPLATES
    TYPEAHEAD_LIMIT = 20

    # TODO : Normalize accents
    # " is stored as '' in the actual data
    # . and , should mean the same thing for numbers

    terms = list(extract_terms(query))[:3]

    if not terms:
         return jsonify({
             'results': [],
             'total_count': 0,
         })

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

    total_count = q.count()

    if 'full' not in request.args:
        q = q.limit(TYPEAHEAD_LIMIT)

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

    return jsonify({
        'results': sorted_results,
        'total_count': total_count,
    })


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

@app.route('/api/refund/', methods=['POST'])
def api_refund():

    data = json.loads(request.form['items'])

    refunded_items_id = data['refunded_items_id']
    old_workorder_id = data['workorder_id']
    old_workorder = get_object_or_404(Workorder, (Workorder.id==old_workorder_id))

    # Checks if the items have already been refuned
    workorder_items = []
    for item_id in refunded_items_id:
        workorder_item = get_object_or_404(WorkorderItem, (WorkorderItem.id==item_id))
        if not workorder_item.serialized()['refunded_in_workorder_id'] and workorder_item.refund_item_id is None:
            workorder_items.append(workorder_item)

    if len(workorder_items) == 0 or not old_workorder.paid:
        return '/' # current_workorder

    # Creates new workorder based on the original workorder
    new_workorder = Workorder.create(
        client_id=old_workorder.client_id,
        bike_description=old_workorder.bike_description,
        bike_serial_number=old_workorder.bike_serial_number,
        invoice_notes=old_workorder.invoice_notes,
        internal_notes=old_workorder.internal_notes,
    )

    for item in workorder_items:
        WorkorderItem.create(
                    name=item.name,
                    nb = -item.nb,
                    price= item.price,
                    orig_price= item.price,
                    taxable=item.taxable,
                    refund_item_id=item.id,
                    workorder_id=new_workorder.id, inventory_item_id=item.inventory_item_id
                )


    return '/workorder/' + str(new_workorder.id)

