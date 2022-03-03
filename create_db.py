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
