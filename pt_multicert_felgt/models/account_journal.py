# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    fel_certifier = fields.Selection([
        ('digifact', 'Digifact'),
        ('infile', 'InFile'),
        ('g4s', 'G4S'),
        ('guatefacturas', 'Guatefacturas'),
        ('forcon', 'FORCON')
        ], string='Certificador a utilizar', compute="get_fel_certifier", store=False)
    is_fel = fields.Selection([
        ('inactive', 'Inactivo'),
        ('development', 'Ambiente de pruebas'),
        ('production', 'Ambiente de producción'),
    ], string='Factura  Electrónica', default='inactive', required=False, help="Indique si este diario utilizara emisión de facturas electrónica y sobre que ambiente")
    infile_fel_active = fields.Boolean(string="Facturación electrónica")
    forcon_fel_active = fields.Boolean(string="Facturación electrónica")
    fel_establishment_code = fields.Char(string="Código Establecimiento", help="Ingrese el código de establecimiento a utilizar")
    g4s_fel_active = fields.Boolean(string="Facturación electrónica")
    
    fel_address = fields.Char(string="Dirección de facturación", default=lambda self: self.company_id.street)
    fel_commercial_name = fields.Char(string="Nombre comercial", default=lambda self: self.company_id.name)
    fel_zip_code = fields.Char(string="Código postal", default=lambda self: self.company_id.zip)
    fel_department = fields.Char(string="Departamento", default=lambda self: self.company_id.state_id.name)
    fel_township = fields.Char(string="Municipio", default=lambda self: self.company_id.city)
    
    
    guatefacturas_fel = fields.Selection([
        ('inactive', 'Inactivo'),
        ('development', 'Ambiente de pruebas'),
        ('production', 'Ambiente de producción'),
    ], string='Factura  Electrónica', default='inactive', required=False, help="Indique si este diario utilizara emisión de facturas electrónica y sobre que ambiente")
    
    forcon_fel = fields.Selection([
        ('development', 'Ambiente de pruebas'),
        ('production', 'Ambiente de producción'),
    ], string='Ambiente', default='development', required=False, help="Indique si este diario utilizara emisión de facturas electrónica y sobre que ambiente")
    

    def get_fel_certifier(self):
        fel_certifier = self.env.company.fel_certifier
        self.fel_certifier = fel_certifier
