# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from decimal import Decimal, ROUND_HALF_UP
from odoo.exceptions import UserError, ValidationError
import logging
logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    conversion_rate_ref = fields.Float(string="Tasa de conversión", default=lambda self: self.get_conversion_rate_reference_default(), digits=(16, 10))
    conversion_rate_ref_readonly_store = fields.Float(string="Tasa de conversión", digits=(16, 10))
    show_conversion_rate = fields.Boolean(compute="check_currency")

    account_check_user_group = fields.Boolean(compute="get_rate_user_group", default=lambda self: self.default_get_rate_user_group(), )

    @api.model_create_multi
    def create(self, vals_list):
        
        if 'conversion_rate_ref_readonly_store' in vals_list:
            vals_list.update({'conversion_rate_ref': vals_list.get('conversion_rate_ref_readonly_store')})
        return super(AccountMove, self).create(vals_list)
    
    def write(self, vals):
        for rec in self:
            if 'conversion_rate_ref_readonly_store' in vals:
                vals.update({'conversion_rate_ref': vals.get('conversion_rate_ref_readonly_store')})
        return super(AccountMove, self).write(vals)

    def default_get_rate_user_group(self):
        can_edit = self.env['res.users'].has_group('automated_rate.group_change_rate')

        return can_edit
    
    def get_rate_user_group(self):
        can_edit = self.env['res.users'].has_group('automated_rate.group_change_rate')

        self.account_check_user_group = can_edit
        #return can_edit

    @api.onchange('invoice_date')
    def onchange_invoice_date(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        account_move_currency = self.currency_id.id
        self.show_conversion_rate = False
        if company_currency_id != account_move_currency and self.is_invoice(include_receipts=True):
            self.show_conversion_rate = True
            conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate
            if conversion_rate > 0:
                conversion_rate = 1 / conversion_rate
            self.conversion_rate_ref = round(conversion_rate, 10)
            self.conversion_rate_ref_readonly_store = self.conversion_rate_ref
            if self.show_conversion_rate:
                self = self.with_context(override_currency_rate=self.conversion_rate_ref)

    @api.onchange('conversion_rate_ref')
    def onchange_conversion_rate_ref(self):
        if self.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.conversion_rate_ref)
            self.with_context(check_move_validity=False, override_currency_rate=self.conversion_rate_ref)._onchange_currency()
            self.conversion_rate_ref_readonly_store = self.conversion_rate_ref

    @api.onchange('journal_id')
    def _onchange_journal(self):
        res = super(AccountMove, self)._onchange_journal()
        print('access')
        company_currency_id = self.env.user.company_id.currency_id.id
        account_move_currency = self.currency_id.id
        print('access', account_move_currency, company_currency_id)
        self.show_conversion_rate = False
        if company_currency_id != account_move_currency and self.is_invoice(include_receipts=True):
            self.show_conversion_rate = True
            conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate
            if conversion_rate > 0:
                conversion_rate = 1 / conversion_rate
            self.conversion_rate_ref = round(conversion_rate, 10)
            self.conversion_rate_ref_readonly_store = self.conversion_rate_ref
            if self.show_conversion_rate:
                self = self.with_context(override_currency_rate=self.conversion_rate_ref)
    
    @api.onchange('currency_id')
    def onchange_currency_id(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        account_move_currency = self.currency_id.id
        self.show_conversion_rate = False
        if company_currency_id != account_move_currency and self.is_invoice(include_receipts=True):
            self.show_conversion_rate = True
            conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate
            if conversion_rate > 0:
                conversion_rate = 1 / conversion_rate
            self.conversion_rate_ref = round(conversion_rate, 10)
            self.conversion_rate_ref_readonly_store = self.conversion_rate_ref
            if self.show_conversion_rate:
                self = self.with_context(override_currency_rate=self.conversion_rate_ref)

    def check_currency(self):
        for rec in self:
            company_currency_id = self.env.user.company_id.currency_id.id
            account_move_currency = rec.currency_id.id
            rec.show_conversion_rate = False
            if company_currency_id != account_move_currency and rec.is_invoice(include_receipts=True):
                rec.show_conversion_rate = True
                self.get_conversion_rate_reference_default()

    def get_conversion_rate_reference_default(self):

        conversion_rate_ref = 0.00
        for rec in self:
            company_currency_id = self.env.user.company_id.currency_id.id
            account_move_currency = rec.currency_id.id
            conversion_rate_ref = 0.00
            if company_currency_id != account_move_currency and rec.is_invoice(include_receipts=True):
                conversion_rate = rec.currency_id.with_context(date=rec.invoice_date).rate
                if conversion_rate > 0:
                    conversion_rate = 1 / conversion_rate
                conversion_rate_ref = round(conversion_rate, 10)

        return conversion_rate_ref


    @api.model
    def _get_default_currency(self):
        if self.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.conversion_rate_ref)
        return super(AccountMove, self)._get_default_currency()

    @api.onchange('invoice_line_ids', 'tax_withold_amount')
    def _onchange_invoice_line_ids(self):

        if self.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.conversion_rate_ref)
        return super(AccountMove, self)._onchange_invoice_line_ids()
    
    def _recompute_tax_lines(self, recompute_tax_base_amount=False):
        if self.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.conversion_rate_ref)
        return super(AccountMove, self)._recompute_tax_lines(recompute_tax_base_amount)
    
    def update_conversion(self):
        if self.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.conversion_rate_ref)
            self.onchange_conversion_rate_ref()
    
    @api.model
    def default_get(self, fields_list):
        if self.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.conversion_rate_ref)
        return super(AccountMove, self).default_get(fields_list)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_computed_taxes(self):
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
        return super(AccountMoveLine, self)._get_computed_taxes()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
        return super(AccountMoveLine, self)._onchange_product_id()

    @api.onchange('tax_ids')
    def _onchange_tax_ids(self):
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
            self.move_id.onchange_conversion_rate_ref()


    @api.onchange('product_uom_id')
    def _onchange_uom_id(self):
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
        return super(AccountMoveLine, self)._onchange_uom_id()

    @api.onchange('quantity')
    def _onchange_quantity(self):
        
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
            self.move_id.onchange_conversion_rate_ref()

    def _get_fields_onchange_subtotal_model(self, price_subtotal, move_type, currency, company, date):
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
        return super(AccountMoveLine, self)._get_fields_onchange_subtotal_model(price_subtotal, move_type, currency, company, date)

    def _recompute_debit_credit_from_amount_currency(self):
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
        return super(AccountMoveLine, self)._recompute_debit_credit_from_amount_currency()

    
    def _get_fields_onchange_balance(self, quantity=None, discount=None, amount_currency=None, move_type=None, currency=None, taxes=None, price_subtotal=None, force_computation=False):
        if self.move_id.show_conversion_rate:
            self = self.with_context(override_currency_rate=self.move_id.conversion_rate_ref)
        return super(AccountMoveLine, self)._get_fields_onchange_balance(quantity, discount, amount_currency, move_type, currency, taxes, price_subtotal, force_computation)
    
    
    def check_full_reconcile(self):
        for rec in self:
            if rec.move_id.show_conversion_rate:
                self = self.with_context(override_currency_rate=rec.move_id.conversion_rate_ref)
            return super(AccountMoveLine, self).check_full_reconcile()

    def _reconcile_lines(self, debit_moves, credit_moves, field):
        for rec in self:
            if rec.move_id.show_conversion_rate:
                self = self.with_context(override_currency_rate=rec.move_id.conversion_rate_ref)
            return super(AccountMoveLine, self)._reconcile_lines(debit_moves, credit_moves, field)
