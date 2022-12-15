# -*- coding: utf-8 -*-
{
    'name': "Electronic Invoicing - SAT FEL",

    'summary': """
        Odoo module for Guatemalan Electronic Invoice System (SAT FEL).
        """,

    'description': """
        Odoo module for Guatemalan Electronic Invoice System (SAT FEL).
        The following SAT Certificate provider are supoorted by this version: \n
        - DIGIFACT \n
        - InFile \n
    """,

    'author': "Pitaya Tech",
    'website': "https://www.pitaya.tech",
    'mainteiner': "Pitaya Tech Development Team",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Invoicing & Payments',
    'version': '13.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'web', 'base_setup', 'account'],

    # always loaded
    'data': [
        'security/digifact_felgt_security.xml',
        'security/infile_felgt_security.xml',
        'security/forcon_felgt_security.xml',
        'security/g4s_felgt_security.xml',
        'security/guatefacturas_felgt_security.xml',
        'security/ir.model.access.csv',
        'views/fel_report.xml',
        'views/account_move_view.xml',
        'views/account_journal_view.xml',
        'views/res_company_view.xml',
        'views/res_partner.xml',
        'views/res_config_settings_views.xml',
        'views/account_tax_views.xml'
    ],
    'assets':{
        'web.assets_backend': [
            'pt_multicert_felgt/static/src/js/pt_multicert_felgt_action_manager.esm.js'
        ]
    },
    # only loaded in demonstration mode
    'demo': [],
}
