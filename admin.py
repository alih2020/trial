from setup_app import app, db
from models import *
from security import security

from flask_admin import Admin, BaseView, expose
from flask_admin.menu import MenuLink
from flask_admin.contrib.peewee import ModelView
from flask import request, jsonify

import json
from peewee import fn

app.config['FLASK_ADMIN_SWATCH'] = 'default'

admin = Admin(app, name='MiniPOS', template_mode='bootstrap4')

admin.add_link(MenuLink(name='Back to App', url='/'))

class CustomizeWorkordersView(BaseView):
    @expose('/')
    def index(self):
        # return self.render('analytics_index.html')
        return '<b>TODO</b><ul><li>Choose quick access categories<li>Choose Quick Add items<li>Workorder statuses'

admin.add_view(CustomizeWorkordersView(name='Cutomize interface', endpoint='cutomize'))


class CustomizeWorkorderStatusView(BaseView):
    @expose('/api/status/', methods=['POST'])
    def api_status(self):
        """ Modifies or creates a workorder status, and sets the display
        order of the statuses.

        It is possible to set a status to archive using GET,
         if the status_id is provided as a parameter. """

        form = request.form

        # Rearranging order
        if 'ids' in form:
            data = json.loads(form['ids'])
            status_ids = data['status_ids']
            statuses = []

            WorkorderStatus.update({WorkorderStatus.display_order:None}).execute()

            order = 0
            for status_id in status_ids:
                status = WorkorderStatus.get(status_id)
                status.display_order = order
                statuses.append(status)
                order += 1

            WorkorderStatus.bulk_update(statuses, fields=[WorkorderStatus.display_order])

            return jsonify(True)

        # Archiving
        if 'archived' in form:
            status = WorkorderStatus.get(WorkorderStatus.id==form['statusId'])

            order = status.display_order
            status.display_order = None
            status.archived = True
            status.save()

            workorderstatuses = WorkorderStatus.select().where(WorkorderStatus.display_order > order).order_by(WorkorderStatus.display_order.asc())
            statuses = []
            for status in workorderstatuses:
                status.display_order = status.display_order - 1
                statuses.append(status)

            if len(statuses) > 0:
                WorkorderStatus.bulk_update(statuses, fields=[WorkorderStatus.display_order])

            # This should always be true, if it's not, there's a flaw in the logic
            nb_not_archived = WorkorderStatus.select().where(~WorkorderStatus.archived).count()
            orders = set(w.display_order for w in WorkorderStatus.select().where(~WorkorderStatus.archived))
            assert orders == set(range(nb_not_archived))

            return jsonify(True)


        # Modifiying/Creating
        if 'id' in form:
            status = WorkorderStatus.get(WorkorderStatus.id==form['id'])
        else:
            last_place = WorkorderStatus.select(fn.MAX(WorkorderStatus.display_order)).scalar()

            if last_place is None: # All statuses are archived
                last_place = -1

            status = WorkorderStatus()
            status.display_order = last_place + 1


        status.name = form['name']
        status.color = form['color']
        status.save()

        return status.serialized()



    @expose('/')
    def index(self):
        workorderstatuses = []
        statuses = WorkorderStatus.select().where((WorkorderStatus.archived == False ) & (WorkorderStatus.display_order == None ))

        for status in statuses:
            last_place = WorkorderStatus.select(fn.MAX(WorkorderStatus.display_order)).scalar()
            status.display_order = last_place + 1
            status.save()

        statuses = WorkorderStatus.select().order_by(WorkorderStatus.display_order).where(WorkorderStatus.archived == False)
        for status in statuses:
            workorderstatuses.append(status.serialized())

        return self.render('admin/workorderstatus.html',
                             statuses=statuses,
                             workorderstatuses=workorderstatuses)

admin.add_view(CustomizeWorkorderStatusView(name='Cutomize Workorder Status', endpoint='status'))


class ClientModelView(ModelView):
    column_searchable_list = ['first_name', 'last_name', 'address', 'phone', 'email', 'internal_notes']
    column_list = ['archived', 'first_name', 'last_name', 'postal_code', 'phone', 'email', 'created']
    column_filters = ['postal_code', 'created', 'internal_notes', 'year_of_birth', 'email_consent']
    page_size = 80
    column_default_sort = [('archived', False), ('id', False)]
    can_export = True
    can_view_details = True
    details_modal = True

class InventoryItemModelView(ModelView):
    column_searchable_list = ['name', 'keywords', 'category', 'subcategory', 'ean_code', 'upc_code', 'sku_code']
    column_filters = ['name', 'price', 'cost', 'type']
    column_list = ['id', 'archived', 'name', 'price', 'cost', 'category', 'subcategory', 'sku_code']
    column_default_sort = [('archived', False), ('id', False)]
    page_size = 80
    can_export = True
    can_view_details = True
    details_modal = True

class WorkorderModelView(ModelView):
    inline_models = (WorkorderItem,)
    column_list = ['client', 'paid', 'status', 'bike_description', 'invoice_notes', 'internal_notes']
    can_export = True
    can_view_details = True
    details_modal = True

class WorkorderStatusModelView(ModelView):
    column_searchable_list = ['name', 'color']
    column_filters = ['name', 'color', 'display_order', 'archived']
    column_list = ['id', 'archived', 'name', 'color', 'display_order']
    column_default_sort = [('archived', False), ('id', False)]
    page_size = 80
    can_export = True
    can_view_details = True
    details_modal = True


admin.add_view(ClientModelView(Client, menu_icon_type='fa', menu_icon_value='fa-user', category='Raw data'))
admin.add_view(InventoryItemModelView(InventoryItem, menu_icon_type='fa', menu_icon_value='fa-cog', category='Raw data'))
admin.add_view(WorkorderModelView(Workorder, menu_icon_type='fa', menu_icon_value='fa-list-alt', category='Raw data'))
admin.add_view(WorkorderStatusModelView(WorkorderStatus, menu_icon_type='fa', menu_icon_value='fa-check-square', category='Raw data'))
admin.add_view(ModelView(WorkorderItem, menu_icon_type='fa', menu_icon_value='fa-list', category='Raw data'))

from flask_admin import helpers as admin_helpers
@security.context_processor
def security_context_processor():
    return dict(
        admin_base_template=admin.base_template,
        admin_view=admin.index_view,
        h=admin_helpers,
    )
