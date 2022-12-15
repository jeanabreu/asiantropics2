# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    iva_retencion_account_id = fields.Many2one('account.journal', related="company_id.iva_retencion_account_id", string='Diario de retencion de IVA', readonly=False)
    isr_retencion_account_id = fields.Many2one('account.journal', related="company_id.isr_retencion_account_id", string='Diario de retencion de ISR', readonly=False)
    show_analytic_lines = fields.Boolean(string="Mostrar lineas analíticas", related="company_id.show_analytic_lines", readonly=False)
    
    user_electronic_payment = fields.Many2one('res.users', related="company_id.user_electronic_payment", string='B.O. Pagos Electronicos', readonly=False)
    manager_electronic_payment = fields.Many2one('res.users', related="company_id.manager_electronic_payment", string='Encargado Pagos Electronicos', readonly=False)
