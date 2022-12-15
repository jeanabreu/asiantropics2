# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    fel_certifier = fields.Selection([
        ('digifact', 'Digifact'),
        ('infile', 'InFile'),
        ('g4s', 'G4S'),
        ('guatefacturas', 'Guatefacturas'),
        ('forcon', 'Forcon')
        ], string='Certificador a utilizar', related="company_id.fel_certifier", readonly=False)

    fel_currency_from_invoice = fields.Boolean(string="Seleccionar moneda de facturación a factura", related="company_id.fel_currency_from_invoice", readonly=False)
    fel_invoice_currency = fields.Many2one('res.currency', related="company_id.fel_invoice_currency", string="Moneda de facturación", readonly=False)
    fel_addendum_currency_rate = fields.Boolean(string="Tasa de cambio", related="company_id.fel_addendum_currency_rate", readonly=False)
    fel_addendum_journal_sequence = fields.Boolean(string="Correlativo de diario", related="company_id.fel_addendum_journal_sequence", readonly=False)
    fel_default_code_divider = fields.Char(string="Separador de referencia interna", related="company_id.fel_default_code_divider", readonly=False)
    fel_invoice_line_name = fields.Selection([
        ('product', 'Nombre de producto'),
        ('description', 'Descripcion')
    ], string="Descripcion de producto de factura", related="company_id.fel_invoice_line_name", readonly=False)
    fel_company_configuration = fields.Boolean(string="Configurar Frases Manualmente", related="company_id.fel_company_configuration", default=True)

    # INFILE

    infile_user = fields.Char(string="Usuario", related="company_id.infile_user", readonly=False)
    infile_xml_key_signature = fields.Char(string="Llave Firma", related="company_id.infile_xml_key_signature", readonly=False)
    infile_xml_url_signature = fields.Char(string="URL Firma", related="company_id.infile_xml_url_signature", readonly=False)
    infile_key_certificate = fields.Char(string="Llave Certificación", related="company_id.infile_key_certificate", readonly=False)
    infile_url_certificate = fields.Char(string="URL Certificación", related="company_id.infile_url_certificate", readonly=False)
    infile_url_anulation = fields.Char(string="URL Anulación", related="company_id.infile_url_anulation", readonly=False)
    fel_establishment_code = fields.Char(string="Código Establecimiento", related="company_id.fel_establishment_code", readonly=False)

    #FORCON

    forcon_user = fields.Char(string="Usuario", related="company_id.forcon_user", readonly=False)
    forcon_password = fields.Char(string="Contraseña", related="company_id.forcon_password", readonly=False)
    forcon_url_dev = fields.Char(string="URL Pruebas", related="company_id.forcon_url_dev", readonly=False)
    forcon_url_prod = fields.Char(string="URL Producción", related="company_id.forcon_url_prod", readonly=False)
    # DIGIFACT

    digifact_username = fields.Char(string="Usuario", related="company_id.digifact_username", readonly=False)
    digifact_password = fields.Char(string="Contraseña", related="company_id.digifact_password", readonly=False)
    digifact_api_dev_login = fields.Char(string="Login", related="company_id.digifact_api_dev_login", readonly=False)
    digifact_api_dev_certificate = fields.Char(string="Generación FEL", related="company_id.digifact_api_dev_certificate", readonly=False)
    digifact_api_prod_login = fields.Char(string="Login", related="company_id.digifact_api_prod_login", readonly=False)
    digifact_api_prod_certificate = fields.Char(string="Generación FEL", related="company_id.digifact_api_prod_certificate", readonly=False)
    
    # GUATEFACTURAS
    guatefacturas_soap_username = fields.Char(string="Usuario", related="company_id.guatefacturas_soap_username", readonly=False)
    guatefacturas_soap_password = fields.Char(string="Contraseña", related="company_id.guatefacturas_soap_password", readonly=False)
    guatefacturas_username = fields.Char(string="Usuario", related="company_id.guatefacturas_username", readonly=False)
    guatefacturas_password = fields.Char(string="Contraseña", related="company_id.guatefacturas_password", readonly=False)
    guatefacturas_url_dev = fields.Char(string="Generación FEL", related="company_id.guatefacturas_url_dev", readonly=False)
    guatefacturas_url_prod = fields.Char(string="Generación FEL"    , related="company_id.guatefacturas_url_prod", readonly=False)

    # G4S
    requestor_id = fields.Char(string="Requestor", related="company_id.requestor_id", readonly=False)
    g4s_username = fields.Char(string="Usuario", related="company_id.g4s_username", readonly=False)
    g4s_dev_url = fields.Char(string="URL Pruebas", related="company_id.g4s_dev_url", readonly=False)
    g4s_prod_url = fields.Char(string="URL Producción", related="company_id.g4s_prod_url", readonly=False)
    g4s_environment = fields.Selection([
        ('development', "Pruebas"),
        ('production', "Producción")
    ], string="Ambiente", related="company_id.g4s_environment", readonly=False)
