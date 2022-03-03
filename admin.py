from setup_app import app, db
from models import *
from security import security

from flask_admin import Admin, BaseView, expose
from flask_admin.menu import MenuLink
from flask_admin.contrib.peewee import ModelView

app.config['FLASK_ADMIN_SWATCH'] = 'default'

admin = Admin(app, name='MiniPOS', template_mode='bootstrap4')

admin.add_link(MenuLink(name='Back to App', url='/'))

class CustomizeWorkordersView(BaseView):
    @expose('/')
    def index(self):
        # return self.render('analytics_index.html')
        return '<b>TODO</b><ul><li>Choose quick access categories<li>Choose Quick Add items<li>Workorder statuses'

admin.add_view(CustomizeWorkordersView(name='Cutomize interface', endpoint='cutomize'))


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

admin.add_view(ClientModelView(Client, menu_icon_type='fa', menu_icon_value='fa-user', category='Raw data'))
admin.add_view(InventoryItemModelView(InventoryItem, menu_icon_type='fa', menu_icon_value='fa-cog', category='Raw data'))
admin.add_view(WorkorderModelView(Workorder, menu_icon_type='fa', menu_icon_value='fa-list-alt', category='Raw data'))
admin.add_view(ModelView(WorkorderItem, menu_icon_type='fa', menu_icon_value='fa-list', category='Raw data'))

from flask_admin import helpers as admin_helpers
@security.context_processor
def security_context_processor():
    return dict(
        admin_base_template=admin.base_template,
        admin_view=admin.index_view,
        h=admin_helpers,
    )
