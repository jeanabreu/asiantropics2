# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    settlement_credit_account_id = fields.Many2one('account.account', string="Cuenta crédito de liquidación ")
    settlement_debit_account_id = fields.Many2one('account.account', string="Cuenta débito de liquidación ")