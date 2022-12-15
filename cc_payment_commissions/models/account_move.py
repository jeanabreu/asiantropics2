# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
 
log = logging.getLogger(__name__)
 
  
class AccountMove(models.Model):
    _inherit = "account.move"
    
    cc_payment_operation = fields.Boolean(string="Liquidación de tarjeta")
    cc_payment_resolution = fields.Char(string="Resolución")
    cc_payment_serial = fields.Char(string="Serie")
    cc_payment_correlative = fields.Char(string="Correlativo")
    cc_payment_amount = fields.Monetary(string="Documento por")
    cc_payment_applied_amount = fields.Monetary(string="IVA por Transacción", compute="get_cc_taxes")
    cc_payment_transaction_tax = fields.Monetary(string="Monto sujeto de percepción", compute="get_cc_taxes")
    cc_payment_percentage = fields.Float(string="Porcentaje de Comisión")
    cc_payment_id = fields.Many2one('account.payment', string="Pago comisión")
    
    @api.onchange('cc_payment_amount')
    def _onchange_cc_payment_amount(self):
        self.cc_payment_transaction_tax = self.cc_payment_amount / 1.13
        self.cc_payment_applied_amount = self.cc_payment_transaction_tax * 0.13
    
    def get_cc_taxes(self):
        for rec in self:
            rec.cc_payment_transaction_tax = 0
            rec.cc_payment_applied_amount = 0
            if rec.cc_payment_amount > 0:
                rec.cc_payment_transaction_tax = rec.cc_payment_amount / 1.13
                rec.cc_payment_applied_amount = rec.cc_payment_transaction_tax * 0.13
        
    def create_cc_payment(self):
        for rec in self:
            if not self.cc_payment_operation:
                raise ValidationError('La factura no es de liquidación de tarjeta')
            
            invoice_data = self.env['account.move'].browse(rec.id)

            ctx = self._context.copy()
            ctx.update({
                'default_amount': rec.cc_payment_amount,
                'default_apply_commission': True,
                'default_partner_id': rec.partner_id.id,
                'default_provider_invoice_id': rec.id
            })
            
            return {
                'name': _('Create payment'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'account.payment',
                'view_id': self.env.ref('account.view_account_payment_form').id,
                'context': ctx
            }