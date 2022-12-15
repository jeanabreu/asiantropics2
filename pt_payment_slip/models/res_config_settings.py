# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    payment_slip_detail_line_1 = fields.Char(string="Detalle de pagos - Linea 1", related="company_id.payment_slip_detail_line_1", readonly=False)
    payment_slip_detail_line_2 = fields.Char(string="Detalle de pagos - Linea 2", related="company_id.payment_slip_detail_line_2", readonly=False)
    payment_slip_detail_line_3 = fields.Char(string="Detalle de pagos - Linea 3", related="company_id.payment_slip_detail_line_3", readonly=False)
