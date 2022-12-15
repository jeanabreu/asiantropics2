# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import ValidationError

class WizardAssetsCapitalization(models.TransientModel):
    _name = "l10n_gt_extra.wizard_assets_capitalization"
    _description = "Capitalizacion de activos"
    
    journal_id = fields.Many2one('account.journal', string="Diario", required=True, domain=[('capitalization_account_id', '!=', False)])
    capitalization_date = fields.Date(string="Fecha", default=fields.Date.context_today, required=True)
    
    def process_asset(self):
        
        journal_id = self.journal_id
        move_date = self.capitalization_date

        invoices_data = self.env['account.move'].search([
            ('id', '=', self.env.context['active_id'])
        ])
        
        for invoice in invoices_data:
            
            if invoice.state != 'posted':
                raise ValidationError('La factura debe estar publicada para poder ser capitalizada')
            
            move_validations = self.env['account.move'].search([
                ('capitalization_invoice_id', '=', invoice.id),
                ('state', '=', 'posted')
            ], limit=1)
            if move_validations:
                raise ValidationError('Ya existe movimiento de capitalización asociado a la factura. (%s)' % move_validations.name)

            cap_amount = 0
            
            account_id = invoice.partner_id.property_account_payable_id.id
            invoice_lines = []
            for line in invoice.line_ids:                
                if line.account_id.id == account_id and line.credit > 0:
                    cap_amount += line.credit
                
                if line.account_id.reconcile:
                    if not line.reconciled:
                        invoice_lines.append(line)
            
            move_name = "Capitalización de activo - " + str(invoice.name)
            new_lines = []
            new_lines.append((0, 0, {
                'name': move_name,
                'debit': cap_amount,
                'credit': 0,
                'account_id': account_id,
                'partner_id': invoice.partner_id.id,
                'date_maturity': move_date,
                'amount_residual': 0.0,
                'amount_residual_currency': 0.0
            }))
            new_lines.append((0, 0, {
                'name': move_name,
                'debit': 0,
                'credit': cap_amount,
                'account_id': journal_id.capitalization_account_id.id,
                'partner_id': invoice.partner_id.id,            
                'date_maturity': move_date,
                'amount_residual': 0.0,
                'amount_residual_currency': 0.0
            }))
            
            move_vals = {
                'line_ids': new_lines,
                'ref': invoice.name,
                'date': move_date,
                'journal_id': journal_id.id,
                'capitalization_invoice_id': invoice.id,
                'move_type': 'entry'
            }
            
            move = self.env['account.move'].create(move_vals)
            
            move.action_post()
            index = 0
            move_lines = move.line_ids
            for line in invoice_lines:
                par = line | move_lines[index]
                par.reconcile()
                index += 1
            
            invoice.write({"capitalization_move_id": move.id, "payment_state": 'paid', "amount_residual": 0, "amount_residual_signed": 0})
            
        
        return {
            'name': _('Create move'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': move.id,
        }
