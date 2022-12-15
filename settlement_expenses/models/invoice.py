# -*- encoding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    settlement_expenses_id = fields.Many2one("settlement_expenses", string="Liquidación", readonly=False, states={'paid': [('readonly', True)]}, ondelete='restrict')

    @api.onchange('settlement_expenses_id')
    def _onchange_settlement_expenses_id(self):

        if self.is_invoice(include_receipts=True):
            company_currency_id = self.env.user.company_id.currency_id.id
            account_move_currency = self.currency_id.id
            if self.settlement_expenses_id and 'show_conversion_rate' in self.env['account.move']._fields:
                for payment in self.settlement_expenses_id.payment_id:
                    if payment.payment_type == 'outbound':
                        if payment.currency_id.id != company_currency_id:
                            outbound_currency = self.env['res.currency.rate'].search([
                                ('currency_id', '=', payment.currency_id.id),
                                ('name', '=', payment.date),
                                ('company_id', '=', self.env.company)
                            ], limit=1)
                            conversion_rate = outbound_currency.rate
                            if conversion_rate > 0:
                                conversion_rate = 1 / conversion_rate
                            self.conversion_rate_ref = round(conversion_rate, 5)

            '''if not self.settlement_expenses_id and 'show_conversion_rate' in self.env['account.move']._fields:
                company_currency_id = self.env.user.company_id.currency_id.id
                account_move_currency = self.currency_id.id
                self.show_conversion_rate = False
                if company_currency_id != account_move_currency:
                    self.show_conversion_rate = True
                    conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate
                    if conversion_rate > 0:
                        conversion_rate = 1 / conversion_rate
                    self.conversion_rate_ref = round(conversion_rate, 5)'''

