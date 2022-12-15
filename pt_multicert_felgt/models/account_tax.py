# -*- encoding: UTF-8 -*-

from odoo import api, models, fields, _
import xml.etree.cElementTree as ET
from datetime import datetime, timedelta


class AccountTax(models.Model):
    _inherit = 'account.tax'

    fel_timbre_tax = fields.Boolean(string="Timbre FEL")
    fel_tax = fields.Selection([
        ('IVA', 'IVA'),
        ('PETROLEO', 'PETROLEO'),
        ('TURISMO HOSPEDAJE', 'TURISMO HOSPEDAJE'),
        ('TURISMO PASAJES', 'TURISMO PASAJES'),
        ('TIMBRE DE PRENSA', 'TIMBRE DE PRENSA'),
        ('BOMBEROS', 'BOMBEROS'),
        ('TASA MUNICIPAL', 'TASA MUNICIPAL'),
    ], string="Tipo impuesto FEL", default="IVA")
