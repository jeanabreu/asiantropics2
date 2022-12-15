# -*- coding: utf-8 -*-
{
    'name': "Pago a cuenta especifica",

    'summary': """
        Habilita la opción para realizar un pago a una cuenta especifica""",

    'description': """
        Habilita la opción para realizar un pago a una cuenta especifica
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_views.xml',
    ],

}
