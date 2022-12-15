# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from openerp.exceptions import UserError, ValidationError

class MappingRefsBank(models.TransientModel):
    _name = 'l10n_gt_extra.mapping_refs_bank'

    count_payment = fields.Integer('Cantidad de Registros a Mapear')
    count_mapping = fields.Integer('Mapear en Lotes de')

    def payment_to_mapping(self):
        payment_data = self.env['account.payment'].search([
            ('payment_type','=','inbound'),
            ('ref_mapping','=', False),
        ])
        count_payment = 0
        for count in payment_data:
            count_payment += 1
        self.write({'count_payment': count_payment})
        if self.count_payment == 0:
            raise ValidationError("Ya esta mapeado todo")
        return {
            "type": "ir.actions.do_nothing",
        }
        
    def mapping_refs_bank(self):
        if self.count_payment == 0:
            raise ValidationError("Valide la cantidad de Pagos pendientes a mapear")
        
        payment_data = self.env['account.payment'].search([
            ('payment_type','=','inbound'),
            ('ref_mapping','=', False),
        ])
        
        for payment_info in payment_data[1:self.count_mapping]:
            if payment_info.communication:
                payment_info.ref_mapping = True
                refs_bank = []
                ref_bank = payment_info.communication
                if ' ' in ref_bank:
                    refs_bank = ref_bank.split(' ')
                if ' ' not in ref_bank:
                    refs_bank.append(ref_bank)
                ref_bank_data = self.env['l10n_gt_extra.bank_operation_ref'].search([])
                unique_deposits = []
                for ref_info in ref_bank_data:
                    unique_deposits.append(ref_info.name)
                for rec in refs_bank:
                    if rec not in unique_deposits:
                        values = {
                            'name': rec,
                            'payment_id': int(payment_info.id),
                        }
                        self.env['l10n_gt_extra.bank_operation_ref'].create(values)
        
        count_payment = 0
        for count in payment_data:
            count_payment += 1
        self.write({'count_payment': count_payment})
        
        return {
            "type": "ir.actions.do_nothing",
        }


