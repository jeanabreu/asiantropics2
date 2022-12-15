# -*- coding: utf-8 -*-

import copy
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.misc import formatLang, format_date, parse_date


class AccountBankStatementLine(models.AbstractModel):
    _inherit = "account.bank.statement.line"
    
    
    bank_operation_ref = fields.Char(string="Referencia bancaria")
    type_document_id = fields.Many2one('l10n_gt_extra.type.document.payment', string="Tipo de documento de pago")
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountBankStatementLine, self).create(vals_list)
        for line in res:
            if line.move_id:
                line.move_id.write({"bank_operation_ref": line.bank_operation_ref, "belongs_to_bank_statement": True})

        return res

class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    def button_post(self):
        company_id = self.env.company
        
        # Check db bank_operation_ref duplicates
        is_pos_session = False
        if 'pos_session_id' in self.env['account.bank.statement']._fields:
            if self.pos_session_id:
                is_pos_session = True
        
        if not is_pos_session:
            # Check local bank_operation_ref duplicates
            bank_operation_refs = []
            for line in self.line_ids:
                ref_found = False
                for local_ref in bank_operation_refs:
                    if line.type_document_id.validate_duplicity:
                        if local_ref["amount"] == line.amount and local_ref["bank_operation_ref"] == line.bank_operation_ref and local_ref["type_document_id"] == line.type_document_id.id:
                            ref_found = True
                if ref_found:   
                    raise ValidationError('La referencia bancaria %s - %s (Importe: %s) esta duplicada, por favor revisar' % (line.bank_operation_ref, line.type_document_id.name, line.amount))
                else:
                    if line.type_document_id.validate_duplicity:
                        new_bak_ref = {
                            "bank_operation_ref": line.bank_operation_ref,
                            "type_document_id": line.type_document_id.id,
                            "amount": line.amount,
                        }
                        bank_operation_refs.append(new_bak_ref)
                    
            for line in self.line_ids:
                if line.type_document_id.validate_duplicity:
                    statement_line_data = self.env['account.bank.statement.line'].search([
                        ('bank_operation_ref', '=', line.bank_operation_ref),
                        ('amount', '=', line.amount),
                        ('journal_id', '=', self.journal_id.id),
                        ('statement_id', '!=', self.id),
                        ('type_document_id', '!=', line.type_document_id.id),
                        ('company_id', '=', company_id.id)
                    ], limit=1)
                    if statement_line_data:
                        raise ValidationError('Ya existe una linea de extracto para este diario con la referencia bancaria %s (Importe: %s), en el extracto %s' % (line.bank_operation_ref, line.amount, statement_line_data.statement_id.name))
        
        #TODO: VALIDAR CON ODOO PARA CAMBIO A NUEVO CODIGO
        return super(AccountBankStatement, self).button_post()
        """if any(statement.state != 'open' for statement in self):
            raise UserError(_("Only new statements can be posted."))

        self._check_balance_end_real_same_as_computed()

        for statement in self:
            if not statement.name:
                statement._set_next_sequence()

        self.write({'state': 'posted'})
        lines_of_moves_to_post = self.line_ids.filtered(lambda line: line.move_id.state != 'posted')
        if lines_of_moves_to_post:
            lines_of_moves_to_post.move_id._post(soft=False)"""
            
        
        