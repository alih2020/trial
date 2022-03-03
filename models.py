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

class WorkorderStatus(db.Model):
    name = peewee.TextField()
    color = peewee.TextField()
    display_order = peewee.IntegerField(null=True, default=None)
    archived = peewee.BooleanField(default=False)

    def serialized(self):
        """Serialization to send via the json API"""
        serialized_item = {k: getattr(self, k) for k in ['id', 'name', 'color', 'display_order', 'archived']}

        return serialized_item

    def __str__(self):
        return self.name

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
    # status = peewee.TextField(default='open')
    status = peewee.ForeignKeyField(WorkorderStatus, default=1)
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
        return ['bike_description', 'bike_serial_number', 'calendar_date', 'status', 'invoice_notes', 'internal_notes']

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

        calc = Decimal('0.00')

        for item in self.items:
            calc += item.subtotal()

        return calc

    def _calc_taxes(self, rate):
        """ABANDON ALL HOPE, YE WHO ENTERS HERE

        BE AWARE: Taxes are complex. Because of rounding, the same
        invoice can end up with two different totals post-taxes :

        sum(item_price) * taxes != sum(item_price * taxes)

              Version 1         !=       Version 2


        Eg.: item1 = 1.15$, item2 = 1.10$

        >>> from decimal import Decimal
        >>> item1 = Decimal('1.15')
        >>> item2 = Decimal('1.10')

        >>> # Subtotal is 2.25$
        >>> item1 + item2
        Decimal('2.25')

        >>> # Version 1
        >>> round((item1 + item2) * Decimal('1.15'), 2)
        Decimal('2.59')

        >>> # Version 2
        >>> round(item1 * Decimal('1.15'), 2) + round(item2 * Decimal('1.15'), 2)
        Decimal('2.58')


        The privileged method seems to be Version 1 in most places.

        For instance :
        https://www.revenuquebec.ca/fr/entreprises/taxes/tpstvh-et-tvq/perception-de-la-tps-et-de-la-tvq/calcul-des-taxes/

        > Si vous vendez plus d'un bien, vous pouvez calculer la TPS
        > et la TVQ payables sur le total des prix de tous ces biens
        > avant d'arrondir la fraction.


        This is more intuitive when looking at the Receipt Summary :

            SUBTOTAL: 2.25$
            TOTAL: 2.25$ + tx = 2.59$

        But it has the drawback of not allowing to display taxes on a
        per-line basis

                   |   Price   | Price+tx
            Item 1 |    1.10$  | 1.27$
            Item 2 |    1.15$  | 1.32$
        --------------------------------
                     Total:      2.58$ doesn't add up


        This can also lead to weird results when refunding an item
        with taxes :

                   |   Price   | Price+tx
            Item 1 |    1.10$  |  1.27$
            Item 2 |    1.15$  |  1.32$
        --------------------------------
                     Total:      2.58$ paid the first time

          Refund 1 |   -1.10$  | -1.27$
        --------------------------------

          Refund 2 |   -1.15$  | -1.32$
        --------------------------------
                     Total:      2.58$ - 1.27$ -1.32$
                              = -0.01$
                          => The client just won a free 1¢

        In the end, it seems that most people don't care that much
        about a 1¢ rounding error, although this might require a
        special handling of a full refund vs partial refund of a
        workorder... *Sigh*

        More on the subject...

        - People angry about a software that uses the Version 2
        computation :
        https://community.waveapps.com/discussion/7873/sales-tax-needs-to-be-calculated-on-subtotal

        -
        https://money.stackexchange.com/questions/23973/what-is-the-optimal-way-to-calculate-tax-apply-tax-to-each-item-then-sum-the-p

        - In Québec specifically, there are weird corner cases that
          would require an even more complex taxes system :

        https://www.lapresse.ca/affaires/finances-personnelles/201604/28/01-4975947-les-de-taxes.php
        https://ici.radio-canada.ca/tele/la-facture/site/segments/reportage/199628/amazon-livre-taxes-tps-tvq-tvh-numerique

        If the need appears, this might *maybe* be handled without
        restructuring everything with a complex system that covers all
        cases of all the countries in the world with a quick hack :

        By specifying arbitrary logic with a `def calc_tax(item):` in
        `config.py`. Such a function could bypass everything here.

        """

        assert type(rate) == Decimal

        subtotal = Decimal('0.00')

        for item in self.items.where(WorkorderItem.taxable):
            subtotal += item.subtotal()

        return round(subtotal * rate, 2)

    def taxes1(self, force_calc=False):

        if not force_calc and self.paid:
            return self.paid_taxes1

        return self._calc_taxes(Decimal(config.taxes[0][1]))

    def taxes2(self, force_calc=False):

        if not force_calc and self.paid:
            return self.paid_taxes2

        return self._calc_taxes(Decimal(config.taxes[1][1]))

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
        self.paid_subtotal = self.subtotal()
        self.paid_tax1_rate = Decimal(config.taxes[0][1])
        self.paid_tax2_rate = Decimal(config.taxes[1][1])
        self.paid_taxes1 = self.taxes1()
        self.paid_taxes2 = self.taxes2()
        self.paid_total = self.total()
        self.paid_date = datetime.datetime.now()

    def test_invariants(self):
        """This method is used to validate that an imported database doesn't
        contain errors"""

        assert self.subtotal(force_calc=False) + self.taxes(force_calc=False) == self.total(force_calc=False)
        assert self.subtotal(force_calc=True) + self.taxes(force_calc=True) == self.total(force_calc=True)

        assert round(self.subtotal(force_calc=True), 2) == self.subtotal(force_calc=False)
        assert round(self.total(force_calc=True), 2) == self.total(force_calc=False)
        assert round(self.taxes1(force_calc=True), 2) == self.taxes1(force_calc=False)
        assert round(self.taxes2(force_calc=True), 2) == self.taxes2(force_calc=False)
        assert round(self.taxes(force_calc=True), 2) == self.taxes(force_calc=False)

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

class CashRegisterState(db.Model):
    """Store the state of the cash register at a given point in time.

    This is required for X/Z reports (to know how much of each payment
    types should

    """

    # These are the expected values, computed from the sum of
    # Transactions since the last close
    expected_cash = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    expected_visa = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    expected_interac = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)

    # These are the actual amounts, physical cash and amounts from the
    # visa machine
    confirmed_cash = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    confirmed_visa = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)
    confirmed_interac = peewee.DecimalField(max_digits=15, decimal_places=2, auto_round=True)

    comment = peewee.TextField(default=None, null=True)

    state_time = peewee.DateTimeField(default=datetime.datetime.now)
