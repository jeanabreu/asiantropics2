# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"
    
    has_commission = fields.Boolean(string="Aplicar comisiones")
    cc_account_payment = fields.Many2one('account.account', string="Cuenta transitoria pagos TC")