# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from decimal import Decimal, ROUND_HALF_UP
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger()


class CurrencyExt(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _register_hook(self):
        def _convert_enhanced(self, from_amount, to_currency, company, date, round=True):
            """Returns the converted amount of ``from_amount``` from the currency
               ``self`` to the currency ``to_currency`` for the given ``date`` and
               company.

               :param company: The company from which we retrieve the convertion rate
               :param date: The nearest date from which we retriev the conversion rate.
               :param round: Round the result or not
            """
            self, to_currency = self or to_currency, to_currency or self
            assert self, "convert amount from unknown currency"
            assert to_currency, "convert amount to unknown currency"
            assert company, "convert amount from unknown company"
            assert date, "convert amount from unknown date"
            _logger.info('Convert ' + str(from_amount) + ' From ' + str(self.name) + ' to ' + str(to_currency.name))

            # apply conversion rate
            if self == to_currency:
                to_amount = from_amount
            else:
                conversion_rate = self._context.get('override_currency_rate', False)
                #print('CONTEXT', self._context)
                _logger.info('Override conversion rate ' + str(conversion_rate))
                if not conversion_rate:
                    #print('CONTEXT', self._context)
                    model_data = self._context.get('params', False)
                    account_move_id = False
                    if model_data:
                        if 'model' in model_data:
                            #print('-------MODEL---------', model_data['model'])
                            if model_data['model'] == 'account.move':
                                if 'id' in model_data:
                                    account_move_id = model_data['id']
                                    account_move_data = self.env['account.move'].browse(account_move_id)
                                    if account_move_data.conversion_rate_ref:
                                        conversion_rate = account_move_data.conversion_rate_ref
                                        self = self.with_context(override_currency_rate=conversion_rate)
                    if not account_move_id:
                        conversion_rate = self._get_conversion_rate(self, to_currency, company, date)
                _logger.info('Conversion rate' + str(conversion_rate))
                to_amount = from_amount * conversion_rate
            # apply rounding
            _logger.info(str(to_amount) + ' Converted FROM ' + str(from_amount))
            return to_currency.round(to_amount) if round else to_amount

        @api.model
        def _get_conversion_rate_enhanced(self, from_currency, to_currency, company, date):
            _logger.info('Get conversion rate from ' + str(from_currency.name) + ' to ' + str(to_currency.name) + ' date ' + str(date))
            res = self._context.get('override_currency_rate', False)
            _logger.info('--Override conversion rate ' + str(res))
            if not res:
                currency_rates = (from_currency + to_currency)._get_rates(company, date)
                # logger.info('Currency Rates are ' + str(currency_rates))
                res = currency_rates.get(to_currency.id) / currency_rates.get(from_currency.id)
            _logger.info(str(res) + ' conversion rate from ' + str(from_currency.name) + ' to ' + str(to_currency.name) + ' date ' + str(date))
            # print(what)
            return res

        Currency._convert = _convert_enhanced
        Currency._get_conversion_rate = _get_conversion_rate_enhanced
        return super(CurrencyExt, self)._register_hook()


class Currency(models.Model):
    _inherit = 'res.currency'

    '''@api.model
    def _convert_fixed(self, from_amount, to_currency, company, date, rate, round=True):

        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"
        assert company, "convert amount from unknown company"
        assert date, "convert amount from unknown date"
        # apply conversion rate
        print('Conversion rate fixed called', from_amount, rate)
        if self == to_currency:
            print('NOTRATE------------------------------')
            to_amount = from_amount
        else:
            to_amount = from_amount * rate
        # apply rounding
        return to_currency.round(to_amount) if round else to_amount'''
