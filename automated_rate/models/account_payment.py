# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from decimal import Decimal, ROUND_HALF_UP
from odoo.exceptions import UserError, ValidationError


class account_payment(models.Model):
    _inherit = 'account.payment'

    # conversion_rate_ref = fields.Float(string="Tasa de conversión", compute="get_conversion_rate_reference", digits=(16, 5))
    conversion_rate_ref = fields.Float(string="Tasa de conversión", default=lambda self: self.get_conversion_rate_reference_default(), digits=(16, 10))
    conversion_rate_ref_readonly_store = fields.Float(string="Tasa de conversión", digits=(16, 10))
    show_conversion_rate = fields.Boolean(compute="check_currency")

    payment_check_user_group = fields.Boolean(default=lambda self: self.get_rate_user_group(), string="DATA")

    @api.model
    def create(self, vals):
        if 'conversion_rate_ref_readonly_store' in vals:
            vals.update({'conversion_rate_ref': vals.get('conversion_rate_ref_readonly_store')})
            self = self.with_context(override_currency_rate=vals.get('conversion_rate_ref_readonly_store'))
        return super(account_payment, self).create(vals)

    def write(self, vals):
        if 'conversion_rate_ref_readonly_store' in vals:
            vals.update({'conversion_rate_ref': vals.get('conversion_rate_ref_readonly_store')})
            self = self.with_context(override_currency_rate=vals.get('conversion_rate_ref_readonly_store'))
        
        res = super(account_payment, self).write(vals)
        
        if self.move_id and self.state == 'draft':
            if self.move_id.show_conversion_rate:
                self.move_id.write({"conversion_rate_ref": self.conversion_rate_ref, "conversion_rate_ref_readonly_store": self.conversion_rate_ref})
                self.move_id.onchange_conversion_rate_ref()
            else:
                self.move_id.write({"show_conversion_rate": True,"conversion_rate_ref": self.conversion_rate_ref, "conversion_rate_ref_readonly_store": self.conversion_rate_ref})
                self.move_id.onchange_conversion_rate_ref()
        
        return res

    def get_rate_user_group(self):
        can_edit = self.env['res.users'].has_group('automated_rate.group_change_rate')
        return can_edit


    @api.onchange('date')
    def onchange_date(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        account_move_currency = self.currency_id.id
        self.show_conversion_rate = False
        if company_currency_id != account_move_currency:
            self.show_conversion_rate = True
            conversion_rate = self.currency_id.with_context(date=self.date).rate
            if conversion_rate > 0:
                conversion_rate = 1 / conversion_rate
            self.conversion_rate_ref = round(conversion_rate, 10)
            self.conversion_rate_ref_readonly_store = self.conversion_rate_ref

    @api.onchange('currency_id')
    def onchange_currency_id(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        account_move_currency = self.currency_id.id
        self.show_conversion_rate = False
        if company_currency_id != account_move_currency:
            self.show_conversion_rate = True
            conversion_rate = self.currency_id.with_context(date=self.date).rate
            if conversion_rate > 0:
                conversion_rate = 1 / conversion_rate
            self.conversion_rate_ref = round(conversion_rate, 10)
            self.conversion_rate_ref_readonly_store = self.conversion_rate_ref

    def check_currency(self):
        for rec in self:
            company_currency_id = self.env.user.company_id.currency_id.id
            account_move_currency = rec.currency_id.id
            rec.show_conversion_rate = False
            if company_currency_id != account_move_currency:
                rec.show_conversion_rate = True

    @api.onchange('conversion_rate_ref')
    def onchange_conversion_rate_ref(self):
        if self.show_conversion_rate:
            self.conversion_rate_ref_readonly_store = self.conversion_rate_ref

    def get_conversion_rate_reference_default(self):

        company_currency_id = self.env.user.company_id.currency_id.id
        account_move_currency = self.currency_id.id
        conversion_rate_ref = 0.00
        if company_currency_id != account_move_currency:
            conversion_rate = self.currency_id.with_context(date=self.date).rate
            if conversion_rate > 0:
                conversion_rate = 1 / conversion_rate
            conversion_rate_ref = round(conversion_rate, 10)

        return conversion_rate_ref

    def get_conversion_rate_reference(self):
        for rec in self:
            company_currency_id = self.env.user.company_id.currency_id.id
            account_move_currency = rec.currency_id.id
            rec.conversion_rate_ref = 0.00
            if company_currency_id != account_move_currency:
                conversion_rate = self.currency_id.with_context(date=self.date).rate
                if conversion_rate > 0:
                    conversion_rate = 1 / conversion_rate
                rec.conversion_rate_ref = round(conversion_rate, 10)
                rec.conversion_rate_ref_readonly_store = self.conversion_rate_ref

    def action_post(self):
        for rec in self:
            if rec.show_conversion_rate:
                self = rec.with_context(override_currency_rate=rec.conversion_rate_ref)
        return super(account_payment, self).action_post()

    """ @api.model
    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        res = super(account_payment, self)._prepare_move_line_default_vals(write_off_line_vals=None)
        res.update({'conversion_rate_ref': self.conversion_rate_ref})
        return res """
        
