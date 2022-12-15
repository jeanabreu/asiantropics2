# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    sat_tax_type = fields.Selection([
        ('service_good', 'Bien/Servicio'),
        ('press_tax', 'Timbre de prensa'),
        ('gas', 'Combustible')
    ], string="Clasificación SAT", default="service_good")
