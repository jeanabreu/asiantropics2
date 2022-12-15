# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
 
log = logging.getLogger(__name__)
 
  
class AccountPaymentInherited(models.Model):
    _inherit = "account.payment"
    
    apply_commision = fields.Boolean(string="Aplicar comisión")
    monthly_fixed_commission = fields.Monetary(string="Comisión mensual")
    visa_commision_fix = fields.Monetary(string="Ajuste visa")
    commision_type_id = fields.Many2one('cc_payment_commisions.journal_percentage', string="Tipo de comisión")
    provider_invoice_id = fields.Many2one('account.move', string="Factura de comisión")
    commission_with_iva = fields.Boolean(string="Comisión con IVA", default=False)
    cc_analytic_account_id = fields.Many2one('account.analytic.account', string="Cuenta analítica TC")
    
    def action_post(self):
        if self.provider_invoice_id:
            if self.provider_invoice_id.state != "posted":
                raise ValidationError('La factura %s no esta confirmada. Por favor validarla antes de publicar el pago' % self.provider_invoice_id.name)
            else:
                self.provider_invoice_id.write({"payment_state": "paid", "amount_residual": 0})
        res = super(AccountPaymentInherited, self).action_post()
        return res
    
    def _synchronize_to_moves(self, changed_fields):
        ''' Update the account.move regarding the modified account.payment.
        :param changed_fields: A list containing all modified fields on account.payment.
        '''
        
        if self.apply_commision:
        
            if self._context.get('skip_account_move_synchronization'):
                return

            if not any(field_name in changed_fields for field_name in (
                'date', 'amount', 'payment_type', 'partner_type', 'payment_reference', 'is_internal_transfer',
                'currency_id', 'partner_id', 'destination_account_id', 'partner_bank_id',
            )):
                return

            for pay in self.with_context(skip_account_move_synchronization=True):
                liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                # Make sure to preserve the write-off amount.
                # This allows to create a new payment with custom 'line_ids'.

                if writeoff_lines:
                    writeoff_amount = sum(writeoff_lines.mapped('amount_currency'))
                    counterpart_amount = counterpart_lines['amount_currency']
                    if writeoff_amount > 0.0 and counterpart_amount > 0.0:
                        sign = 1
                    else:
                        sign = -1

                    write_off_line_vals = {
                        'name': writeoff_lines[0].name,
                        'amount': writeoff_amount * sign,
                        'account_id': writeoff_lines[0].account_id.id,
                    }
                else:
                    write_off_line_vals = {}

                line_vals_list = pay._prepare_move_line_default_vals(write_off_line_vals=write_off_line_vals)
                
                
                line_ids_commands = [
                    (1, liquidity_lines.id, line_vals_list[0]),
                    (1, counterpart_lines[0].id, line_vals_list[1]),
                    (1, counterpart_lines[1].id, line_vals_list[2]),
                ]

                for line in writeoff_lines:
                    line_ids_commands.append((2, line.id))

                if writeoff_lines:
                    line_ids_commands.append((0, 0, line_vals_list[2]))

                # Update the existing journal items.
                # If dealing with multiple write-off lines, they are dropped and a new one is generated.
                
                
                pay.move_id.write({
                    'partner_id': pay.partner_id.id,
                    'currency_id': pay.currency_id.id,
                    'partner_bank_id': pay.partner_bank_id.id,
                    'line_ids': line_ids_commands,
                })
        else:
            super(AccountPaymentInherited, self)._synchronize_to_moves(changed_fields)        
    
    @api.model_create_multi
    def create(self, vals_list):
        
        res = super(AccountPaymentInherited, self).create(vals_list)
        for rec in res:        
            if rec.payment_type == 'inbound' and rec.journal_id.type == 'bank' and rec.journal_id.provider_ap_account and rec.apply_commision:
                final_amount = rec.amount
                bank_account_id = rec.journal_id.default_account_id.id
                if res.provider_invoice_id:
                    res.provider_invoice_id.cc_payment_id = res.id
                for line in rec.line_ids:
                    if bank_account_id != line.account_id.id:
                        final_amount += round(line.debit, 10)

                #res.write({"amount": final_amount})
        return res
    
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id.has_commission:
            self.apply_commision = True
            #self.destination_account_id = self.partner
        else:
            self.apply_commision = False
    
    
    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        :param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
            * amount:       The amount to be added to the counterpart amount.
            * name:         The label to set on the line.
            * account_id:   The account on which create the write-off.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}
        
        print('------------------------------------------------')
        print(self.apply_commision)
        print(self.payment_type)
        print(self.journal_id.type)
        print(self.journal_id.provider_ap_account)
        print('------------------------------------------------')
        
        
        if self.payment_type == 'inbound' and self.journal_id.type == 'bank' and self.journal_id.provider_ap_account and self.apply_commision:

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
            counterpart_balance = -liquidity_balance - write_off_balance
            currency_id = self.currency_id.id

            if self.is_internal_transfer:
                if self.payment_type == 'inbound':
                    liquidity_line_name = _('Transfer to %s', self.journal_id.name)
                else: # payment.payment_type == 'outbound':
                    liquidity_line_name = _('Transfer from %s', self.journal_id.name)
            else:
                liquidity_line_name = self.payment_reference

            # Compute a default label to set on the journal items.

            payment_display_name = self._prepare_payment_display_name()

            default_line_name = self.env['account.move.line']._get_default_line_name(
                _("Internal Transfer") if self.is_internal_transfer else payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
                self.amount,
                self.currency_id,
                self.date,
                partner=self.partner_id,
            )
            
            cc_analytic_account = self.cc_analytic_account_id
            if cc_analytic_account:
                line_vals_list = [
                    # Liquidity line.
                    {
                        'name': liquidity_line_name or default_line_name,
                        'date_maturity': self.date,
                        'amount_currency': liquidity_amount_currency,
                        'currency_id': currency_id,
                        'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                        'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                        'partner_id': self.partner_id.id,
                        'analytic_account_id': cc_analytic_account.id,
                        'account_id': self.outstanding_account_id.id,
                    },
                    # Receivable / Payable.
                    {
                        'name': self.payment_reference or default_line_name,
                        'date_maturity': self.date,
                        'amount_currency': counterpart_amount_currency,
                        'currency_id': currency_id,
                        'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
                        'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                        'partner_id': self.partner_id.id,
                        'analytic_account_id': cc_analytic_account.id,
                        'account_id': self.destination_account_id.id,
                    },
                ]
                if not self.currency_id.is_zero(write_off_amount_currency):
                    # Write-off line.
                    line_vals_list.append({
                        'name': write_off_line_vals.get('name') or default_line_name,
                        'amount_currency': write_off_amount_currency,
                        'currency_id': currency_id,
                        'debit': write_off_balance if write_off_balance > 0.0 else 0.0,
                        'credit': -write_off_balance if write_off_balance < 0.0 else 0.0,
                        'partner_id': self.partner_id.id,
                        'analytic_account_id': cc_analytic_account.id,
                        'account_id': write_off_line_vals.get('account_id'),
                    })
            else:
                line_vals_list = [
                    # Liquidity line.
                    {
                        'name': liquidity_line_name or default_line_name,
                        'date_maturity': self.date,
                        'amount_currency': liquidity_amount_currency,
                        'currency_id': currency_id,
                        'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                        'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                        'partner_id': self.partner_id.id,
                        'account_id': self.outstanding_account_id.id,
                    },
                    # Receivable / Payable.
                    {
                        'name': self.payment_reference or default_line_name,
                        'date_maturity': self.date,
                        'amount_currency': counterpart_amount_currency,
                        'currency_id': currency_id,
                        'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
                        'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                        'partner_id': self.partner_id.id,
                        'account_id': self.destination_account_id.id,
                    },
                ]
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
                    
            comm_fixed = self.journal_id.provider_commission_fixed
            comm_perc = self.commision_type_id.provider_commission_percent
            
            credit_account = False
            if self.payment_method_line_id:
                payment_method_id = self.payment_method_line_id.id
                
                for journal_payment_method in self.journal_id.inbound_payment_method_line_ids:
                    
                    if journal_payment_method.id == payment_method_id and journal_payment_method.payment_account_id:
                        credit_account = journal_payment_method.payment_account_id
                if not credit_account:
                    credit_account = self.company_id.account_journal_payment_debit_account_id    
            else:
                credit_account = self.company_id.account_journal_payment_debit_account_id
            
            country = self.journal_id.commision_country
            company_currency = self.company_id.currency_id
            
            for line in line_vals_list:

                if line['account_id'] == credit_account.id:
                    
                    fixed_comm_pay_curr = comm_fixed
                    if self.journal_id.currency_id != self.currency_id:
                        # Multi-currencies AND journal_currency != payment_currency --> Convert amount to payment currency
                        fixed_comm_pay_curr = self.journal_id.currency_id._convert(comm_fixed, self.currency_id, self.company_id, self.date)
                        
                    currency_id = False
                    fixed_comm_comp_curr = fixed_comm_pay_curr
                    
                    if self.currency_id != company_currency:
                        # Multi-currencies AND payment_currency != company_currency --> Convert amount to company currency
                        currency_id = self.currency_id.id
                        fixed_comm_comp_curr = self.currency_id._convert(fixed_comm_pay_curr, company_currency, self.company_id, self.date)
                    else:
                        currency_id = self.currency_id.id
                    
                    debit = line['debit']
                    amount_currency = line['amount_currency']
                    
                    comm_comp_curr = fixed_comm_comp_curr + (comm_perc/100) * debit
                    comm_pay_curr = fixed_comm_pay_curr + (comm_perc/100) * amount_currency
                    
                    ####### EL SALVADOR
                    if country == "sv":
                        base_amount = comm_comp_curr
                        #base_amount = base_amount * 0.13
                        base_amount = round(base_amount, 2)
                        base_commission_amount = (base_amount / 1.13)
                        base_commission_amount = round(base_commission_amount, 2)
                        iva_commission_amount = base_commission_amount * 0.13
                        iva_commission_amount = iva_commission_amount
                        iva_retencion = (debit / 1.13) * 0.02
                        
                        print('---------------------------- BASE 1')
                        print('BASE Comisino',base_commission_amount)
                        print('IVA Comisino',iva_commission_amount)
                        print('BASE ',base_amount)
                        print('IVA RET',iva_retencion)
                        
                        
                        iva_retencion = round(iva_retencion, 2)
                        
                        base_commission_amount = self.monthly_fixed_commission + base_commission_amount + self.visa_commision_fix
                        base_amount = base_commission_amount + iva_retencion + iva_commission_amount
                        commision_amount = base_commission_amount + iva_commission_amount
                        
                        transit_amount = iva_retencion + commision_amount
                        print('TRANSITO',transit_amount)
                        print('Comision', commision_amount)
                        #raise ValidationError('STOP !')
                        print('---------------------------- BASE 1')
                        
                        comm_comp_curr = base_amount
                        comm_pay_curr = base_amount
                        
                        comm_comp_curr = round(comm_comp_curr, 2)
                        comm_pay_curr = round(comm_pay_curr, 2)
                        
                        line['debit'] = debit - comm_comp_curr
                        line['amount_currency'] = amount_currency - comm_pay_curr
                        """
                        line_vals_list.append({
                            'name': self.journal_id.account_move_name_desc,
                            'amount_currency': iva_retencion if currency_id else 0.0,
                            'debit': iva_retencion,
                            'currency_id': currency_id,
                            'credit': 0.0,
                            'date_maturity': self.date, 
                            'partner_id': self.partner_id.commercial_partner_id.id,
                            'account_id': self.journal_id.percentage_cc_account.id,
                            #'payment_id': self.id,
                        })
                        """
                        
                        line_vals_list.append({
                            'name': self.journal_id.account_move_name_desc,
                            'amount_currency': commision_amount if currency_id else 0.0,
                            'debit': transit_amount,
                            'currency_id': currency_id,
                            'credit': 0.0,
                            'date_maturity': self.date,
                            'partner_id': self.partner_id.commercial_partner_id.id,
                            'account_id': self.journal_id.provider_ap_account.id,
                            #'payment_id': self.id,
                        })
                        """
                        line_vals_list.append({
                            'name': self.journal_id.account_move_name_desc,
                            'amount_currency': iva_commission_amount if currency_id else 0.0,
                            'debit': iva_commission_amount,
                            'currency_id': currency_id,
                            'credit': 0.0,
                            'date_maturity': self.date,
                            'partner_id': self.partner_id.commercial_partner_id.id,
                            'account_id': self.journal_id.cc_fiscal_debit_account.id,
                            #'payment_id': self.id,
                        })
                        """
                        print(line_vals_list)
                    ####### GUATEMALA
                    
                    if country == "gt":
                        
                        if self.commission_with_iva:
                        
                            base_amount = comm_comp_curr
                            base_amount = base_amount * 0.12
                            base_amount = round(base_amount, 10)
                            iva_retencion = (debit / 1.12) * 0.12
                            
                            
                            iva_retencion = iva_retencion * 0.15
                            iva_retencion = round(iva_retencion, 10)
                            base_amount = base_amount + iva_retencion
                            
                            comm_comp_curr += self.monthly_fixed_commission + base_amount + self.visa_commision_fix
                            comm_pay_curr += self.monthly_fixed_commission + base_amount + self.visa_commision_fix
                            
                        
                            comm_comp_curr = round(comm_comp_curr, 10)
                            comm_pay_curr = round(comm_pay_curr, 10)
                        else:
                            payment_amount = fixed_comm_comp_curr + debit
                            payment_amount_curr = fixed_comm_pay_curr + amount_currency
                            
                            if payment_amount == payment_amount_curr:
                                payment_amount_without_iva = payment_amount / 1.12
                            else:
                                payment_amount_without_iva = payment_amount_curr / 1.12

                            iva_amount = payment_amount_without_iva * 0.12
                            comm_comp_curr = (comm_perc/100) * payment_amount_without_iva
                            iva_commission_amount = comm_comp_curr * 0.12
                            iva_retencion_commission = 0
                            if self.journal_id.commision_type == "cc":
                                iva_retencion_commission = iva_amount * 0.15
                            
                            comm_comp_curr = comm_comp_curr + iva_commission_amount + iva_retencion_commission
                            
                            if payment_amount != payment_amount_curr:
                                comm_pay_curr = comm_comp_curr
                                comm_comp_curr = comm_pay_curr * self.conversion_rate_ref
                                

                            comm_comp_curr += self.monthly_fixed_commission + self.visa_commision_fix
                            comm_pay_curr += self.monthly_fixed_commission + self.visa_commision_fix
                            
                            
                            comm_comp_curr = round(comm_comp_curr, 2)
                            comm_pay_curr = round(comm_pay_curr, 2)
                        
                        line['debit'] = debit - comm_comp_curr
                        line['amount_currency'] = amount_currency - comm_pay_curr
                        #raise ValidationError('STOP!')
                        if cc_analytic_account:
                            if payment_amount == payment_amount_curr:
                                line_vals_list.append({
                                    'name': self.journal_id.account_move_name_desc,
                                    'amount_currency': comm_pay_curr if currency_id else 0.0,
                                    'debit': comm_comp_curr,
                                    'currency_id': currency_id,
                                    'credit': 0.0,
                                    'date_maturity': self.date,
                                    'analytic_account_id': cc_analytic_account.id,
                                    'partner_id': self.partner_id.commercial_partner_id.id,
                                    'account_id': self.journal_id.provider_ap_account.id,
                                    #'payment_id': self.id,
                                })
                            else:
                                line_vals_list.append({
                                    'name': self.journal_id.account_move_name_desc,
                                    'amount_currency': comm_pay_curr if currency_id else 0.0,
                                    'debit': comm_comp_curr,
                                    'currency_id': currency_id,
                                    'credit': 0.0,
                                    'date_maturity': self.date,
                                    'analytic_account_id': cc_analytic_account.id,
                                    'partner_id': self.partner_id.commercial_partner_id.id,
                                    'account_id': self.journal_id.provider_ap_account.id,
                                    #'payment_id': self.id,
                                })
                        else:
                            if payment_amount == payment_amount_curr:
                                line_vals_list.append({
                                    'name': self.journal_id.account_move_name_desc,
                                    'amount_currency': comm_pay_curr if currency_id else 0.0,
                                    'debit': comm_comp_curr,
                                    'currency_id': currency_id,
                                    'credit': 0.0,
                                    'date_maturity': self.date,
                                    'partner_id': self.partner_id.commercial_partner_id.id,
                                    'account_id': self.journal_id.provider_ap_account.id,
                                    #'payment_id': self.id,
                                })
                            else:
                                line_vals_list.append({
                                    'name': self.journal_id.account_move_name_desc,
                                    'amount_currency': comm_pay_curr if currency_id else 0.0,
                                    'debit': comm_comp_curr,
                                    'currency_id': currency_id,
                                    'credit': 0.0,
                                    'date_maturity': self.date,
                                    'partner_id': self.partner_id.commercial_partner_id.id,
                                    'account_id': self.journal_id.provider_ap_account.id,
                                    #'payment_id': self.id,
                                })
                            
                        self.write({'apply_commision': True})
                        
                    break
            
            return line_vals_list
        else:
            all_move_vals = super(AccountPaymentInherited, self)._prepare_move_line_default_vals(write_off_line_vals)
            return all_move_vals
    
    
    
    def _synchronize_from_moves(self, changed_fields):
        ''' Update the account.payment regarding its related account.move.
        Also, check both models are still consistent.
        :param changed_fields: A set containing all modified fields on account.move.
        '''
        if self._context.get('skip_account_move_synchronization'):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):
            
            
            if pay.payment_type == 'inbound' and pay.journal_id.type == 'bank' and pay.journal_id.provider_ap_account and pay.apply_commision:
            

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
                    
                    print('-----------------------')
                    print(counterpart_lines)
                    print(liquidity_lines)
                    print('-----------------------')

                    '''if len(liquidity_lines) != 1 or len(counterpart_lines) != 1:
                        raise UserError(_(
                            "The journal entry %s reached an invalid state relative to its payment.\n"
                            "To be consistent, the journal entry must always contains:\n"
                            "- one journal item involving the outstanding payment/receipts account.\n"
                            "- one journal item involving a receivable/payable account.\n"
                            "- optional journal items, all sharing the same account.\n\n"
                        ) % move.display_name)'''

                    """
                    if writeoff_lines and len(writeoff_lines.account_id) != 1:
                        raise UserError(_(
                            "The journal entry %s reached an invalid state relative to its payment.\n"
                            "To be consistent, all the write-off journal items must share the same account."
                        ) % move.display_name)
                    """

                    if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                        raise UserError(_(
                            "The journal entry %s reached an invalid state relative to its payment.\n"
                            "To be consistent, the journal items must share the same currency."
                        ) % move.display_name)

                    if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                        raise UserError(_(
                            "The journal entry %s reached an invalid state relative to its payment.\n"
                            "To be consistent, the journal items must share the same partner."
                        ) % move.display_name)

                    partner_type = 'customer'
                    '''if counterpart_lines.account_id.user_type_id.type == 'receivable':
                        partner_type = 'customer'
                    else:
                        partner_type = 'supplier'''

                    liquidity_amount = liquidity_lines.amount_currency
                    
                    move_vals_to_write.update({
                        'currency_id': liquidity_lines.currency_id.id,
                        'partner_id': liquidity_lines.partner_id.id,
                    })
                    payment_vals_to_write.update({
                        'amount': abs(liquidity_amount),
                        'payment_type': 'inbound' if liquidity_amount > 0.0 else 'outbound',
                        'partner_type': partner_type,
                        'currency_id': liquidity_lines.currency_id.id,
                        'destination_account_id': counterpart_lines[0].account_id.id,
                        'partner_id': liquidity_lines.partner_id.id,
                    })

                move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
                pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))
            else:
                all_move_vals = super(AccountPaymentInherited, self)._synchronize_from_moves(changed_fields)
            