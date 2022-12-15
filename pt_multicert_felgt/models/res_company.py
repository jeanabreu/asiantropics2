# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    fel_certifier = fields.Selection([
        ('digifact', 'Digifact'),
        ('infile', 'InFile'),
        ('g4s', 'G4S'),
        ('guatefacturas', 'Guatefacturas'),
        ('forcon', 'Forcon')
        ], string='Certificador a utilizar', default='infile')

    fel_currency_from_invoice = fields.Boolean(string="Seleccionar moneda de facturación en base a diario")
    fel_invoice_currency = fields.Many2one('res.currency', string="Moneda de facturación")
    fel_addendum_currency_rate = fields.Boolean(string="Tasa de cambio")
    fel_addendum_journal_sequence = fields.Boolean(string="Correlativo de diario")
    fel_default_code_divider = fields.Char(string="Separador de referencia interna")
    fel_invoice_line_name = fields.Selection([
        ('product', 'Nombre de producto'),
        ('description', 'Descripcion')
    ], string="Descripcion de producto de factura")
    fel_company_configuration = fields.Boolean(string="Configurar Frases Manualmente", default=True)

    # INFILE

    infile_user = fields.Char(string="Usuario")
    infile_xml_key_signature = fields.Char(string="Llave Firma")
    infile_xml_url_signature = fields.Char(string="URL Firma")
    infile_key_certificate = fields.Char(string="Llave Certificación")
    infile_url_certificate = fields.Char(string="URL Certificación")
    infile_url_anulation = fields.Char(string="URL Anulación")
    fel_establishment_code = fields.Char(string="Código Establecimiento")
    
    #FORCON
    forcon_user = fields.Char(string="Usuario")
    forcon_password = fields.Char(string="Contraseña")
    forcon_url_dev = fields.Char(string="URL Pruebas")
    forcon_url_prod = fields.Char(string="URL Producción")
    #fel_establishment_code = fields.Char(string="Código Establecimiento")
    # DIGIFACT

    digifact_username = fields.Char(string="Usuario")
    digifact_password = fields.Char(string="Contraseña")
    digifact_api_dev_login = fields.Char(string="Login")
    digifact_api_dev_certificate = fields.Char(string="Generación FEL")
    digifact_api_prod_login = fields.Char(string="Login", default="https://felgttestaws.digifact.com.gt/felapi/api/login/get_token")
    digifact_api_prod_certificate = fields.Char(string="Generación FEL", default="https://felgttestaws.digifact.com.gt/felapi/api/FELRequest")
    
    # GUATEFACTURAS
    guatefacturas_soap_username = fields.Char(string="Usuario")
    guatefacturas_soap_password = fields.Char(string="Contraseña")
    guatefacturas_username = fields.Char(string="Usuario")
    guatefacturas_password = fields.Char(string="Contraseña")
    guatefacturas_url_dev = fields.Char(string="Generación FEL")
    guatefacturas_url_prod = fields.Char(string="Generación FEL")
    
    # G4S
    requestor_id = fields.Char(string="Requestor")
    g4s_username = fields.Char(string="Usuario")
    g4s_dev_url = fields.Char(string="URL Pruebas")
    g4s_prod_url = fields.Char(string="URL Producción")
    g4s_environment = fields.Selection([
        ('development', "Pruebas"),
        ('production', "Producción")
    ], string="Ambiente")
    

    fel_company_type = fields.Char(string="Tipo de frase", help="De acuerdo al tipo de afiliación a los impuestos, o el tipo de operación que esté realizando el emisor.", default="1")
    fel_company_code = fields.Char(string="Código de escenario", help="Indique el escenario del emisor en base al tipo de frase.", default="1")
    fel_resolution_date = fields.Char(string="Fecha de resolución", help="Ingrese la fecha de resolución en caso de aplicar")
    fel_resolution_number = fields.Char(string="Número de resolución", help="Ingrese el número de resolución en caso de aplicar")
    consignatary_code = fields.Char(string="Código de Consignatario o Destinatario")
    exporter_code = fields.Char(string="Código Exportador")
    fel_iva_company_exception = fields.Boolean(string="Aplica frases de exento o no afecto de IVA")
