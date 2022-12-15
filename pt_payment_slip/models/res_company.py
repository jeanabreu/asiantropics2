# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    payment_slip_detail_line_1 = fields.Char(string="Detalle de pagos - Linea 1")
    payment_slip_detail_line_2 = fields.Char(string="Detalle de pagos - Linea 2")
    payment_slip_detail_line_3 = fields.Char(string="Detalle de pagos - Linea 3")
    
