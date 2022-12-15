# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_receipt_journal = fields.Boolean(string="¿Es recibo?")
    iva_forgiveness_account_id = fields.Many2one('account.account', string="Cuenta exención ventas")
    isr_sales_account_id = fields.Many2one('account.account', string="Cuenta ISR ventas")
    isr_purchase_account_id = fields.Many2one('account.account', string="Cuenta ISR compras")
    
    iva_sales_account_id = fields.Many2one('account.account', string="Cuenta retención IVA ventas")
    iva_purchase_account_id = fields.Many2one('account.account', string="Cuenta retención IVA compras")
    
    is_capitalization_journal = fields.Boolean(string="Diario de capitalización")
    capitalization_account_id = fields.Many2one('account.account', string="Cuenta de capitalización de activos")
    
    def _inverse_check_next_number(self):
        for journal in self:
            if journal.check_next_number and not re.match(r'^[0-9]+$', journal.check_next_number):
                raise ValidationError(_('Next Check Number should only contains numbers.'))
            #if int(journal.check_next_number) < journal.check_sequence_id.number_next_actual:
            #    raise ValidationError(_(
            #        "The last check number was %s. In order to avoid a check being rejected "
            #        "by the bank, you can only use a greater number.",
            #        journal.check_sequence_id.number_next_actual
            #    ))
            if journal.check_sequence_id:
                journal.check_sequence_id.sudo().number_next_actual = int(journal.check_next_number)
                journal.check_sequence_id.sudo().padding = len(journal.check_next_number)