# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    tax_withholding_isr = fields.Selection(
        [
            ('quarter_witholding', 'Sujeto a Pagos Trimestrales'),
            ('definitive_withholding', 'Sujeto a Retención Definitiva'),
            ('small_taxpayer_withholding', 'Pequeño Contribuyente')
        ], string="Régimen tributario", default="quarter_witholding"
    )

    tax_withholding_iva = fields.Selection(
        [
            ('no_witholding', 'No es agente rentenedor de IVA'),
            ('export', 'Exportadores'),
            ('public_sector', 'Sector Público'),
            ('credit_cards_companies', 'Operadores de Tarjetas de Crédito y/o Débito'),
            ('special_taxpayer', 'Contribuyente Especiales'),
            ('special_taxpayer_export', 'Contribuyente Especial y Exportador'),
            ('others', 'Otros Agentes de Retención'),
            ('iva_forgiveness', 'Exención de IVA')
        ], string='Retención IVA', default='no_witholding')

    user_country_id = fields.Char(string="UserCountry", default=lambda self: self.env.user.company_id.country_id.code)

    @api.constrains('vat')
    def _validar_nit(self):
        for p in self:
            if p.vat == 'CF' or p.vat == 'C/F' or not p.vat:
                return True

            if p.country_id and p.country_id.code != 'GT':
                return True

            nit = p.vat.replace('-', '')
            verificador = nit[-1]
            if verificador.upper() == 'K':
                verificador = '10'
            secuencia = nit[:-1]

            total = 0
            i = 2
            for c in secuencia[::-1]:
                total += int(c) * i
                i += 1

            resultante = (11 - (total % 11)) % 11

            #if str(resultante) != verificador:
            #    raise ValidationError("El NIT no es correcto (según lineamientos de la SAT)")

    @api.constrains('vat')
    def _validar_duplicado(self):
        for p in self:
            if p.country_id and p.country_id.code != 'GT':
                return True

            if not p.parent_id and p.vat and p.vat != 'CF' and p.vat != 'C/F':
                repetidos = p.search([('vat', '=', p.vat), ('id', '!=', p.id), ('parent_id', '=', False)])
                if len(repetidos) > 0:
                    raise ValidationError("El NIT ya existe")

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        res1 = super(ResPartner, self).name_search(name, args, operator=operator, limit=limit)

        records = self.search([('vat', 'ilike', name)], limit=limit)
        res2 = records.name_get()

        return res1+res2

    pequenio_contribuyente = fields.Boolean(string="Pequeño Contribuyente", compute="_get_pequenio_contribuyente")

    def _get_pequenio_contribuyente(self):
        for rec in self:
            if rec.tax_withholding_isr:
                if rec.tax_withholding_isr == "small_taxpayer_withholding":
                    rec.pequenio_contribuyente = True
                else:
                    rec.pequenio_contribuyente = False
            else:
                rec.pequenio_contribuyente = False

    @api.onchange('tax_withholding')
    def _onchange_tax_withholding(self):
        if self.tax_withholding_isr:
            if self.tax_withholding_isr == "small_taxpayer_withholding":
                self.pequenio_contribuyente = True
            else:
                self.pequenio_contribuyente = False
        else:
            self.pequenio_contribuyente = False
