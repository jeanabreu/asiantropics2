# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    settlement_expenses_id = fields.Many2one("settlement_expenses", string="Liquidación", readonly=False, states={'reconciled': [('readonly', True)]}, ondelete='restrict')
