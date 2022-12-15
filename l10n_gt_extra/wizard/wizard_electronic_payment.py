# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _


class WizardElectronicPayment(models.TransientModel):
    _name = "l10n_gt_extra.wizard_electronic_payment_wizard"
    _description = "Pagos electrónicos"

    start_date = fields.Date(string="Fecha de inicio")
    end_date = fields.Date(string="Fecha de fin", default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one('res.partner', string="Proveedor", required=True)
    debit_note = fields.Char(string="Nota de débito")
    payment_concept = fields.Char(string="Concepto del pago", required=True)
    request_date = fields.Date("Fecha de solicitud", default=fields.Date.context_today, required=True)
    payment_date = fields.Date(string="Fecha de pago", default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id, string="Empresa")
    bank_account_id = fields.Many2one('res.partner.bank', string='Cuenta bancaria', required=True)
    invoice_ids = fields.Many2many('account.move', 'wizard_electronic_payment_wizard_account_move_rel', 'account_id', 'wizard_electronic_payment_id', string='Facturas')

    def get_electronic_payments(self):

        data = {
             'ids': [],
             'model': 'l10n_gt_extra.wizard_electronic_payment',
             'form': self.read()[0]
        }
        return self.env.ref('l10n_gt_extra.l10n_gt_extra_electronic_payment').report_action(self, data=data)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            if self.start_date:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'posted'),
                    ('invoice_date_due', '<=', self.end_date),
                    ('invoice_date_due', '>=', self.start_date),
                    ('amount_residual_signed', '<', 0),
                    ('move_type', '=', 'in_invoice'),
                ], order="invoice_date_due")

                self.invoice_ids = invoices
            else:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'posted'),
                    ('invoice_date_due', '<=', self.end_date),
                    ('amount_residual_signed', '<', 0),
                    ('move_type', '=', 'in_invoice'),
                ], order="invoice_date_due")

                self.invoice_ids = invoices

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.partner_id:
            if self.start_date:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'posted'),
                    ('invoice_date_due', '<=', self.end_date),
                    ('invoice_date_due', '>=', self.start_date),
                    ('amount_residual_signed', '<', 0),
                    ('move_type', '=', 'in_invoice'),
                ], order="invoice_date_due")

                self.invoice_ids = invoices
            else:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'posted'),
                    ('invoice_date_due', '<=', self.end_date),
                    ('amount_residual_signed', '<', 0),
                    ('move_type', '=', 'in_invoice'),
                ], order="invoice_date_due")

                self.invoice_ids = invoices

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.partner_id:
            if self.start_date:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'posted'),
                    ('invoice_date_due', '<=', self.end_date),
                    ('invoice_date_due', '>=', self.start_date),
                    ('amount_residual_signed', '<', 0),
                    ('move_type', '=', 'in_invoice'),
                ], order="invoice_date_due")

                self.invoice_ids = invoices
            else:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'posted'),
                    ('invoice_date_due', '<=', self.end_date),
                    ('amount_residual_signed', '<', 0),
                    ('move_type', '=', 'in_invoice'),
                ], order="invoice_date_due")

                self.invoice_ids = invoices
