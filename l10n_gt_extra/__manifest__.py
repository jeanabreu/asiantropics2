# -*- encoding: utf-8 -*-

{
    'name': 'Guatemala - Reportes Requeridos por S.A.T.',
    'version': '1.2',
    'category': 'Localization',
    'description': """ Reportes Requeridos por la S.A.T. : Libros de: Banco, Ventas, Compras, Inventario, Diario, Mayor, Banco Conciliado v14""",
    'author': 'Pitaya Tech',
    'website': 'https://www.pitaya.tech/',
    'depends': ['l10n_gt', 'account_tax_python', 'product', 'account', 'account_accountant', 'report_xlsx'],
    'data': [
        'security/ir.model.access.csv',
        #'views/assets.xml',
        'data/l10n_gt_extra_base.xml',
        'views/l10_gt_extra_report.xml',
        'views/reporte_banco.xml',
        'views/reporte_partida.xml',
        'views/reporte_compras.xml',
        'views/reporte_ventas.xml',
        'views/reporte_inventario.xml',
        'views/reporte_diario.xml',
        'views/reporte_mayor.xml',
        'views/l10n_gt_extra_view.xml',
        'views/res_partner_view.xml',
        'views/res_company_view.xml',
        'views/product_views.xml',
        'views/account_move_view.xml',
        'views/account_view.xml',
        'views/product_category_view.xml',
        'views/res_config_settings_views.xml',
        'views/account_journal_view.xml',
        'views/account_payment_view.xml',
        'wizard/report_electronic_payment.xml',
        'wizard/report.xml',
        'wizard/wizard_electronic_payment_views.xml',
        'wizard/wizard_assets_capitalization_views.xml',
        'views/account_tax_views.xml',
        'report/check_report_xlsx.xml',
        'report/check_report.xml',
        'views/account_bank_statement_view.xml',
    ],
    "assets":{
        "web.assets_backend": [
            "/l10n_gt_extra/static/src/js/reconciliation_action.js"
        ],
        'web.assets_qweb': [
            "/l10n_gt_extra/static/src/xml/account_reconciliation.xml",
        ],
    },

    'demo': [],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
