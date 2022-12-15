# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PtPaymentSpecificAccountMultipleAccountPayments(models.Model):
    _name = "pt_payment_specific_account.multiple_account_payments"
    _description = 'Detalle de cuentas relacionadas al pago'
    
    payment_id = fields.Many2one('account.payment', string="Pago")
    account_id = fields.Many2one('account.account', string="Cuenta contable", required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Cuenta analítica")
    amount = fields.Monetary(string="Monto", required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id, string="Empresa")
    currency_id = fields.Many2one(string="Moneda", related='company_id.currency_id', readonly=False)
    
    
    @api.model
    def create(self, vals):
        #if 'amount' in vals:
        #    if vals['amount'] <= 0:
        #        raise ValidationError('El monto del detalle debe ser mayor a cero')

        res = super(PtPaymentSpecificAccountMultipleAccountPayments, self).create(vals)
        return res


class PtPaymentSpecificAccountMultipleAccountDiscounts(models.Model):
    _name = "pt_payment_specific_account.multiple_account_discounts"
    _description = 'Detalle de cuentas relacionadas al pago a descontar'
    
    payment_id = fields.Many2one('account.payment', string="Pago")
    account_id = fields.Many2one('account.account', string="Cuenta contable", required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Cuenta analítica", required=True)
    amount = fields.Monetary(string="Monto", required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id, string="Empresa")
    currency_id = fields.Many2one(string="Moneda", related='company_id.currency_id', readonly=False)
    