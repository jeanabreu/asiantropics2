# -*- coding: utf-8 -*-
from odoo import models, fields, api
from openerp.exceptions import UserError, ValidationError                

class L10nGtExtraBankOperationRef(models.Model):
    _name = 'l10n_gt_extra.bank_operation_ref'

    name = fields.Char(string="Referencia Bancaria")
    payment_id = fields.Many2one('account.payment', string="Pago")
    journal_id = fields.Many2one('account.journal', string="Diario")
    _name = 'l10n_gt_extra.bank_operation_ref'
    type_document = fields.Many2one('l10n_gt_extra.type.document.payment')
    
    @api.model
    def create(self, values):
        ref_data = self.env['l10n_gt_extra.bank_operation_ref'].search([])
        for ref_bank in ref_data:
            if ref_bank.name == values['name'] and ref_bank.journal_id.id == values['journal_id'] and ref_bank.type_document.id == values['type_document'] and ref_bank.type_document.validate_duplicity == True:
                raise ValidationError("La Referencia Bancaria ya a sido creada con anterioridad")
        return super(L10nGtExtraBankOperationRef, self).create(values)