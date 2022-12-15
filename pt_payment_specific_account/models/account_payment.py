# -*- coding: utf-8 -*-

from odoo.addons import decimal_precision as dp
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class account_payment(models.Model):
    _inherit = "account.payment"

    enable_direct_account = fields.Boolean(string="Registro a", default=False)
    direct_account_id = fields.Many2one('account.account', string="Cuenta contable")
    direct_payment_reason = fields.Char(string="Motivo de pago directo")
    
    mutilple_account_ids = fields.One2many('pt_payment_specific_account.multiple_account_payments', 'payment_id', string="Cuentas")
    mutilple_account_discount_ids = fields.One2many('pt_payment_specific_account.multiple_account_discounts', 'payment_id', string="Descuentos")
    
    @api.onchange('amount')
    def _onchange_amount(self):
        if self.enable_direct_account:        
            total = 0
            discount = 0
            for line in self.mutilple_account_ids:
                total += line.amount
            for line in self.mutilple_account_discount_ids:
                discount += line.amount
            
            amount = total - discount
            if amount != self.amount:
                raise ValidationError('El monto a pagar debe ser igual a la sumatoria de la distribución de cuentas')

    @api.onchange('mutilple_account_discount_ids')
    def _onchange_mutilple_account_discount_ids(self):        
        total = 0
        discount = 0
        for line in self.mutilple_account_ids:
            total += line.amount
        for line in self.mutilple_account_discount_ids:
            discount += line.amount

        #self.analytic_account_register = True
        amount = total - discount
        if amount <= 0 and total > 0 and discount > 0:
            raise ValidationError('El monto a pagar debe ser mayor a cero')
        self.amount = amount
    
    @api.onchange('mutilple_account_ids')
    def _onchange_mutilple_account_ids(self):        
        total = 0
        discount = 0
        for line in self.mutilple_account_ids:
            total += line.amount
        for line in self.mutilple_account_discount_ids:
            discount += line.amount

        #self.analytic_account_register = True
        amount = total - discount
        if amount <= 0 and total > 0 and discount > 0:
            raise ValidationError('El monto a pagar debe ser mayor a cero')
        self.amount = amount


    def _seek_for_lines(self):
        ''' Helper used to dispatch the journal items between:
        - The lines using the temporary liquidity account.
        - The lines using the counterpart account.
        - The lines being the write-off lines.
        :return: (liquidity_lines, counterpart_lines, writeoff_lines)
        '''
        if not self.enable_direct_account:
            return super(account_payment,self)._seek_for_lines()
        else:
            
            self.ensure_one()

            liquidity_lines = self.env['account.move.line']
            counterpart_lines = self.env['account.move.line']
            writeoff_lines = self.env['account.move.line']
            
            multiple_account_ids = []
            for line in self.mutilple_account_ids:
                multiple_account_ids.append(line.account_id.id)
            
            for line in self.move_id.line_ids:
                if line.account_id in self._get_valid_liquidity_accounts():
                    liquidity_lines += line
                elif line.account_id.id in multiple_account_ids or line.partner_id == line.company_id.partner_id:
                    counterpart_lines += line
                else:
                    writeoff_lines += line

            return liquidity_lines, counterpart_lines, writeoff_lines

    
    def _synchronize_from_moves(self, changed_fields):
        ''' Update the account.payment regarding its related account.move.
        Also, check both models are still consistent.
        :param changed_fields: A set containing all modified fields on account.move.
        '''
    
        if self._context.get('skip_account_move_synchronization'):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):
            if not pay.enable_direct_account:
                super(account_payment,self)._synchronize_from_moves(changed_fields)
            else:

                # After the migration to 14.0, the journal entry could be shared between the account.payment and the
                # account.bank.statement.line. In that case, the synchronization will only be made with the statement line.
                if pay.move_id.statement_line_id:
                    continue

                move = pay.move_id
                move_vals_to_write = {}
                payment_vals_to_write = {}

                if 'journal_id' in changed_fields:
                    if pay.journal_id.type not in ('bank', 'cash'):
                        raise UserError(_("A payment must always belongs to a bank or cash journal."))

                if 'line_ids' in changed_fields:
                    all_lines = move.line_ids
                    liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                    """if len(liquidity_lines) != 1:
                        raise UserError(_(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "include one and only one outstanding payments/receipts account.",
                            move.display_name,
                        ))

                    if len(counterpart_lines) != 1:
                        raise UserError(_(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "include one and only one receivable/payable account (with an exception of "
                            "internal transfers).",
                            move.display_name,
                        ))"""

                    if writeoff_lines and len(writeoff_lines.account_id) != 1:
                        raise UserError(_(
                            "Journal Entry %s is not valid. In order to proceed, "
                            "all optional journal items must share the same account.",
                            move.display_name,
                        ))

                    if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                        raise UserError(_(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "share the same currency.",
                            move.display_name,
                        ))

                    if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                        raise UserError(_(
                            "Journal Entry %s is not valid. In order to proceed, the journal items must "
                            "share the same partner.",
                            move.display_name,
                        ))

                    liquidity_amount = liquidity_lines.amount_currency

                    move_vals_to_write.update({
                        'currency_id': liquidity_lines.currency_id.id,
                        'partner_id': liquidity_lines.partner_id.id,
                    })
                    
                    for counterpart_line in counterpart_lines:
                        
                        if counterpart_line.account_id.user_type_id.type == 'receivable':
                            partner_type = 'customer'
                        else:
                            partner_type = 'supplier'
                        payment_vals_to_write.update({
                            'amount': abs(counterpart_line.debit - counterpart_line.credit),
                            'partner_type': partner_type,
                            'currency_id': liquidity_lines.currency_id.id,
                            'destination_account_id': counterpart_line.account_id.id,
                            'partner_id': liquidity_lines.partner_id.id,
                        })
                    if liquidity_amount > 0.0:
                        payment_vals_to_write.update({'payment_type': 'inbound'})
                    elif liquidity_amount < 0.0:
                        payment_vals_to_write.update({'payment_type': 'outbound'})

                move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
                pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))
        
        return    
    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}
        line_vals_list = []
        if not self.enable_direct_account:
            line_vals_list = super(account_payment,self)._prepare_move_line_default_vals(write_off_line_vals)
            return line_vals_list
        else:
            write_off_line_vals = write_off_line_vals or {}

            if not self.outstanding_account_id:
                raise UserError(_(
                    "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
                    self.payment_method_line_id.name, self.journal_id.display_name))

            # Compute amounts.
            write_off_amount_currency = write_off_line_vals.get('amount', 0.0)

            if self.payment_type == 'inbound':
                # Receive money.
                liquidity_amount_currency = self.amount
            elif self.payment_type == 'outbound':
                # Send money.
                liquidity_amount_currency = -self.amount
                write_off_amount_currency *= -1
            else:
                liquidity_amount_currency = write_off_amount_currency = 0.0

            write_off_balance = self.currency_id._convert(
                write_off_amount_currency,
                self.company_id.currency_id,
                self.company_id,
                self.date,
            )
            liquidity_balance = self.currency_id._convert(
                liquidity_amount_currency,
                self.company_id.currency_id,
                self.company_id,
                self.date,
            )
            counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
            
            currency_id = self.currency_id.id

            if self.is_internal_transfer:
                if self.payment_type == 'inbound':
                    liquidity_line_name = _('Transfer to %s', self.journal_id.name)
                else: # payment.payment_type == 'outbound':
                    liquidity_line_name = _('Transfer from %s', self.journal_id.name)
            else:
                liquidity_line_name = self.payment_reference

            # Compute a default label to set on the journal items.

            payment_display_name = {
                'outbound-customer': _("Customer Reimbursement"),
                'inbound-customer': _("Customer Payment"),
                'outbound-supplier': _("Vendor Payment"),
                'inbound-supplier': _("Vendor Reimbursement"),
            }

            default_line_name = self.env['account.move.line']._get_default_line_name(
                _("Internal Transfer") if self.is_internal_transfer else payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
                self.amount,
                self.currency_id,
                self.date,
                partner=self.partner_id,
            )
            liquidity_line = {
                'name': liquidity_line_name or default_line_name,
                'date_maturity': self.date,
                'amount_currency': liquidity_amount_currency,
                'currency_id': currency_id,
                'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.outstanding_account_id.id,
            }
            line_vals_list.append(liquidity_line)

            for account in self.mutilple_account_ids:
                if self.payment_type == 'inbound':
                    counterpart_balance = -account.amount - write_off_balance
                    counterpart_amount_currency = -account.amount - write_off_amount_currency
                if self.payment_type == 'outbound':
                    counterpart_balance = account.amount - write_off_balance
                    counterpart_amount_currency = account.amount - write_off_amount_currency
                
                line_id =  {
                        'name': self.payment_reference or default_line_name,
                        'date_maturity': self.date,
                        'amount_currency': counterpart_amount_currency,
                        'currency_id': currency_id,
                        'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
                        'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                        'analytic_account_id': account.analytic_account_id.id,
                        'partner_id': self.partner_id.id,
                        'account_id': account.account_id.id,
                    }
                line_vals_list.append(line_id)
                
            if not self.currency_id.is_zero(write_off_amount_currency):
                # Write-off line.
                line_vals_list.append({
                    'name': write_off_line_vals.get('name') or default_line_name,
                    'amount_currency': write_off_amount_currency,
                    'currency_id': currency_id,
                    'debit': write_off_balance if write_off_balance > 0.0 else 0.0,
                    'credit': -write_off_balance if write_off_balance < 0.0 else 0.0,
                    'partner_id': self.partner_id.id,
                    'account_id': write_off_line_vals.get('account_id'),
                })

            
            return line_vals_list
        
    @api.model_create_multi
    def create(self, vals_list):
        res = super(account_payment, self).create(vals_list)
        for rec in self:
            if rec.enable_direct_account:
                total = 0
                discount = 0
                for line in rec.mutilple_account_ids:
                    total += line.amount
                for line in rec.mutilple_account_discount_ids:
                    discount += line.amount

                amount = total - discount
                if amount <= 0 and total > 0 and discount > 0:
                    raise ValidationError('El monto a pagar debe ser mayor a cero')
                vals_list['amount'] = amount
        return res
