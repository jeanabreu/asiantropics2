# -*- coding: utf-8 -*-
{
    'name': "Contraseña de pago de proveedores",

    'summary': """
        Modulo para el manejo de contraseñas de proveedores
        """,

    'description': """
        Modulo para el manejo de contraseñas de proveedores
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Invoicing',
    'version': '14.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'mail'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',        
        'data/pt_payment_slip_data.xml',
        'views/pt_payment_slip_views.xml',
        'reports/pt_payment_slip_format.xml',
        'reports/pt_payment_slip_report.xml',
        'data/pt_payment_slip_mail_template.xml',        
        'wizard/payment_send.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
