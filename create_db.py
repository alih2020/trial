#!/usr/bin/env python3
from models import *
import config
from import_db import *

def create_db(import_data=False):
    # ---------- Setup database ----------
    for Model in (Role, User, UserRoles):
        Model.create_table()

    Client.add_index(peewee.SQL('CREATE INDEX client_idx_first_name ON client(first_name COLLATE NOCASE)'))
    Client.add_index(peewee.SQL('CREATE INDEX client_idx_last_name ON client(last_name COLLATE NOCASE)'))

    Client.create_table()

    if import_data:
        import_clients()
    else:
        # Test data
        Client.insert_many([
            ('Jimmy', 'Whooper', '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'jimmy@example.com', 1, '', None),
            ('Alice', 'Whooper', '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'alice@example.com', 0, '', '2021-12-25 00:00:00.000000'),
            ('Theresa', 'Horton', '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'theresa@example.com', 0, '', '2020-01-01 00:00:00.000000'),
            ('Robert', 'Tackitt',  '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'robert@example.com', 0, '', '2022-12-25 00:00:00.000000'),
            ('Helen', 'Nathan',  '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'helen@example.com', 0, '', '2021-09-25 00:00:00.000000'),
            ('Robin', 'Graves',  '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'robin@example.com', 0, '', '2021-12-25 00:00:00.000000'),
            ('Carolyn', 'Degraffenreid',  '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'carolyn@example.com', 0, '', '2021-12-25 00:00:00.000000'),
            ('Katelyn', 'Anderson',  '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'katelyn@example.com', 0, '', '2021-12-25 00:00:00.000000'),
            ('Louise', 'Howard',  '123 rue Jarry', 'H2R 1M8', '514 222 3333', 'louise@example.com', 0, '', '2021-12-25 00:00:00.000000'),
        ], fields=(Client.first_name,
                   Client.last_name,
                   Client.address,
                   Client.postal_code,
                   Client.phone,
                   Client.email,
                   Client.email_consent,
                   Client.internal_notes,
                   Client.membership_paid_until)).execute()

    InventoryItem.add_index(peewee.SQL('CREATE INDEX inventoryitem_idx_name ON inventoryitem(name COLLATE NOCASE)'))

    InventoryItem.create_table()

    if import_data:
        import_inventory_items()
    else:
        InventoryItem.insert(name='Abonnement DIY', keywords='membership abonnement annuel membre diy atelier',
                             price=24.00, cost=0.0, msrp=0, taxable=True, avg_time_spent=0,
                             quick_add=True, special_meaning='membership').execute()

        InventoryItem.insert_many([
            ('Mise au point standard', 'mapbb checkup', 45.00, 0, 0, 45, True),
            ('Mise au point avancée', 'checkup complet', 75.00, 0, 0, 90, False),
            ('Mise au point hiver standard', 'checkup', 95.00, 0, 0, 80, True),
            ('Mise au point hiver avancée', 'checkup complet', 145.00, 0, 0, 120, False),
            ('Chambre à air + Installation', 'flat crevaison pneu crevé', 12.00, 0, 0, 10, True),
            ('Chambre à air', 'flat crevaison pneu crevé', 6.00, 0, 0, 0, False),
            ('Heure Atelier DIY', 'self-service', 1.00, 0, 0, 0, True),
            ('Pneu usagé', 'used tire', 24.00, 0, 0, 0, False),
            ('Pneu usagé (hiver)', 'used tire winter', 35.00, 0, 0, 0, False),
            ('Patins de freins usagé', '', 8.00, 0, 0, 0, False),
            ('Patins de freins neufs', '', 16.00, 0, 0, 0, False),
        ], fields=(
            InventoryItem.name, InventoryItem.keywords,
            InventoryItem.price, InventoryItem.cost, InventoryItem.msrp,
            InventoryItem.avg_time_spent, InventoryItem.quick_add)).execute()

        InventoryItem.insert(name='Don', keywords='donate donation',
                             price=10.00, cost=0, msrp=0, taxable=False, avg_time_spent=0,
                            quick_add=True, special_meaning='donation').execute()

    WorkorderStatus.create_table()

    if not import_data:
        WorkorderStatus.insert_many([
            ('Open', '#0D6EFD', 0),
            ('RDV MAP', '#8DB6D7', 1),
            ('En cours', '#0D6EFD', 2),
            ('À évaluer', '#fc00c9', 3),
            ('Approuvé', '#ae00ff', 4),
            ('RDV Pickup', '#8DB6D7', 5),
            ('Done', '#636363', 6),
            ('À vendre', '#8DB6D7', 7),
        ], fields=(WorkorderStatus.name, WorkorderStatus.color,
                   WorkorderStatus.display_order, WorkorderStatus.archived)
                                    ).execute()


    Workorder.create_table()
    WorkorderItem.create_table()
    Transaction.create_table()

    if import_data:
        import_workorders()
    else:
        Workorder.insert_many([
            (1, 'Nakamura red', 'Basic tuneup', 'Internal notes here', datetime.datetime(2021, 7, 8), datetime.datetime(2021, 7, 1),
             '123.00', '0.05', '0.09975', '6.15', '12.26', '141.41'),
        ], fields=(
            Workorder.client_id, Workorder.bike_description,
            Workorder.invoice_notes, Workorder.internal_notes,
            Workorder.paid_date,
            Workorder.created,
            Workorder.paid_subtotal, Workorder.paid_tax1_rate,
            Workorder.paid_tax2_rate, Workorder.paid_taxes1,
            Workorder.paid_taxes2, Workorder.paid_total)).execute()

        Workorder.insert_many([
            (1, 'Big fatbike', 'Winter tuneup', 'Winter Tuneup\nI already checked the chain, all seems good\nStill waiting for bearings to ship'),
            (2, 'Red Spider-man kid''s bike', 'Remove training wheels', '')
        ], fields=(Workorder.client_id, Workorder.bike_description, Workorder.invoice_notes, Workorder.internal_notes)).execute()

        Transaction.insert_many([
            ('141.41', 'interac', 1, datetime.datetime(2021, 7, 1))
        ], fields=(Transaction.amount, Transaction.payment_method, Transaction.workorder_id, Transaction.created)).execute()

        WorkorderItem.create_table()

        WorkorderItem.insert_many([
            (1, 1, 'Abonnement DIY', 24.00, 24.00),
            (1, 3, 'Mise au point avancée', 75.00, 75.00),
            (1, 9, 'Pneu usagé', 24.00, 24.00)
        ], fields=(WorkorderItem.workorder_id, WorkorderItem.inventory_item_id,
                   WorkorderItem.name, WorkorderItem.price,
                   WorkorderItem.orig_price)).execute()

    CashRegisterState.create_table()
    CashRegisterState.insert(
        expected_cash=Decimal('0.00'),
        expected_visa=Decimal('0.00'),
        expected_interac=Decimal('0.00'),
        confirmed_cash=Decimal('0.00'),
        confirmed_visa=Decimal('0.00'),
        confirmed_interac=Decimal('0.00'),
        comment='Database created',
    ).execute()




def anonymize():
    from random import seed, choice, random
    import string

    seed(1337)

    def randomize_char(c, multiple=True):

        # Randomly add similar chars
        times = 1 + (multiple and random() < 0.1)

        if c in string.ascii_lowercase:
            return ''.join(choice(string.ascii_lowercase) for i in range(times))
        elif c in string.ascii_uppercase:
            return ''.join(choice(string.ascii_uppercase) for i in range(times))
        elif c in string.digits:
            return ''.join(choice(string.digits) for i in range(times))

        return c

    example_names = []
    with open('data/prenoms.txt') as f:
        for name in f:
            example_names.append(string.capwords(name))

    for client in Client.select():

        if client.first_name:
            parts = len(client.first_name.split())
            new_name = choice(example_names)
            while len(new_name.split()) != parts:
                new_name = choice(example_names)
            client.first_name = new_name

        if client.last_name:
            parts = len(client.last_name.split())
            new_name = choice(example_names)
            while len(new_name.split()) != parts:
                new_name = choice(example_names)

            client.last_name = new_name

        addr = ''
        for c in client.address:
            addr += randomize_char(c)

        client.address = addr

        if client.postal_code:
            client.postal_code = choice(('H0H 0H0', 'H1A 0H0', 'H1B 0H0'))

        phone = ''
        for c in client.phone:
            phone += randomize_char(c, multiple=False)
        client.phone = phone

        email = ''
        for c in client.email:
            email += randomize_char(c, multiple=True)
        client.email = email

        internal_notes = ''
        for c in client.internal_notes:
            internal_notes += randomize_char(c)
        client.internal_notes = internal_notes

        client.save()

    for workorder in Workorder.select() \
                              .where((Workorder.bike_serial_number != '') |
                                     (Workorder.internal_notes != '') |
                                     (Workorder.invoice_notes != '')):

        bike_serial_number = ''
        for c in workorder.bike_serial_number:
            bike_serial_number += randomize_char(c)
        workorder.bike_serial_number = bike_serial_number

        internal_notes = ''
        for c in workorder.internal_notes:
            internal_notes += randomize_char(c)
        workorder.internal_notes = internal_notes

        invoice_notes = ''
        for c in workorder.invoice_notes:
            invoice_notes += randomize_char(c)
        workorder.invoice_notes = invoice_notes

        workorder.save()

    # Anonymize imported labels/custom items, as they may contain
    # phone numbers from invoice notes
    for item in WorkorderItem.select() \
                             .where(WorkorderItem.inventory_item_id.in_(
                                 InventoryItem.select(InventoryItem.id).where(InventoryItem.special_meaning != '')
                             )):

        name = ''

        if item.name.startswith('Work order #'):
            item.name = item.name[len('Work order #'):]
            name = 'Work order #'

        for c in item.name:
            name += randomize_char(c)
        item.name = name

        item.save()
