# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    has_payslip_created = fields.Boolean(compute="check_payslip", store=False)

    def check_payslip(self):
        for rec in self:
            validate_invoice_id_query = self.env['pt_payment_slip.slip_config'].search([
                ('invoice_id', '=', rec.id)
            ])

            if len(validate_invoice_id_query) > 0:
                rec.has_payslip_created = True
            else:
                rec.has_payslip_created = False

    def action_view_payment_slip(self):
        validate_invoice_id_query = self.env['pt_payment_slip.slip_config'].search([
            ('invoice_id', '=', self.id)
        ], limit=1)
        action = self.env.ref('pt_payment_slip.action_pt_payment_slip').read()[0]
        action['domain'] = [('id', '=', validate_invoice_id_query.id)]
        action['views'] = [(self.env.ref('pt_payment_slip.pt_payment_slip_slip_config_form_view').id, 'form')]
        action['res_id'] = validate_invoice_id_query.id
        return action

    def update_payment_slip(self):
        vendor_id = self.partner_id.id

        return self.env['pt_payment_slip.slip_config']\
            .with_context(active_ids=self.ids, active_id=self.id, vendor_id=vendor_id)\
            .action_edit_payment_slip()
        return true

    def create_payment_slip(self):
        
        vendor_id = self.partner_id.id
        
        return self.env['pt_payment_slip.slip_config']\
            .with_context(active_ids=self.ids, active_id=self.id, vendor_id=vendor_id)\
            .action_create_payment_slip()
        return true
