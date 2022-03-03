import os
import peewee
from config import taxes
# from flask_peewee.db import Database
import datetime
from playhouse.hybrid import hybrid_property
from decimal import Decimal
import config

from setup_app import db

import decimal

decimal.getcontext().rounding = 'ROUND_HALF_UP'

# ---------- Flask-Security ----------
# https://github.com/flask-admin/flask-admin/blob/master/examples/auth/app.py
# https://flask-security-too.readthedocs.io/en/stable/quickstart.html#basic-peewee-application
from flask_security import Security, PeeweeUserDatastore, \
    UserMixin, RoleMixin, auth_required, hash_password, current_user

class Role(RoleMixin, db.Model):
    name = peewee.CharField(unique=True)
    description = peewee.TextField(null=True)
    permissions = peewee.TextField(null=True)

# N.B. order is important since Model also contains a get_id() -
# we need the one from UserMixin.
class User(UserMixin, db.Model):
    email = peewee.TextField()
    password = peewee.TextField()
    active = peewee.BooleanField(default=True)
    fs_uniquifier = peewee.TextField(null=False)
    confirmed_at = peewee.DateTimeField(null=True)


class UserRoles(db.Model):
    # Because peewee does not come with built-in many-to-many
    # relationships, we need this intermediary class to link
    # user to roles.
    user = peewee.ForeignKeyField(User, backref='roles')
    role = peewee.ForeignKeyField(Role, backref='users')
    name = property(lambda self: self.role.name)
    description = property(lambda self: self.role.description)

    def get_permissions(self):
        return self.role.get_permissions()


# ---------- Models ----------

current_dir = os.path.dirname(os.path.abspath(__file__))
postal_codes = {}

with open(current_dir + '/data/postal_codes.txt') as f:
    for line in f:
        postal_codes[line[:3]] = line[4:].strip()


class Client(db.Model):
    # SQLite explicit AUTOINCREMENT == don't reuse a previously delete ID
    id = peewee.BigIntegerField(primary_key=True, constraints=[peewee.SQL('AUTOINCREMENT')])
    first_name = peewee.TextField()
    last_name = peewee.TextField()
    address = peewee.TextField(default='')
    postal_code = peewee.TextField(default='')
    phone = peewee.TextField(default='')
    email = peewee.TextField(default='')
    email_consent = peewee.BooleanField(default=False)
    year_of_birth = peewee.IntegerField(null=True, default=None)
    internal_notes = peewee.TextField(default='')
    # FIXME : customized code
    # TODO : two kinds of membership
    membership_paid_until = peewee.DateTimeField(null=True)
    created = peewee.DateTimeField(default=datetime.datetime.now)
    updated = peewee.DateTimeField(default=datetime.datetime.now)
    archived = peewee.BooleanField(default=False)

    @classmethod
    def editable_cols(cls):
        return ['first_name', 'last_name', 'address', 'postal_code', 'phone', 'email', 'email_consent', 'year_of_birth', 'internal_notes']

    def name(self):
        return self.first_name + ' ' + self.last_name

    def postal_code_region(self):
        start = self.postal_code.strip().upper()[:3]
        if start in postal_codes:
            return postal_codes[start]

        return ''

    def __str__(self):
        return self.first_name + ' ' + self.last_name


class InventoryItem(db.Model):
    id = peewee.BigIntegerField(primary_key=True, constraints=[peewee.SQL('AUTOINCREMENT')])
    name = peewee.TextField()
    # TODO : À valider
    keywords = peewee.TextField(default='') # Servent dans la recherche sans être dans le nom
    category = peewee.TextField(default='')
    subcategory = peewee.TextField(default='')
    ean_code = peewee.TextField(default='')
    upc_code = peewee.TextField(default='')
    sku_code = peewee.TextField(default='')
    price = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    cost = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    msrp = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    taxable = peewee.BooleanField(default=True)
    discountable = peewee.BooleanField(default=True)
    # price_with_discount INTEGER NULLABLE DEFAULT NULL,
    avg_time_spent = peewee.IntegerField(default=0) # Temps en minutes, approximatif pour des fins de stats
    quick_add = peewee.BooleanField(default=False)
    special_meaning = peewee.TextField(default='') # Used for membership and donation
    type = peewee.TextField(default='article', choices=('labor', 'article', 'other'),
                            constraints=[peewee.SQL('''CHECK("type" IN ('labor', 'article', 'other'))''')])
    inventory_count = peewee.IntegerField(default=0)
    archived = peewee.BooleanField(default=False)

    def __str__(self):
        return self.name

# class WorkorderStatus(db.Model):
#     name = peewee.TextField()
#     color = peewee.TextField()

class Workorder(db.Model):
    """Workorders are used as a reference to compute profits, taxes,
    etc. They are both :

    - A todolist/project to be completed for workers
    - A sale

    """
    id = peewee.BigIntegerField(primary_key=True, constraints=[peewee.SQL('AUTOINCREMENT')])
    client = peewee.ForeignKeyField(Client, null=True, backref='workorders', on_delete='RESTRICT')
    bike_description = peewee.TextField(default='')
    bike_serial_number = peewee.TextField(default='')
    calendar_date = peewee.DateTimeField(default=datetime.datetime.now)
    # XXX : Customizable via une table de Status dans la database?
    # Est-ce que a peut poser des problèmes?
    status = peewee.TextField(default='open')
    # status = peewee.ForeignKeyField(WorkorderStatus, null=True)
    invoice_notes = peewee.TextField(default='')
    internal_notes = peewee.TextField(default='')
    created = peewee.DateTimeField(default=datetime.datetime.now)
    updated = peewee.DateTimeField(default=datetime.datetime.now)
    archived = peewee.BooleanField(default=False)

    # Archived values : if anything changes in the future (tax rates,
    # rebates, ...), these prices must stay

    paid_subtotal = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True, null=True)
    paid_tax1_rate = peewee.DecimalField(max_digits=15, decimal_places=8, auto_round=True, null=True)
    paid_tax2_rate = peewee.DecimalField(max_digits=15, decimal_places=8, auto_round=True, null=True)
    paid_taxes1 = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True, null=True)
    paid_taxes2 = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True, null=True)
    paid_total = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True, null=True)
    paid_date = peewee.DateTimeField(null=True, constraints=[
        # Either all of them or none of them are NULL
        peewee.SQL('''CHECK(
        ("paid_date" IS NULL) == ("paid_subtotal" IS NULL) AND
        ("paid_date" IS NULL) == ("paid_tax1_rate" IS NULL) AND
        ("paid_date" IS NULL) == ("paid_tax2_rate" IS NULL) AND
        ("paid_date" IS NULL) == ("paid_taxes1" IS NULL) AND
        ("paid_date" IS NULL) == ("paid_taxes2" IS NULL) AND
        ("paid_date" IS NULL) == ("paid_total" IS NULL)
        )''')])

    @classmethod
    def editable_cols(cls):
        return ['bike_description', 'bike_serial_number', 'calendar_date', 'invoice_notes', 'internal_notes']

    @hybrid_property
    def paid(self):
        """Called from code"""
        return self.paid_date is not None

    @paid.expression
    def paid(cls):
        """Called in SQL"""
        return cls.paid_date.is_null(False)

    def subtotal(self, force_calc=False):
        """Subtotal for all items (taxable or not)"""

        if not force_calc and self.paid:
            return self.paid_subtotal

        calc = Decimal(0)

        for item in self.items:
            calc += item.subtotal()

        return calc

    def taxes1(self, force_calc=False):

        if not force_calc and self.paid:
            return self.paid_taxes1

        calc = Decimal(0)

        for item in self.items:
            calc += item.taxes1()

        return calc

    def taxes2(self, force_calc=False):

        if not force_calc and self.paid:
            return self.paid_taxes2

        calc = Decimal(0)

        for item in self.items:
            calc += item.taxes2()

        return calc

    def taxes(self, force_calc=False):
        return self.taxes1(force_calc=force_calc) + self.taxes2(force_calc=force_calc)

    def total_discounts(self, force_calc=False):
        """Discount display on reciept"""

        if force_calc:
           raise NotImplementedError

        discount = Decimal(0)

        for item in self.items.where(WorkorderItem.price < WorkorderItem.orig_price):
            discount += (item.orig_price - item.price) * item.nb

        return round(discount, 2)

    def total(self, force_calc=False):
        return self.subtotal(force_calc=force_calc) + self.taxes(force_calc=force_calc)

    def __str__(self):
        return self.bike_description or 'No description'

    def set_paid(self):
        """Save archived values"""
        self.paid_date = datetime.datetime.now()
        self.paid_subtotal = self.subtotal()
        self.paid_tax1_rate = Decimal(config.taxes[0][1])
        self.paid_tax2_rate = Decimal(config.taxes[1][1])
        self.paid_taxes1 = self.taxes1()
        self.paid_taxes2 = self.taxes2()
        self.paid_total = self.total()

    def test_invariants(self):
        """Use this method in unit tests"""
        raise NotImplementedError

        assert self.updated >= self.created

class WorkorderItem(db.Model):
    id = peewee.BigIntegerField(primary_key=True, constraints=[peewee.SQL('AUTOINCREMENT')])
    workorder = peewee.ForeignKeyField(Workorder, backref='items', on_delete='RESTRICT')
    inventory_item = peewee.ForeignKeyField(InventoryItem, backref='workorder_items', null=True, on_delete='RESTRICT')
    name = peewee.TextField()
    nb = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True, default=1)
    price = peewee.DecimalField(max_digits=15, decimal_places=3, auto_round=True)
    # orig_price is duplicated here, it might change in the InventoryItem later
    orig_price = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    taxable = peewee.BooleanField(default=True)
    refund_item = peewee.ForeignKeyField('self', null=True, default=None, backref='refunded_by', on_delete='RESTRICT')

    @classmethod
    def editable_cols(cls):
        return ['name', 'nb', 'price', 'taxable']

    def subtotal(self):
        return self.nb * self.price

    def _calc_taxes(self, rate):
        assert type(rate) == Decimal
        return round(self.subtotal() * rate, 2)

    def taxes1(self):
        return self._calc_taxes(Decimal(config.taxes[0][1])) if self.taxable else Decimal(0)

    def taxes2(self):
        return self._calc_taxes(Decimal(config.taxes[1][1])) if self.taxable else Decimal(0)

    def serialized(self):
        """Serialization to send via the json API"""
        serialized_item = {k: getattr(self, k) for k in ['id', 'name', 'nb', 'taxable']}
        serialized_item['price'] = str(round(self.price, 2))
        serialized_item['orig_price'] = str(round(self.orig_price, 2))
        serialized_item['type'] = self.inventory_item.type

        serialized_item['refund_workorder_id'] = False
        if self.refund_item_id is not None:
            serialized_item['refund_workorder_id'] = self.refund_item.workorder.id

        serialized_item['refunded_in_workorder_id'] = False

        assert self.refunded_by.count() in [0, 1]

        if self.refunded_by.count():
            serialized_item['refunded_in_workorder_id'] = self.refunded_by.get().workorder.id

        return serialized_item

    def __str__(self):
        return self.name

class Transaction(db.Model):
    """Transactions are mostly used to keep track of cash registery and
    credit card terminal amounts. They are either related to a sale or
    to a non-sales-related amount adjustment (withdrawal/deposit).

    They are required for :

    - Unusual corner-cases (ex.: a workorder paid with a cash client
      deposit + 20$ visa)
    - Cash register balancing, to keep an history of cash register
      close/withdrawals/deposits of cash

    Total of transactions != total profits
    """
    TRANSACTION_TYPES = ('cash', 'interac', 'visa', 'check', 'credit account')

    id = peewee.BigIntegerField(primary_key=True, constraints=[peewee.SQL('AUTOINCREMENT')])
    amount = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    payment_method = peewee.TextField(choices=TRANSACTION_TYPES,
                                      constraints=[peewee.SQL('CHECK(payment_method IN (' +
                                                              ', '.join([f"'{t}'" for t in TRANSACTION_TYPES]) +
                                                              '))')])
    workorder_id = peewee.ForeignKeyField(Workorder, null=True, backref='transactions')

    # Comment should be at least an empty string (but preferably not)
    # if the transaction is not related to a workorder
    comment = peewee.TextField(default=None, null=True,
                               constraints=[peewee.SQL('''
                               CHECK((comment IS NULL) == (workorder_id IS NOT NULL))
                               ''')])
    created = peewee.DateTimeField(default=datetime.datetime.now)

class CashRegister(db.Model):
    """Store Cash Register close informations"""
    cash = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    visa = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    interac = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    closed = peewee.DateTimeField()
