# -*- coding: utf-8 -*-
{
    'name': "Credit Card Payment Commissions",

    'summary': """
        Enables to deduct commissions for the Online payment provider from each payment done
       """,

    'description': """
        Enables to deduct commissions for the Online payment provider from each payment done.
        Each journal refers to a payment provider and linked to a payment bank. 
        When the journal is of type bank then it is possible to configure the commissions.
        Commissons are based on both fixed cost per transaction and percentage.
        In addition, the commissions are automatically debited to the provider account.
    """,

    'author': "Azkatech SAL",
    'website': "http://www.azka.tech",
    'version': '14.0.0',
    "category": "Accounting",
    "license": "AGPL-3",
    "support": "support+odoo@azka.tech",
    
    "price": 29.99,
    "currency": "USD",

    'depends': ['base', 'account'],

    'data': [
        'security/ir.model.access.csv',
        'views/account_journal.xml',
        'views/res_partner_views.xml',
        'views/account_payment_views.xml',
        'views/account_move_views.xml'
    ],
    
    'application': False, 
    'images': ['static/description/banner.png'],
}
