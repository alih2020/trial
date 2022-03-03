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
                0: '',
                1: 'item',
                2: 'labor',
                3: '',
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

        # FIXME
        InventoryItem.update(special_meaning='membership').where(InventoryItem.id==71).execute()

def import_workorders():

    all_statuses = {}

    with open('migration/dump-WorkorderStatus.pickle', 'rb') as f:
        for status in pickle.load(f):
            all_statuses[status['workorderStatusID']] = status['name']


    all_serialized = {}

    with open('migration/dump-Serialized.pickle', 'rb') as f:
         for serialized in pickle.load(f):
             bike_description = (serialized['description'].strip() + ' ' +
                                 serialized['colorName'].strip() + ' ' +
                                 serialized['sizeName'].strip()).strip()
             bike_serial_number = serialized['serial'].strip()
             all_serialized[serialized['serializedID']] = (bike_description, bike_serial_number)

    all_sales = {}
    with open('migration/dump-Sale.pickle', 'rb') as f:
        for sale in pickle.load(f):
            all_sales[sale['saleID']] = sale

    all_sale_lines = {}
    with open('migration/dump-SaleLine.pickle', 'rb') as f:
        for line in pickle.load(f):
            all_sale_lines[line['saleLineID']] = line
            assert line['tax1Rate'] in ['0', '0.05']
            assert line['tax2Rate'] in ['0', '0.09975']

    all_sale_payments = {}
    with open('migration/dump-SalePayment.pickle', 'rb') as f:
        for payment in pickle.load(f):
            all_sale_payments[payment['salePaymentID']] = payment

    all_payment_types = {}
    with open('migration/dump-PaymentType.pickle', 'rb') as f:
        for payment in pickle.load(f):
            all_payment_types[payment['paymentTypeID']] = payment

    all_payment_types = {}
    with open('migration/dump-PaymentType.pickle', 'rb') as f:
        for payment in pickle.load(f):
            all_payment_types[payment['paymentTypeID']] = payment

    print(all_sales['170'])
    print(all_sale_lines['170'])
    print(all_sale_payments['170'])

    print()
    print()

    with open('migration/dump-Workorder.pickle', 'rb') as f:

        all_rows = []

        all_workorders = pickle.load(f)

        for workorder in all_workorders:

            w = {}

            w['id'] = int(workorder['workorderID'])

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

            w['client_id'] = None
            if workorder['customerID'] != '0':
                w['client_id'] = int(workorder['customerID'])

            w['status'] = all_statuses[workorder['workorderStatusID']]
            w['archived'] = workorder['archived'] == 'true'

            # TODO TODO TODO
            w['paid'] = False
            w['payment_method'] = None

            w['paid_subtotal'] = None
            w['paid_tax1_rate'] = None
            w['paid_tax2_rate'] = None
            w['paid_taxes1'] = None
            w['paid_taxes2'] = None
            w['paid_total'] = None
            w['paid_date'] = None


            if workorder['saleID'] != '0':

                sale = all_sales[workorder['saleID']]

                if sale['completed'] != 'true' or 'SalePayments' not in sale:
                    print('incomplete', w['id'])
                    continue

                if type(sale['SalePayments']['SalePayment']) == dict:
                    sale_payment_id = sale['SalePayments']['SalePayment']['salePaymentID']
                    sale_payment = all_sale_payments[sale_payment_id]

                    amount_paid = sale_payment['amount']
                    payment_method = all_payment_types[sale_payment['paymentTypeID']]['name']
                    paid_date = sale_payment['createTime']

                elif type(sale['SalePayments']['SalePayment']) == list:
                    # TODO TODO TODO
                    print('TODO')
                    print(sale['SalePayments']['SalePayment'])
                    amount_paid = sum(Decimal(x['amount']) for x in sale['SalePayments']['SalePayment'])
                    payment_method = 'Mixed'
                    paid_date = sale['SalePayments']['SalePayment'][0]['createTime']
                else:
                    assert False

                w['paid_subtotal'] = Decimal(sale['calcSubtotal']) - Decimal(sale['calcDiscount'])
                w['paid_tax1_rate'] = sale['tax1Rate']
                w['paid_tax2_rate'] = sale['tax2Rate']
                w['paid_taxes1'] = sale['calcTax1']
                w['paid_taxes2'] = sale['calcTax2']
                w['paid_total'] = sale['calcTotal']

                assert round(Decimal(w['paid_total']), 2) == round(Decimal(amount_paid), 2)

                w['paid'] = True
                w['payment_method'] = payment_method
                w['paid_date'] = paid_date

            this_row = (
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

                w['paid'],
                w['payment_method'],
                w['paid_date'],
            )

            all_rows.append(this_row)


        Workorder.insert_many(all_rows, fields=(
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
            Workorder.paid,
            Workorder.payment_method,
            Workorder.paid_date,
        )).execute()


    all_rows = []

    for fname in ['migration/dump-WorkorderLine.pickle', 'migration/dump-WorkorderItem.pickle']:

        print(fname)
        with open(fname, 'rb') as f:

            all_workorderlines = pickle.load(f)

            for item in all_workorderlines:

                # TODO TODO TODO
                if item['itemID'] == '0':
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
