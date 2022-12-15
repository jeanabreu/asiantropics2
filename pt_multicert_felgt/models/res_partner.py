# -*- coding: utf-8 -*-

from typing import ValuesView
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    buyer_code = fields.Char(string="Código Comprador")
    invoice_currency = fields.Many2one('res.currency', string="Moneda de facturación")
    dpi_number = fields.Char(string="D.P.I.")
    
    #Campo agregado para la implementación de la factura de exportación para analytecs
    is_foreign_customer = fields.Boolean(string="Cliente del Extranjero", default =False)
    consignatary_name = fields.Char(string="Nombre Consignatario")
    consignatary_code = fields.Char(string="Código Consignatario")
    consignatary_address = fields.Char(string="Dirección Consignatario")
    buyer_name = fields.Char(string="Nombre Comprador")
    buyer_address = fields.Char(string="Dirección del Comprador")
    exporter_name = fields.Char(string="Nombre del Exportador")
    exporter_code = fields.Char(string="Código del Exportador")


    @api.onchange('is_foreign_customer')
    def _get_export_information(self):
        if self.is_foreign_customer:
            self.consignatary_name = self.name
            self.consignatary_address = str(self.street if self.street else " ") + " " + str(self.street2 if self.street2 else " ")
            self.buyer_name = self.name
            self.buyer_address = str(self.street if self.street else " ") + " " +str(self.street2 if self.street2 else " ")
            self.exporter_name = ""
            self.exporter_code = ""


