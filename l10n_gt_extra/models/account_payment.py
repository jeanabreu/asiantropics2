# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime


class AccountPayment(models.Model):
    _inherit = "account.payment"

    bank_operation_ref = fields.Char(string="Referencia bancaria")
    account_journal_type = fields.Char(string="Tipo de diario", readonly=True, store=False)
    discarded_date = fields.Date(string="Fecha de Anulación")
    bank_operation_ref_many = fields.Many2one('pt_unique_deposits.bank_operation_ref', string="Referencia bancaria Many2one")
    type_document = fields.Many2one('l10n_gt_extra.type.document.payment', string='Tipo de Documento')
    
    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        self.account_journal_type = self.journal_id.type

    def _prepare_payment_moves(self):

        all_move_vals = []
        all_moves = super(AccountPayment, self)._prepare_payment_moves()
        for payment in self:
            for move in all_moves:
                if payment.bank_operation_ref:
                    move['bank_operation_ref'] = payment.bank_operation_ref

        return all_moves

    def action_discarded(self):
        for rec in self:
            rec.action_draft()
            self.move_id.button_cancel()
            self.write({'amount': 0.0, 'discarded_date': datetime.today()})
            self.move_id.write({'state': 'discarded'})
        return

    @api.onchange('payment_method_id')
    def _onchange_payment_method_id(self):
        payment_method_name = self.payment_method_id.name
        payment_method_name = payment_method_name.lower()
        
        document_types = False
        if self.payment_type == "outbound":
            if payment_method_name == "cheques":    
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Cheque')
                ], limit=1)
            if payment_method_name == "manual":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Nota de Débito')
                ], limit=1)
            if payment_method_name == "electrónico":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Nota de Débito')
                ], limit=1)
        if self.payment_type == "inbound":
            if payment_method_name == "manual":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Déposito')
                ], limit=1)
            if payment_method_name == "electrónico":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Déposito')
                ], limit=1)
            
        if document_types:
            self.type_document = document_types.id

    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountPayment, self).create(vals_list)
        for payment in res:

            if payment.check_number:
                payment.write({"bank_operation_ref": payment.check_number})

        for rec in res:
            if rec.bank_operation_ref and rec.type_document:
                vals_deposits = {
                    'name': rec.bank_operation_ref,
                    'payment_id': rec.id,
                    'journal_id': rec.journal_id.id,
                    'type_document': rec.type_document.id
                }
                bank_operation_ref = self.env['l10n_gt_extra.bank_operation_ref'].create(vals_deposits)
                rec.bank_operation_ref_many = bank_operation_ref.id
        return res
    
    def write(self, vals):
        for rec in self:
            res = super(AccountPayment, rec).write(vals)
            if 'bank_operation_ref' in vals:
                if rec.move_id:
                    rec.move_id.write({"bank_operation_ref": vals["bank_operation_ref"]})
                    
        return res
    
class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"
    
    bank_operation_ref = fields.Char(string="Referencia bancaria")
    type_document = fields.Many2one('l10n_gt_extra.type.document.payment', string='Tipo de Documento')
    
    @api.model
    def _set_journal_type_value(self):
        return self.journal_id.type
        

    bank_operation_ref = fields.Char(string="Referencia bancaria")
    account_journal_type = fields.Char(string="Tipo de diario", readonly=True, store=False, default=lambda self: self._set_journal_type_value())

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        self.account_journal_type = self.journal_id.type
    
    @api.onchange('payment_method_id')
    def _onchange_payment_method_id(self):
        payment_method_name = self.payment_method_id.name
        payment_method_name = payment_method_name.lower()
        
        document_types = False
        if self.payment_type == "outbound":
            if payment_method_name == "cheques":    
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Cheque')
                ], limit=1)
            if payment_method_name == "manual":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Nota de Débito')
                ], limit=1)
            if payment_method_name == "electrónico":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Nota de Débito')
                ], limit=1)
        if self.payment_type == "inbound":
            if payment_method_name == "manual":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Déposito')
                ], limit=1)
            if payment_method_name == "electrónico":
                document_types = self.env['l10n_gt_extra.type.document.payment'].search([
                    ('name', 'ilike', 'Déposito')
                ], limit=1)
            
        if document_types:
            self.type_document = document_types.id
    
    def _create_payment_vals_from_wizard(self):
        vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard()
        vals['bank_operation_ref'] = self.bank_operation_ref
        vals['type_document'] = self.type_document.id
        return vals
    
    def _create_payment_vals_from_batch(self, batch_result):
        vals = super(AccountPaymentRegister, self)._create_payment_vals_from_batch(batch_result)
        vals['bank_operation_ref'] = self.bank_operation_ref
        vals['type_document'] = self.type_document.id
        return vals
