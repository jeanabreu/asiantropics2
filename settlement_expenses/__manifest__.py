# -*- coding: utf-8 -*-

{
    'name': "Liquidaciones Guatemala",
    'version': '1.0',
    'category': 'Custom',
    'description': """Manejo de cajas chicas y liquidaciones""",
    'author': 'Pitaya Tech',
    'website': 'https://www.pitaya.tech',
    'depends': ['account', 'hr'],
    'data': [
        'views/invoice.xml',
        'views/payment.xml',
        'views/settlement_expenses_view.xml',
        'security/ir.model.access.csv',
        'security/settlement_expenses_security.xml',
        'reports/account_payment_report.xml',
        'views/account_journal_views.xml'
    ],
    'assets': {
        "web.assets_backend":["/settlement_expenses/static/src/css/settlement_expenses.css"]
    },
    'installable': True,
    'certificate': '',
}
