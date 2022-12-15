# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.osv import expression
from openerp.exceptions import UserError, ValidationError

class L10nGtExtraTypeDocumentPayment(models.Model):
    _name = 'l10n_gt_extra.type.document.payment'
    _description = 'Tipo de Documento de Pago'
    
    name = fields.Char(string='Tipo de Documento')
    validate_duplicity  = fields.Boolean(string='Validar Duplicidad')
    code = fields.Char(string='Código')
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []

        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            connector = '&' if operator in expression.NEGATIVE_TERM_OPERATORS else '|'
            domain = [connector, ('code', operator, name), ('name', operator, name)]
        
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)