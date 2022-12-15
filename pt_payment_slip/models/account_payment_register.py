# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError



class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    
    def action_create_payments(self):
        payments = self._create_payments()
        
        for payment in payments:

            if len(payment.reconciled_bill_ids) > 0:
                mail_template = self.env.ref('pt_payment_slip.pt_payment_slip_payment_confirmation_template')
                email = payment.partner_id.email
                if 'billing_email' in self.env['res.partner']._fields:
                    if payment.partner_id.billing_email:
                        email = payment.partner_id.billing_email
                email_values = {
                    'email_to': email
                }
                mail_template.send_mail(payment.id, force_send=True, email_values=email_values)

        if self._context.get('dont_redirect_to_payments'):
            return True

        action = {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'context': {'create': False},
        }
        if len(payments) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': payments.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', payments.ids)],
            })
        return action
    