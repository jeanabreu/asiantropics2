{
    'name': "Automated Rate",
    'summary': """
        Banguat automated rate""",
    'description': """
        Retreives Banguat daily Dollar rate and adds it to the currency rate
    """,
    'author': "Pitaya Tech",
    'license': "AGPL-3",
    'website': "https://www.pitaya.tech",
    'category': 'Rates',
    'version': '1.0.0',
    'data': [
        'security/automated_rates_security.xml',
        'data/automated_rate_data.xml',
        'security/ir.model.access.csv',
        'views/account_move_view.xml',
        'views/account_payment_view.xml'
    ],
    'depends': ['base', 'account'],
}
