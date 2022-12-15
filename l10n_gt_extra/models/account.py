# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    numero_viejo = fields.Char(string="Numero Viejo")
    nombre_impreso = fields.Char(string="Nombre Impreso")
    no_negociable = fields.Boolean(string="No Negociable", default=True)
    #Cambié
    def action_cancel(self):
        for rec in self:
            rec.write({'numero_viejo': rec.name})
        return super(AccountPayment, self).action_cancel()

    def anular(self):
        for rec in self:
            
            rec.action_draft()
            
            journal_id = rec.journal_id
            if rec.check_number:
                payment_check_number = int(rec.check_number)
                new_next_val = payment_check_number + 1
                current_next_val = int(journal_id.check_next_number)
                
                if current_next_val == new_next_val:
                    sequence = journal_id.check_sequence_id
                    next_seq = sequence.get_next_char(current_next_val - 1)
                    journal_id.write({"check_next_number": next_seq})
                    rec.check_number = False
                else:
                    raise ValidationError("El pago no puede ser descartado debido a que el correlativo de cheques asociado al diario ya fue utilizado en otro pago")


class AccountJournal(models.Model):
    _inherit = "account.journal"

    direccion = fields.Many2one('res.partner', string='Dirección')
    facturas_por_rangos = fields.Boolean(string='Las facturas se ingresan por rango', help='Cada factura realmente es un rango de factura y el rango se ingresa en Referencia/Descripción')
