# -*- coding: utf-8 -*-

import copy
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.misc import formatLang, format_date, parse_date


class AccountReconciliation(models.AbstractModel):
    _inherit = "account.reconciliation.widget"
    
    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        """ Handles data sent from the bank statement reconciliation widget
            (and can otherwise serve as an old-API bridge)

            :param st_line_ids
            :param list of dicts data: must contains the keys
                'counterpart_aml_dicts', 'payment_aml_ids' and 'new_aml_dicts',
                whose value is the same as described in process_reconciliation
                except that ids are used instead of recordsets.
            :returns dict: used as a hook to add additional keys.
        """
        st_lines = self.env['account.bank.statement.line'].browse(st_line_ids)
        ctx = dict(self._context, force_price_include=False)

        for st_line, datum in zip(st_lines, data):
            if datum.get('partner_id') is not None:
                st_line.write({'partner_id': datum['partner_id']})
            
            if st_line.move_id.state == "draft":
                st_line.move_id._post(soft=False)
                print(st_line.move_id.state)
            st_line.with_context(ctx).reconcile(datum.get('lines_vals_list', []), to_check=datum.get('to_check', False))
        return {'statement_line_ids': st_lines, 'moves': st_lines.move_id}

    @api.model
    def _get_search_domain(self, search_str=''):
        domain = super(AccountReconciliation, self)._get_search_domain(search_str)
        domain = expression.OR([domain, [('move_id.bank_operation_ref', 'ilike', search_str)]])
        return domain

    @api.model
    def _prepare_js_reconciliation_widget_move_line(self, statement_line, line, recs_count=0):
        ret = super(AccountReconciliation, self)._prepare_js_reconciliation_widget_move_line(statement_line, line, recs_count)
        ret['bank_operation_ref'] = line.move_id.bank_operation_ref or ''
        return ret
        
    @api.model
    def _prepare_move_lines(self, move_lines, target_currency=False, target_date=False, recs_count=0):

        ret = super(AccountReconciliation, self)._prepare_move_lines(move_lines)
        context = dict(self._context or {})
        ret_bank_ref = []
        ret_counter = 0
        for line in move_lines:
            ret[ret_counter]['bank_operation_ref'] = line.move_id.bank_operation_ref or ''
            ret_counter += 1

        return ret

    @api.model
    def _process_move_lines(self, move_line_ids, new_mv_line_dicts):
        """ Create new move lines from new_mv_line_dicts (if not empty) then call reconcile_partial on self and new move lines

            :param new_mv_line_dicts: list of dicts containing values suitable for account_move_line.create()
        """
        if len(move_line_ids) < 1 or len(move_line_ids) + len(new_mv_line_dicts) < 2:
            raise UserError(_('A reconciliation must involve at least 2 move lines.'))

        move_lines = self.env['account.move.line'].browse(move_line_ids)

        # Create writeoff move lines
        if len(new_mv_line_dicts) > 0:
            move_vals_list = self._prepare_writeoff_move_vals(move_lines, new_mv_line_dicts)
            moves = self.env['account.move'].create(move_vals_list)
            moves.action_post()
            account = move_lines[0].account_id
            move_lines |= moves.line_ids.filtered(lambda line: line.account_id == account and not line.reconciled)
        move_lines.reconcile()

    @api.model
    def _domain_move_lines_for_reconciliation(self, st_line, aml_accounts, partner_id, excluded_ids=[], search_str=False, mode='rp'):
        domain = super(AccountReconciliation, self)._domain_move_lines_for_reconciliation(st_line, aml_accounts, partner_id, excluded_ids, search_str)
        domain = expression.OR([domain, [('move_id.bank_operation_ref', 'ilike', search_str)]])
        return domain

    @api.model
    def _get_statement_line(self, st_line):
        ret = super(AccountReconciliation, self)._get_statement_line(st_line)
        ret['bank_operation_ref'] = st_line.bank_operation_ref or ''
        return ret
    
    
    @api.model
    def get_bank_statement_line_data(self, st_line_ids, excluded_ids=None):
        """ Returns the data required to display a reconciliation widget, for
            each statement line in self

            :param st_line_id: ids of the statement lines
            :param excluded_ids: optional move lines ids excluded from the
                result
        """
        results = {
            'lines': [],
            'value_min': 0,
            'value_max': 0,
            'reconciled_aml_ids': [],
        }
        
        if not st_line_ids:
            return results

        excluded_ids = excluded_ids or []

        # Make a search to preserve the table's order.
        bank_statement_lines = self.env['account.bank.statement.line'].search([('id', 'in', st_line_ids)])
        results['value_max'] = len(bank_statement_lines)
        reconcile_model = self.env['account.reconcile.model'].search([('rule_type', '!=', 'writeoff_button')])

        # Search for missing partners when opening the reconciliation widget.
        partner_map = self._get_bank_statement_line_partners(bank_statement_lines)

        matching_amls = reconcile_model._apply_rules(bank_statement_lines, excluded_ids=excluded_ids, partner_map=partner_map)

        # Iterate on st_lines to keep the same order in the results list.
        bank_statements_left = self.env['account.bank.statement']
        payment_debit_account_id = []
        payment_credit_account_id = []
        print('----------------------------------- RECONCILE -----------------------------------')
        for line in bank_statement_lines:
            payment_debit_account_id.append(line.journal_id.company_id.account_journal_payment_debit_account_id.id)
            payment_credit_account_id.append(line.journal_id.company_id.account_journal_payment_credit_account_id.id)
            
            for payment_method in line.journal_id.inbound_payment_method_line_ids:
                if payment_method.payment_account_id:
                    payment_debit_account_id.append(payment_method.payment_account_id.id)
                    
            for payment_method in line.journal_id.outbound_payment_method_line_ids:
                if payment_method.payment_account_id:
                    payment_credit_account_id.append(payment_method.payment_account_id.id)
                
            if matching_amls[line.id].get('status') == 'reconciled':
                reconciled_move_lines = matching_amls[line.id].get('reconciled_lines')
                results['value_min'] += 1
                results['reconciled_aml_ids'] += reconciled_move_lines and reconciled_move_lines.ids or []
            else:
                aml_ids = matching_amls[line.id]['aml_ids']
                bank_statements_left += line.statement_id
                
                
                print(aml_ids)
                
                
                if len(aml_ids) > 0:
                    amls = aml_ids and self.env['account.move.line'].browse(aml_ids)
                    
                    filtered_amls = []
                    
                    for aml in amls:

                        if aml.payment_type_document.id == line.type_document_id.id and round(aml.amount_currency, 2) == round(line.amount, 2):
                            filtered_amls.append(aml)
                else:
                    print(payment_debit_account_id)
                    print(payment_credit_account_id)
                    amls = self.env['account.move.line'].search([
                        ('move_id.state', '=', 'posted'),
                        ('move_id.bank_operation_ref', '=', line.bank_operation_ref),
                        '|',('account_id', 'in', payment_debit_account_id),
                        ('account_id', 'in', payment_credit_account_id),
                    ])
                    filtered_amls = []
                    print(filtered_amls)
                    for aml in amls:
                        if aml.payment_type_document.id == line.type_document_id.id and round(aml.amount_currency, 2) == round(line.amount, 2):
                            filtered_amls.append(aml)

                
                line_vals = {
                    'st_line': self._get_statement_line(line),
                    'reconciliation_proposition': [self._prepare_js_reconciliation_widget_move_line(line, aml) for aml in amls],
                    'model_id': matching_amls[line.id].get('model') and matching_amls[line.id]['model'].id,
                }

                # Add partner info if necessary
                line_partner = matching_amls[line.id].get('partner')

                if not line_partner and partner_map.get(line.id):
                    line_partner = self.env['res.partner'].browse(partner_map[line.id])

                if line_partner:
                    line_vals.update({
                        'partner_id': line_partner.id,
                        'partner_name': line_partner.name,
                    })

                # Add writeoff info if necessary
                if matching_amls[line.id].get('status') == 'write_off':
                    line_vals['write_off_vals'] = matching_amls[line.id]['write_off_vals']
                    self._complete_write_off_vals_for_widget(line_vals['write_off_vals'])

                results['lines'].append(line_vals)

        return results
