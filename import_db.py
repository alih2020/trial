#!/usr/bin/env python3

import re
import datetime
from models import *
import config
import json
import pickle
from decimal import Decimal

def where(lst, field, value):
    for row in lst:
        if field in row and row[field] == value:
            return row
    return None

def all_where(lst, field, value):
    return [x for x in lst if x[field] == value]

def todt(d):
    x = datetime.datetime.fromisoformat(d).astimezone()
    return x.replace(tzinfo=None)


def import_clients():
    with open('migration/dump-Customer.pickle', 'rb') as f:
        all_rows = []

        all_customers = pickle.load(f)

        for customer in all_customers:

            def get(field):
                return customer[field]

            c = {}

            c['id'] = int(get('customerID'))
            c['first_name'] = get('firstName').strip()
            c['last_name'] = get('lastName').strip()

            _contact = get('Contact')
            _contact_address = _contact['Addresses']['ContactAddress']
            c['address'] = (_contact_address['address1'].strip() + ' ' + _contact_address['address2']).strip()
            c['postal_code'] = _contact_address['zip'].strip()
            _contact_address

            c['phone'] = ''

            if _contact['Phones'] != '':
                _contact_phone = _contact['Phones']['ContactPhone']

                if type(_contact_phone) == dict:
                    # Only one number == phone
                    c['phone'] = _contact_phone['number'].strip()
                elif type(_contact_phone) == list:
                    # Home, then Mobile, then whatever
                    maybe_phone = where(_contact_phone, 'useType', 'Home')

                    if maybe_phone:
                        c['phone'] = maybe_phone['number'].strip()
                    else:
                        maybe_phone = where(_contact_phone, 'useType', 'Mobile')

                        if maybe_phone:
                            c['phone'] = maybe_phone['number'].strip()
                        else:
                            c['phone'] = _contact_phone[0]['number'].strip()

            c['email'] = ''

            if _contact['Emails'] == '':
                # No email
                pass
            elif type(_contact['Emails']['ContactEmail']) == dict:
                c['email'] = _contact['Emails']['ContactEmail']['address'].strip()
            elif type(_contact['Emails']['ContactEmail']) == list:
                row = where(_contact['Emails']['ContactEmail'], 'useType', 'Primary')

                if row is None:
                    c['email'] = _contact['Emails']['ContactEmail'][0]['address'].strip()
                else:
                    c['email'] = row['address']

            c['internal_notes'] = (customer['Note']['note'] if 'Note' in customer else '').strip()

            c['email_consent'] = _contact['noEmail'] == 'false'

            c['year_of_birth'] = None

            if 'dob' in customer:
                date_of_birth = datetime.datetime.fromisoformat(get('dob'))
                c['year_of_birth'] = date_of_birth.year

            c['created'] = todt(customer['createTime'])

            c['membership_paid_until'] = None
            if 'CustomFieldValues' in customer:
                custom_fields = get('CustomFieldValues')['CustomFieldValue']
                if type(custom_fields) == dict:
                    if custom_fields['name'] == "Date de renouvellement de l'abonnement" \
                       and 'value' in custom_fields:
                        c['membership_paid_until'] = todt(custom_fields['value'])
                elif type(custom_fields) == list:
                    row = where(custom_fields, 'name', "Date de renouvellement de l'abonnement")

                    if row is not None and 'value' in row:
                        c['membership_paid_until'] = todt(row['value'])
                else:
                    assert False, str(type(get('CustomFieldValues')))

            # c['all_infos'] = json.dumps(customer)

            c['archived'] = customer['archived'] == 'true'

            # Strip everything
            for key in c:
                if type(c[key]) == str:
                    c[key] = c[key].strip()

            this_row = (
                c['id'],
                c['first_name'],
                c['last_name'],
                c['address'],
                c['postal_code'],
                c['phone'],
                c['email'],
                c['email_consent'],
                c['year_of_birth'],
                c['internal_notes'],
                c['membership_paid_until'],
                c['created'],
                c['archived'],
            )

            all_rows.append(this_row)

        Client.insert_many(all_rows, fields=(
            Client.id,
            Client.first_name,
            Client.last_name,
            Client.address,
            Client.postal_code,
            Client.phone,
            Client.email,
            Client.email_consent,
            Client.year_of_birth,
            Client.internal_notes,
            Client.membership_paid_until,
            Client.created,
            Client.archived,
        )).execute()

def import_inventory_items():

    categories = {}
    subcat2cat = {}

    with open('migration/dump-Category.pickle', 'rb') as f:
        all_categories = pickle.load(f)
        for category in all_categories:
            categories[category['categoryID']] = category['name']

        for category in all_categories:
            if category['nodeDepth'] == '1':
                subcat2cat[category['categoryID']] = category['parentID']

    with open('migration/dump-Item.pickle', 'rb') as f:
        all_rows = []

        all_items = pickle.load(f)

        for item in all_items:

            it = {}

            it['id'] = item['itemID']

            it['cost'] = item['defaultCost']

            it['archived'] = item['archived'] == 'true'

            it['name'] = item['description']

            it['upc_code'] = item['upc']
            it['ean_code'] = item['ean']
            it['sku_code'] = (item['customSku'].strip() or item['manufacturerSku']).strip()

            assert 'Prices' in item

            list_prices = item['Prices']['ItemPrice']

            if type(list_prices) != list:
                list_prices = [list_prices]

            msrp = where(list_prices, 'useType', 'MSRP')
            if msrp is not None:
                it['msrp'] = msrp['amount']

            price = where(list_prices, 'useType', 'Default')
            if price is not None:
                it['price'] = msrp['amount']

            if len(list_prices) > 2:
                assert False, str(list_prices)

            it['taxable'] = item['tax'] == 'true'

            categoryID = item['categoryID']

            if categoryID in subcat2cat:
                it['category'] = categories[subcat2cat[categoryID]]
                it['subcategory'] = categories[categoryID]
            elif categoryID == '0':
                it['category'] = ''
                it['subcategory'] = ''
            else:
                it['category'] = categories[categoryID]
                it['subcategory'] = ''

            it['discountable'] = item['discountable'] == 'true'

            # Strip everything
            for key in it:
                if type(it[key]) == str:
                    it[key] = it[key].strip()

            #type
            it['type'] = {
                0: 'other',
                1: 'article',
                2: 'labor',
                3: 'other',
            }[int(item['taxClassID'])]

            this_row = (
                it['id'],
                it['name'],
                it['category'],
                it['subcategory'],
                it['ean_code'],
                it['upc_code'],
                it['sku_code'],
                it['price'],
                it['cost'],
                it['msrp'],
                it['taxable'],
                it['discountable'],
                it['type'],
                it['archived'],
            )

            all_rows.append(this_row)

        InventoryItem.insert_many(all_rows, fields=(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.category,
            InventoryItem.subcategory,
            InventoryItem.ean_code,
            InventoryItem.upc_code,
            InventoryItem.sku_code,
            InventoryItem.price,
            InventoryItem.cost,
            InventoryItem.msrp,
            InventoryItem.taxable,
            InventoryItem.discountable,
            InventoryItem.type,
            InventoryItem.archived,
        )).execute()

        # FIXME : not quite the right item, memberships are weirder than expected
        InventoryItem.update(special_meaning='membership').where(InventoryItem.id==71).execute()

        # Special item : "custom" to add an arbitrary item to the sale
        InventoryItem(
            name="",
            category="",
            subcategory="",
            ean_code="",
            upc_code="",
            sku_code="",
            price='0',
            cost='0',
            msrp='0',
            taxable=True,
            discountable=False,
            type='other',
            special_meaning='custom').save()

        # Special item : 0$ thing, only a label to be displayed on the
        # invoice
        InventoryItem(
            name="",
            category="",
            subcategory="",
            ean_code="",
            upc_code="",
            sku_code="",
            price='0',
            cost='0',
            msrp='0',
            taxable=True,
            discountable=False,
            type='other',
            special_meaning='label').save()


def import_workorders():

    all_sales_by_id = {}
    with open('migration/dump-Sale.pickle', 'rb') as f:
        for sale in pickle.load(f):
            all_sales_by_id[sale['saleID']] = sale

    all_workorders_by_sale_id = {}
    with open('migration/dump-Workorder.pickle', 'rb') as f:
        for workorder in pickle.load(f):

            sale_id = int(workorder['saleID'])

            if sale_id not in all_workorders_by_sale_id:
                all_workorders_by_sale_id[sale_id] = []

            all_workorders_by_sale_id[sale_id].append(workorder)

    all_sale_lines_by_id = {}
    with open('migration/dump-SaleLine.pickle', 'rb') as f:
        for line in pickle.load(f):
            all_sale_lines_by_id[line['saleLineID']] = line

    all_status_rows = []
    status_done_id = None

    all_statuses = {}

    with open('migration/dump-WorkorderStatus.pickle', 'rb') as f:
        for status in pickle.load(f):
            all_statuses[status['workorderStatusID']] = status['name']

            display_order = int(status['sortOrder'])

            if display_order == 0:
                display_order = 9999

            if status['name'] == 'Done & Paid':
                status_done_id = int(status['workorderStatusID'])

            all_status_rows.append((
                int(status['workorderStatusID']),
                status['name'],
                status['htmlColor'] or '#CCCCCC',
                display_order
            ))

        WorkorderStatus.insert_many(all_status_rows, fields=(
            WorkorderStatus.id,
            WorkorderStatus.name,
            WorkorderStatus.color,
            WorkorderStatus.display_order,
        )).execute()

        statuses = WorkorderStatus.select().order_by(WorkorderStatus.display_order.asc())

        for order, status in enumerate(statuses):
            status.display_order = order
            status.save()

    all_serialized = {}

    with open('migration/dump-Serialized.pickle', 'rb') as f:
         for serialized in pickle.load(f):
             bike_description = (serialized['description'].strip() + ' ' +
                                 serialized['colorName'].strip() + ' ' +
                                 serialized['sizeName'].strip()).strip()
             bike_serial_number = serialized['serial'].strip()
             all_serialized[serialized['serializedID']] = (bike_description, bike_serial_number)

    all_sale_payments = {}
    with open('migration/dump-SalePayment.pickle', 'rb') as f:
        for payment in pickle.load(f):
            all_sale_payments[payment['salePaymentID']] = payment

    all_payment_types = {}
    with open('migration/dump-PaymentType.pickle', 'rb') as f:
        for payment in pickle.load(f):
            all_payment_types[payment['paymentTypeID']] = payment

    with open('migration/dump-Workorder.pickle', 'rb') as f:
        all_workorders = pickle.load(f)

    """
    Importation :

    - sales become workorders, except unpaid sales
    - workorders that are not yet attached to a sale (open orders) are
      imported, unless they are too old to be relevant

    For the IDs :

    Sales :
    - w['id'] = saleID
    Open workorders :
    - w['id'] = workorderID + max(saleID)

    """

    max_sale_id = 0

    incomplete_sales = set()

    # This looks good, double-checked on 2022-02-03
    with open('migration/dump-Sale.pickle', 'rb') as f:

        all_sale_rows = []
        all_transaction_rows = []

        all_sales = pickle.load(f)

        for sale in all_sales:

            # Sale that was started but not completed -- Skip it
            if sale['completed'] != 'true': # or 'SalePayments' not in sale:

                if todt(sale['updateTime']) > datetime.datetime.now() - datetime.timedelta(days=30):
                    print('WARNING: sale #' + str(w['id']), 'is RECENT (< 30 days old) and is still open, but it will NOT be imported')

                incomplete_sales.add(int(sale['saleID']))
                continue

            w = {}

            w['id'] = int(sale['saleID'])
            max_sale_id = max(max_sale_id, w['id'])

            w['client_id'] = None

            if sale['customerID'] != '0':
                w['client_id'] = int(sale['customerID'])

            w['created'] = todt(sale['createTime'])
            w['updated'] = todt(sale['updateTime'])
            w['archived'] = sale['archived'] == 'true'

            # Fetch all workorders
            workorders = []
            if w['id'] in all_workorders_by_sale_id:
                workorders = all_workorders_by_sale_id[w['id']]

            # XXX: Maybe remove zero-line workorders?
            # workorders = [w for w in workorders if 'WorkorderItems' in w.keys()]

            # No associated workorder : direct sale, no bike
            if len(workorders) == 0:

                w['bike_description'] = ''
                w['bike_serial_number'] = ''
                w['calendar_date'] = w['updated']
                w['status'] = status_done_id
                w['invoice_notes'] = ''
                w['internal_notes'] = ''

            elif len(workorders) == 1:
                # One workorder : copy infos

                workorder = workorders[0]

                assert workorder['customerID'] == sale['customerID']

                w['invoice_notes'] = workorder['note']
                w['internal_notes'] = workorder['internalNote']

                w['bike_description'] = ''
                w['bike_serial_number'] = ''

                if workorder['serializedID'] in all_serialized:
                    w['bike_description'], w['bike_serial_number'] = all_serialized[workorder['serializedID']]

                w['internal_notes'] = workorder['internalNote']

                w['created'] = todt(workorder['timeIn']) if 'timeIn' in workorder else todt(workorder['timeStamp'])
                w['updated'] = todt(workorder['timeStamp'])
                w['calendar_date'] = todt(workorder['etaOut']) if 'etaOut' in workorder else todt(workorder['timeStamp'])

                w['status'] = int(workorder['workorderStatusID'])

            else:
                print('INFO: Multiple workorders paid with sale #' + str(w['id']))
                # Multiple workorders : concatenate all bike descriptions/notes
                bike_descriptions = []
                bike_serial_numbers = []
                for workorder in workorders:

                    assert workorder['customerID'] == sale['customerID']

                    if workorder['serializedID'] in all_serialized:
                        bike_description, bike_serial_number = all_serialized[workorder['serializedID']]
                        bike_descriptions.append(bike_description)
                        bike_serial_numbers.append(bike_serial_number)

                    assert all_statuses[workorder['workorderStatusID']] == 'Done & Paid'


                def join_fields(field, sep):
                    return sep.join([w[field].strip() for w in workorders if w[field].strip()])

                w['invoice_notes'] = join_fields('note', '\n---\n')
                w['internal_notes'] = join_fields('internalNote', '\n---\n')

                w['bike_description'] = ' -- '.join([bd.strip() for bd in bike_descriptions if bd.strip()])
                w['bike_serial_number'] = ' -- '.join([bs.strip() for bs in bike_serial_numbers if bs.strip()])

                w['created'] = min([todt(w['timeIn'] if 'timeIn' in w else w['timeStamp']) for w in workorders])
                w['updated'] = max([todt(w['timeStamp']) for w in workorders])
                w['calendar_date'] = max([todt(w['etaOut'] if 'etaOut' in w else w['timeStamp']) for w in workorders])

                w['status'] = status_done_id

            # Transactions
            if 'SalePayments' not in sale and 'SaleLines' not in sale:

                # SKIP: No payment + No items in the sale, not sure why this
                # is happening, ignore it

                continue

            elif 'SalePayments' not in sale:

                # 0$ Sale that was closed, archive the workorder
                # print('0$ payment for id', w['id'], "-->", sale['tax1Rate'], sale['tax2Rate'])

                total_amount_paid = Decimal('0.00')

                assert Decimal(sale['calcTax1']) == Decimal('0.00')
                assert Decimal(sale['calcTax2']) == Decimal('0.00')
                assert Decimal(sale['calcTotal']) == Decimal('0.00')

                paid_date = w['updated']

            elif type(sale['SalePayments']['SalePayment']) == dict:

                # Sale closed in one transaction

                sale_payment_id = sale['SalePayments']['SalePayment']['salePaymentID']
                sale_payment = all_sale_payments[sale_payment_id]

                amount_paid = round(Decimal(sale_payment['amount']), 2)
                total_amount_paid = amount_paid
                payment_method = all_payment_types[sale_payment['paymentTypeID']]['name'].lower()
                paid_date = todt(sale_payment['createTime'])

                all_transaction_rows.append((
                    sale_payment_id,
                    amount_paid,
                    payment_method,
                    w['id'],
                    paid_date,
                ))
                assert payment_method in Transaction.TRANSACTION_TYPES

            elif type(sale['SalePayments']['SalePayment']) == list:

                # Sale closed in multiple transactions

                total_amount_paid = Decimal('0.00')

                max_paid_date = todt(sale['SalePayments']['SalePayment'][-1]['createTime'])

                for json_sale_payment in sale['SalePayments']['SalePayment']:
                    sale_payment_id = json_sale_payment['salePaymentID']
                    sale_payment = all_sale_payments[sale_payment_id]

                    amount_paid = Decimal(sale_payment['amount'])
                    total_amount_paid += amount_paid

                    payment_method = all_payment_types[sale_payment['paymentTypeID']]['name'].lower()

                    paid_date = todt(sale_payment['createTime'])
                    max_paid_date = max(paid_date, max_paid_date)

                    all_transaction_rows.append((
                        sale_payment_id,
                        round(Decimal(amount_paid), 2),
                        payment_method,
                        w['id'],
                        paid_date,
                    ))

                    assert payment_method in Transaction.payment_method.choices

                paid_date = max_paid_date
            else:
                assert False

            w['paid_subtotal'] = round(Decimal(sale['calcSubtotal']) - Decimal(sale['calcDiscount']), 2)
            w['paid_tax1_rate'] = Decimal(sale['tax1Rate'])
            w['paid_tax2_rate'] = Decimal(sale['tax2Rate'])
            w['paid_taxes1'] = round(Decimal(sale['calcTax1']), 2)
            w['paid_taxes2'] = round(Decimal(sale['calcTax2']), 2)
            w['paid_total'] = round(Decimal(sale['calcTotal']), 2)

            assert w['paid_total'] == round(Decimal(total_amount_paid), 2)

            w['paid_date'] = paid_date

            all_sale_rows.append((
                w['id'],
                w['client_id'],
                w['bike_description'],
                w['bike_serial_number'],
                w['calendar_date'],
                w['status'],
                w['invoice_notes'],
                w['internal_notes'],
                w['created'],
                w['updated'],
                w['archived'],

                w['paid_subtotal'],
                w['paid_tax1_rate'],
                w['paid_tax2_rate'],
                w['paid_taxes1'],
                w['paid_taxes2'],
                w['paid_total'],

                w['paid_date'],
            ))

        Workorder.insert_many(all_sale_rows, fields=(
            Workorder.id,
            Workorder.client,
            Workorder.bike_description,
            Workorder.bike_serial_number,
            Workorder.calendar_date,
            Workorder.status,
            Workorder.invoice_notes,
            Workorder.internal_notes,
            Workorder.created,
            Workorder.updated,
            Workorder.archived,
            Workorder.paid_subtotal,
            Workorder.paid_tax1_rate,
            Workorder.paid_tax2_rate,
            Workorder.paid_taxes1,
            Workorder.paid_taxes2,
            Workorder.paid_total,
            Workorder.paid_date,
        )).execute()

        Transaction.insert_many(all_transaction_rows, fields=(
            Transaction.id,
            Transaction.amount,
            Transaction.payment_method,
            Transaction.workorder_id,
            Transaction.created,
        )).execute()


    # An imported "WorkorderItem" is a part that was required for a repair
    # An imported "WorkorderLine" is typically a task
    # Both offer the same data
    with open('migration/dump-WorkorderLine.pickle', 'rb') as f1:
        with open('migration/dump-WorkorderItem.pickle', 'rb') as f2:
            all_workorderlines = pickle.load(f1) + pickle.load(f2)

    # Two fake InventoryItems :
    # - custom: anything, changes every time
    # - label: a 0$ item that is used to write down a row on a receipt
    custom_item_id = InventoryItem.select(InventoryItem.id).where(InventoryItem.special_meaning=='custom').get().id
    label_id = InventoryItem.select(InventoryItem.id).where(InventoryItem.special_meaning=='label').get().id


    all_workorderitems = []

    # Import all items that were part of a sale
    with open('migration/dump-SaleLine.pickle', 'rb') as f:
        for item in pickle.load(f):

            # All items are either taxed with TPS/TVQ, or de-taxed
            assert item['tax1Rate'] in ['0', '0.05']
            assert item['tax2Rate'] in ['0', '0.09975']

            if item['saleID'] == '0':
                # SKIP : Sale line detached from any sale.  Not clear
                # why this is happening
                # print('WARNING: Sale line of saleID=0:', item['saleLineID'])
                continue

            w = {}
            w['id'] = item['saleLineID']
            w['workorder_id'] = int(item['saleID'])

            # Some SaleLines are part of an incomplete sale, which are
            # not imported
            if Workorder.select().where(Workorder.id == w['workorder_id']).count() == 0:
                assert w['workorder_id'] in incomplete_sales
                continue

            w['inventory_item_id'] = int(item['itemID'])

            # Non-items : either a label or a custom item
            if w['inventory_item_id'] == 0:
                if 'Note' in item:
                    # We're not selling workorders... This is a hack
                    # to write stuff down on receipts
                    is_label = item['Note']['note'].startswith('Work order #')

                    if is_label:
                        w['inventory_item_id'] = label_id
                        # print('XXX', 'Label on', item['saleID'], item['unitPrice'])
                        assert Decimal(item['unitPrice']) == 0
                    else:
                        w['inventory_item_id'] = custom_item_id
                        # if Decimal(item['unitPrice']) == 0:
                        #     print('XXX', 'Custom on', item['saleID'], item['unitPrice'], 'with price 0')

                    name = item['Note']['note']
                else:
                    # parentSaleLineID == item being refunded
                    assert 'parentSaleLineID' in item

                    # TODO : The original line description could be
                    # used as the name
                    name = 'Refund'
                    w['inventory_item_id'] = custom_item_id
                    print('WARNING:', 'Refund on custom item in sale', item['saleID'])
            else:
                assert InventoryItem.select().where(InventoryItem.id == w['inventory_item_id']).count() == 1
                orig_item = InventoryItem.get(id=w['inventory_item_id'])
                name = orig_item.name

            """Problèmes ici... sum(sous-total taxé de chaque item) != total

            Le sous-total ligne de chaque item n'est pas fiable à
            cause des arrondissements, c'est utilisé uniquement pour
            l'affichage

            Plus d'explications ici
            https://gitlab.com/316k/minipos/-/blob/cc66f307/models.py#L197

            """
            if item['discountAmount'] != '0' or item['discountPercent'] != '0':
                # Unit cost after discount
                price = Decimal(item['displayableSubtotal']) / Decimal(item['unitQuantity'])
            else:
                price = item['unitPrice']

            w['price'] = price
            w['orig_price'] = item['unitPrice']
            w['nb'] = item['unitQuantity']

            # Taxes
            w['taxable'] = item['tax'] == 'true'
            assert item['tax'] in ['true', 'false']

            if w['taxable'] and (item['tax1Rate'] == '0' or item['tax2Rate'] == '0'):
                """Il y a deux instances d'items *taxés* à 0%

                - http://127.0.0.1:5000/workorder/3339
                - http://127.0.0.1:5000/workorder/3390

                Bien qu'il y a des cas réels où un item peut être *taxé* à
                *0%* mais PAS *détaxé*, le cas des pièces de vélo semble
                être une erreur d'entrée de données

                """

                # Cas d'erreurs d'entrées qui ont été validées à la main
                assert w['workorder_id'] in [3339, 3390]
                w['taxable'] = False

            w['name'] = name.strip()

            workorder_lines = all_where(all_workorderlines, 'saleLineID', item['saleLineID'])
            assert len(workorder_lines) in [0, 1]

            if workorder_lines:
                workorder_line = workorder_lines[0]

                addons = []

                # The note is already used for Label and Custom items
                if workorder_line['note'] and workorder_line['note'] != 'Labor':
                    addons.append(workorder_line['note'].replace('\n', '--').strip())

                if workorder_line['warranty'] == 'true':
                    addons.append('WARRANTY')

                w['name'] = ' - '.join([w['name']] + addons).strip()


            assert w['name'] != 'LaborLabor'

            w['refund_item_id'] = None

            if item['parentSaleLineID'] != '0':
                w['refund_item_id'] = int(item['parentSaleLineID'])

            this_row = (
                w['id'],
                w['workorder_id'],
                w['inventory_item_id'],
                w['name'],
                w['nb'],
                w['price'],
                w['orig_price'],
                w['taxable'],
                w['refund_item_id'],
            )

            all_workorderitems.append(this_row)

        WorkorderItem.insert_many(all_workorderitems, fields=(
            WorkorderItem.id,
            WorkorderItem.workorder,
            WorkorderItem.inventory_item,
            WorkorderItem.name,
            WorkorderItem.nb,
            WorkorderItem.price,
            WorkorderItem.orig_price,
            WorkorderItem.taxable,
            WorkorderItem.refund_item,
        )).execute()


    open_workorders_ids = []

    with open('migration/dump-Workorder.pickle', 'rb') as f:

        all_workorders_rows = []

        all_workorderline_rows = []

        all_workorders = pickle.load(f)

        for workorder in all_workorders:

            # Import all open workorders more recent than two months
            if workorder['saleID'] != '0' or \
               'timeIn' not in workorder or \
               todt(workorder['timeIn']) < datetime.datetime.now() - datetime.timedelta(days=63):
                # Skip everything else
                continue

            w = {}

            w['id'] = max_sale_id + int(workorder['workorderID'])

            open_workorders_ids.append(int(workorder['workorderID']))

            w['invoice_notes'] = workorder['note']
            w['internal_notes'] = workorder['internalNote']

            w['bike_description'] = ''
            w['bike_serial_number'] = ''

            if workorder['serializedID'] in all_serialized:
                w['bike_description'], w['bike_serial_number'] = all_serialized[workorder['serializedID']]

            w['created'] = todt(workorder['timeIn']) if 'timeIn' in workorder else todt(workorder['timeStamp'])
            w['updated'] = todt(workorder['timeStamp'])
            w['calendar_date'] = todt(workorder['etaOut']) if 'etaOut' in workorder else todt(workorder['timeStamp'])

            w['client_id'] = None
            if workorder['customerID'] != '0':
                w['client_id'] = int(workorder['customerID'])

            w['status'] = workorder['workorderStatusID']
            w['archived'] = workorder['archived'] == 'true'

            all_workorders_rows.append((
                w['id'],
                w['client_id'],
                w['bike_description'],
                w['bike_serial_number'],
                w['calendar_date'],
                w['status'],
                w['invoice_notes'],
                w['internal_notes'],
                w['created'],
                w['updated'],
                w['archived'],
            ))

            # if workorder['workorderID'] == '4118':
            #     print(workorder)
            #     print(w)

        Workorder.insert_many(all_workorders_rows, fields=(
            Workorder.id,
            Workorder.client,
            Workorder.bike_description,
            Workorder.bike_serial_number,
            Workorder.calendar_date,
            Workorder.status,
            Workorder.invoice_notes,
            Workorder.internal_notes,
            Workorder.created,
            Workorder.updated,
            Workorder.archived,
        )).execute()

    max_workorderitem_id = WorkorderItem.select().order_by(WorkorderItem.id.desc()).get().id

    print('max_workorderitem_id', max_workorderitem_id)

    all_workorderitems = []

    for workorder_id in open_workorders_ids:

        # Find all lines
        for item in (l for l in all_workorderlines if int(l['workorderID']) == workorder_id):

            assert item['saleID'] == '0'

            w = {}

            w['workorder_id'] = max_sale_id + workorder_id

            w['inventory_item_id'] = int(item['itemID'])

            # Non-items : either a label or a custom item
            if w['inventory_item_id'] == 0:

                # TODO: Not yet supported
                assert False

            #     if 'Note' in item:
            #         # We're not selling workorders... This is a hack
            #         # to write stuff down on receipts
            #         is_label = item['Note']['note'].startswith('Work order #')

            #         if is_label:
            #             w['inventory_item_id'] = label_id
            #             # print('XXX', 'Label on', item['saleID'], item['unitPrice'])
            #             assert Decimal(item['unitPrice']) == 0
            #         else:
            #             w['inventory_item_id'] = custom_item_id
            #             # if Decimal(item['unitPrice']) == 0:
            #             #     print('XXX', 'Custom on', item['saleID'], item['unitPrice'], 'with price 0')

            #         name = item['Note']['note']
            #     else:
            #         # parentSaleLineID == item being refunded
            #         assert 'parentSaleLineID' in item

            #         # TODO : The original line description could be
            #         # used as the name
            #         name = 'Refund'
            #         w['inventory_item_id'] = custom_item_id
            #         print('WARNING:', 'Refund on custom item in sale', item['saleID'])
            # else:
            #     assert InventoryItem.select().where(InventoryItem.id == w['inventory_item_id']).count() == 1
            #     orig_item = InventoryItem.get(id=w['inventory_item_id'])
            #     name = orig_item.name

            if 'unitPriceOverride' in item:
                price = Decimal(item['unitPriceOverride'])
            else:
                price = item['unitPrice']

            w['price'] = price
            w['nb'] = item['unitQuantity']

            assert w['inventory_item_id'] != 0
            orig_item = InventoryItem.get(InventoryItem.id == w['inventory_item_id'])
            w['orig_price'] = orig_item.price
            w['name'] = orig_item.name

            # Taxes
            w['taxable'] = item['tax'] == 'true'
            assert item['tax'] in ['true', 'false']

            addons = []

            # The note is already used for Label and Custom items
            if item['note'] and item['note'] != 'Labor':
                addons.append(item['note'].replace('\n', '--').strip())

            if 'warranty' in item and item['warranty'] == 'true':
                addons.append('WARRANTY')

            w['name'] = ' - '.join([w['name']] + addons).strip()

            assert w['name'] != 'LaborLabor'

            # It's not possible to include refund in a workorder
            # (because it's not a sale)
            w['refund_item_id'] = None

            this_row = (
                # w['id'],
                w['workorder_id'],
                w['inventory_item_id'],
                w['name'],
                w['nb'],
                w['price'],
                w['orig_price'],
                w['taxable'],
                w['refund_item_id'],
            )

            all_workorderitems.append(this_row)

    WorkorderItem.insert_many(all_workorderitems, fields=(
        # WorkorderItem.id,
        WorkorderItem.workorder,
        WorkorderItem.inventory_item,
        WorkorderItem.name,
        WorkorderItem.nb,
        WorkorderItem.price,
        WorkorderItem.orig_price,
        WorkorderItem.taxable,
        WorkorderItem.refund_item,
    )).execute()

    return

    # bad_workorders = set()
    all_rows = []

    for fname in ['migration/dump-WorkorderLine.pickle', 'migration/dump-WorkorderItem.pickle']:

        print(fname)
        with open(fname, 'rb') as f:

            all_workorderlines = pickle.load(f)

            for item in all_workorderlines:

                # TODO TODO TODO
                if item['itemID'] == '0':
                    print('wat')
                    print(item)
                    print(item['unitCost'] == '0', item['unitPriceOverride'] == '0')
                    # assert item['unitCost'] == '0' and item['unitPriceOverride'] == '0'

                    continue
                # TODO TODO TODO

                # print('wat')
                # print(item)

                w['workorder_id'] = int(item['workorderID'])
                w['inventory_item_id'] = int(item['itemID'])

                # TODO TODO TODO
                if Workorder.select().where(Workorder.id==w['workorder_id']).count() != 1:
                    print('nooooooooooooo such workorder')
                    continue
                if InventoryItem.select().where(InventoryItem.id==w['inventory_item_id']).count() != 1:
                    print('nooooooooooooo such item')
                    continue

                orig_item = InventoryItem.get(id=w['inventory_item_id'])

                sale_line_id = item['saleLineID']

                # TODO TODO TODO
                if sale_line_id == '0':
                    print('TODO 9ou2ijemd')
                    continue
                # TODO TODO TODO

                sale_line = all_sale_lines[sale_line_id]

                if sale_line['discountAmount'] != '0' or sale_line['discountPercent'] != '0':
                    # Unit cost after discount
                    price = Decimal(sale_line['displayableSubtotal']) / Decimal(sale_line['unitQuantity'])
                else:
                    price = sale_line['unitPrice']

                warranty = item['warranty'] == 'true'

                # Not sure why, but there are exceptions to this
                # if not warranty:
                #     assert item['unitPriceOverride'] == sale_line['unitPrice']

                assert item['unitQuantity'] == sale_line['unitQuantity']
                assert item['tax'] == sale_line['tax']

                w['price'] = price
                w['orig_price'] = sale_line['unitPrice']
                w['nb'] = sale_line['unitQuantity']
                w['taxable'] = sale_line['tax'] == 'true'

                assert w['inventory_item_id'] != '0'
                assert item['tax'] in ['true', 'false']

                addon = ''

                if item['note']:
                    addon = item['note'].replace('\n', '--').strip()

                if warranty:
                    addon = ' WARRANTY'

                w['name'] = (orig_item.name + addon).strip()

                this_row = (
                    w['workorder_id'],
                    w['inventory_item_id'],
                    w['name'],
                    w['nb'],
                    w['price'],
                    w['orig_price'],
                    w['taxable'],
                )

                all_rows.append(this_row)


    WorkorderItem.insert_many(all_rows, fields=(
        WorkorderItem.workorder,
        WorkorderItem.inventory_item,
        WorkorderItem.name,
        WorkorderItem.nb,
        WorkorderItem.price,
        WorkorderItem.orig_price,
        WorkorderItem.taxable,
    )).execute()

def validate_db():
    for workorder in Workorder.select():
        try:
            workorder.test_invariants()
        except AssertionError as e:
            print('Error with', workorder.id)
            print(workorder.updated, '>=', workorder.created)
            print()
            print(workorder.total(force_calc=False), 'vs', workorder.total(force_calc=True))
            print(workorder.subtotal(force_calc=False), 'vs', workorder.subtotal(force_calc=True))
            print(workorder.taxes1(force_calc=False), 'vs', workorder.taxes1(force_calc=True))
            print(workorder.taxes2(force_calc=False), 'vs', workorder.taxes2(force_calc=True))
            print()
            print(workorder.subtotal(force_calc=False) + workorder.taxes(force_calc=False), 'vs', workorder.total(force_calc=False))
            print(workorder.subtotal(force_calc=True) + workorder.taxes(force_calc=True), 'vs', workorder.total(force_calc=True))
            print()
