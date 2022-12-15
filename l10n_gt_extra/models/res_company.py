# -*- coding: utf-8 -*-

from odoo import api, models, fields, _


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_withholding_isr = fields.Selection(
        [
            ('quarter_witholding', 'Sujeto a Pagos Trimestrales'),
            ('definitive_withholding', 'Sujeto a Retención Definitiva'),
            ('small_taxpayer_withholding', 'Pequeño Contribuyente')
        ], string="Retención ISR", default="quarter_witholding"
    )

    tax_withholding_iva = fields.Selection(
        [
            ('no_witholding', 'No es agente rentenedor de IVA'),
            ('export', 'Exportadores'),
            ('decree_28_89', 'Beneficiarios del Decreto 28-89'),
            ('public_sector', 'Sector Público'),
            ('credit_cards_companies', 'Operadores de Tarjetas de Crédito y/o Débito'),
            ('special_taxpayer', 'Contribuyente Especiales'),
            ('special_taxpayer_export', 'Contribuyente Especial y Exportador'),
            ('others', 'Otros Agentes de Retención')
        ], string='Retención IVA', default='no_witholding')

    iva_retencion_account_id = fields.Many2one('account.journal', string='Diario de retención de IVA')
    isr_retencion_account_id = fields.Many2one('account.journal', string='Diario de retención de ISR')
    show_analytic_lines = fields.Boolean(string="Mostrar lineas analíticas", default=False)
