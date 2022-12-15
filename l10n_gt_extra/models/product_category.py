# -*- encoding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID


class ProductCategory(models.Model):
    _inherit = "product.category"

    sat_iva_type_product = fields.Selection(
        [
            ('agriculture', 'Agrícolas y pecuarios'),
            ('not_agriculture', 'Producto no agropecuarios'),
            ('good_services', 'Bienes y servicios'),
            ('payment_creditholders', 'Pagos por cuenta de tarjeta-habientes'),
            ('fuel_payments', 'Pagos combustible')
        ], string="Clasificación de retención IVA", default="good_services"
    )
