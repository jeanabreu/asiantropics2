# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountJournalInherited(models.Model):
    _inherit = "account.journal"
    
    cc_payment_account = fields.Many2one('account.account', default=None, string="Cuenta de pago de TC", help="Cuenta a utilizar para registrar el pago de tarjeta de crédito")
    commision_type = fields.Selection([
        ('cc', 'Tarjetas de crédito'),
        ('service', 'Servicio')
    ], string="Tipo de comisión", tracking=True, default="cc", required=True)
    provider_ap_account = fields.Many2one('account.account', default=None, string="Comisión por tarjeta de crédito", help="Comisión por tarjeta de crédito donde se registran las comisiones")
    percentage_cc_account = fields.Many2one('account.account', default=None, string="2% por tarjetas de crédito", help="2% por tarjetas de crédito donde se registran las comisiones")
    cc_fiscal_debit_account = fields.Many2one('account.account', default=None, string="Débito fiscal IVA", help="Cuenta Débito fiscal IVA donde se registran el débito fiscal IVA")
    provider_commission_fixed = fields.Float("Comisión fija de proveedor", help="Monto fijo de comisión que sera debitado del  pago")
    provider_commission_percent = fields.Float("Porcentaje de comisión de proveedor ", help="Porcentaje de comisión que sera debitado del pago")
    account_move_name_desc = fields.Char(string="Nombre de asiento de comisión", defailt="Comisión bancaria")
    commision_country = fields.Selection([
        ('gt', 'Guatemala'),
        ('sv', 'El Salvador')
    ], string="País", default="gt")
    
    journal_comissions_ids = fields.One2many('cc_payment_commisions.journal_percentage', 'journal_id', string="Comisiones")
    
    @api.constrains('provider_commission_fixed', 'provider_commission_percent')
    def validate_provider_commission(self):
    
        for obj in self:
            if obj.provider_commission_fixed < 0:
                raise ValidationError("El monto de comisión debe ser mayor a 0")
            if obj.provider_commission_percent < 0 or obj.provider_commission_percent > 100:
                raise ValidationError("El procentaje de comisión debe ser entre 0 y 100")
            
        return True

class CcPaymentComissionsJournalPercentage(models.Model):
    _name = "cc_payment_commisions.journal_percentage"
    _description = "Comisiones por diario"
    
    journal_id = fields.Many2one('account.journal', string="Diario")
    name = fields.Char(string="Nombre", required=True)
    provider_commission_percent = fields.Float("% Comisión", help="Monto fijo de comisión que sera debitado del  pago", required=True)
    
    