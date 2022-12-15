# -*- encoding: UTF-8 -*-
'''
1. Factura Cambiaria: Crear una factura normal y dar click en otra pestaña, seleccionar tipo de factura, seleccionar factura cambiaria y validar.
2. Factura cambiaria Exp: Crear una factura normal y dar click en otra pestaña, seleccionar tipo de factura, seleccionar factura cambiaria Exp. (El cliente no debe de tener nit solo debe de aparecer CF, dentro del cliente hay un campo que se llama Código comprador, hay que llenarlo)
3. Factura especial: Crear una factura normal y dar click en otra pestaña, seleccionar tipo de factura, seleccionar factura especial y llenar el monto de retención, luego validar.
4. Nota de abono: La nota de abono se crea desde Rectificativas de cliente (Facturas rectificativas), la creas y le das click en otra pestaña y le das click en un check box que dice Nota de abono y validas.
 5. Nota de crédito rebajando régimen face: Esta se crea una factura rectificativa a partir de una factura normal, antes de validar la factura rectificativa dar click en otra pestaña y click en el check box nota de crédito rebajando régimen anterior, luego validar.
 6. Nota de débito: Se presiona el botón de Nota de débito sobre una factura FEL publicada y esta genera una nueva factura FEL tipo de documento Nota de débito enlazada a la anterior.
'''
from attr import set_run_validators
from zeep.xsd import valueobjects
from odoo import api, models, sql_db, fields, _
import xml.etree.cElementTree as ET

from datetime import datetime, timedelta
import time

import datetime as dt
from datetime import date, datetime, timedelta
import dateutil.parser
from dateutil.tz import gettz
from dateutil import parser
import json
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
import base64
import requests
from requests.auth import AuthBase
from json import loads
from random import randint
import re
import zeep
from zeep.transports import Transport
import logging
import io

from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from requests import Session

import decimal

from xml.etree.ElementTree import Element, SubElement, Comment, tostring 
#from ElementTree_pretty import prettify

_logger = logging.getLogger(__name__)


# VALIDATIONS CONSTANTS
RAISE_VALIDATION_COMPANY_REGISTRY = "Por favor ingrese el registro fiscal de la empresa emisora."
RAISE_VALIDATION_COMPANY_EMAIL = "Por favor ingrese el correo electrónico de la empresa emisora."
RAISE_VALIDATION_COMPANY_VAT = "Por favor ingrese el número de NIT de la empresa emisora."
RAISE_VALIDATION_COMPANY_STREET = "Por favor ingrese la dirección de la empresa emisora."
RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE = "Por favor ingrese el código de escenario asociado al tipo de frase utilizado por el emisor."
RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE = "Por favor ingrese tipo de frase la empresa emisora en base al tipo de documento de DTE."
RAISE_VALIDATION_INVOICE_DATE_DUE = "Por favor ingrese la fecha de vencimiento de la factura."
RAISE_VALIDATION_INVOICE_PARTNER_NAME = "Por favor ingrese un nombre para el receptor de la factura."
RAISE_VALIDATION_UUID_CANCEL = "La factura debe tener un número de serie para poder ser cancelada."
RAISE_VALIDATION_PARTNER_BUYER_CODE = "Por favor ingresar el código de comprador del receptor de la factura."
RAISE_VALIDATION_COMPANY_CONSIGNATARY_CODE = "Por favor ingresar el código de consignatario de la empresa emisora."
RAISE_VALIDATION_COMPANY_EXPORTER_CODE = "Por favor ingresar el código de exportador de la empresa emisora."
RAISE_VALIDATION_PARTNER_ADDRESS = "Por favor ingresar la dirección del comprador"


class AccountMove(models.Model):
    _inherit = 'account.move'

    uuid = fields.Char("Número de Autorización", readonly=True, states={'draft': [('readonly', False)]})
    uuid_original = fields.Char("Número de Autorización original", readonly=True, states={'draft': [('readonly', False)]})
    serie = fields.Char("Serie", readonly=True, states={'draft': [('readonly', False)]})
    serie_original = fields.Char("Serie", readonly=True, states={'draft': [('readonly', False)]})
    dte_number = fields.Char("Número DTE", readonly=True, states={'draft': [('readonly', False)]})
    dte_number_original = fields.Char("Número DTE", readonly=True, states={'draft': [('readonly', False)]})
    dte_date = fields.Datetime("Fecha Autorización", readonly=True, states={'draft': [('readonly', False)]})
    cae = fields.Text("CAE", readonly=True, states={'draft': [('readonly', False)]})
    total_in_letters = fields.Text("Total Letras", readonly=True, states={'draft': [('readonly', False)]})
    fel_gt_withhold_amount = fields.Float(string="Retención", readonly=True, states={'draft': [('readonly', False)]})
    fel_gt_invoice_type = fields.Selection([
        ('normal', 'Factura Normal'),
        ('especial', 'Factura Especial'),
        ('cambiaria', 'Factura Cambiaria'),
        ('cambiaria_exp', 'Factura Cambiaria Exp.'),
        ('nota_debito', 'Nota de Débito')
    ], string='Tipo de Factura', default='normal', readonly=True, states={'draft': [('readonly', False)]})
    old_tax_regime = fields.Boolean(string="Nota de crédito rebajando régimen antiguo", readonly=True, states={'draft': [('readonly', False)]}, default=False)
    credit_note = fields.Boolean(string="Nota de Abono", readonly=True, compute="set_credit_note")
    is_receipt = fields.Boolean(string="Es Recibo", default=False, compute="get_type_journal", store=False)
    fel_gt_document_type = fields.Selection([
        ('recibo', 'Recibo')
    ], string='Tipo de Documento', readonly=True, states={'draft': [('readonly', False)]}, default="recibo")

    source_debit_note_id = fields.Many2one('account.move', string="Documento origen")
    debit_note_id = fields.Many2one('account.move', string="Nota de débito")

    sat_ref_id = fields.Char(string="AcuseReciboSAT")
    fel_link = fields.Char(string="Documento FEL", compute="get_link")
    
    fel_certifier = fields.Selection([
        ('digifact', 'Digifact'),
        ('infile', 'InFile'),
        ('g4s', 'G4S'),
        ('guatefacturas', 'Guatefacturas')
        ], string='Certificador a utilizar', related="journal_id.fel_certifier", readonly=False)

    # CIG ONLY
    fel_enable_cancel_bypass = fields.Boolean(default=False, string="Generación de FEL fallida")
    is_foreign_customer = fields.Boolean(string="Cliente del Extrajero", default=False, related="partner_id.is_foreign_customer")
    #APPLIED CHANGES FOR ADVANCE PAYMENTS IN INVOICE
    has_advance_payment = fields.Boolean(string="Tiene Anticipos", default=False)
    advance_untaxed_amount = fields.Monetary(string="Monto de Anticipo sin iva", compute="_compute_advance_payment")
    advance_total_amount = fields.Monetary(string="Monto de Anticipo")
    def _compute_advance_payment(self):
        for rec in self:
            if rec.move_type == 'out_invoice':
                advance_amount = 0
                total_amount = 0
                rec.advance_untaxed_amount = 0
                if rec.invoice_line_ids:
                    for line in rec.invoice_line_ids:
                        if line.quantity < 0:
                            advance_amount += line.price_subtotal
                            total_amount += line.price_unit
                if advance_amount != 0:
                    rec.advance_untaxed_amount = abs(advance_amount)
                    rec.advance_total_amount = total_amount
                    rec.has_advance_payment = True
                else:
                    if rec.advance_untaxed_amount != 0:
                        rec.advance_untaxed_amount = 0
                    if rec.advance_total_amount != 0:
                        rec.advance_total_amount = 0
                    if rec.has_advance_payment != False:
                        rec.has_advance_payment = False
            else:
                if rec.advance_untaxed_amount != 0:
                    rec.advance_untaxed_amount = 0
                if rec.advance_total_amount != 0:
                    rec.advance_total_amount = 0
                if rec.has_advance_payment != False:
                    rec.has_advance_payment = False
            
    @api.model
    def fields_get(self, fields=None):

        hide = ['fel_enable_cancel_bypass']
        res = super(AccountMove, self).fields_get()
        for field in hide:
            res[field]['selectable'] = False
        return res

    def action_debit_note(self):
        for rec in self:
            invoice_data = self.env['account.move'].browse(rec.id)

            ctx = self._context.copy()
            ctx.update({
                'default_type_invoice': 'out_invoice',
                'default_source_debit_note_id': invoice_data.id,
                'default_fel_gt_invoice_type': 'nota_debito',
                'default_partner_id': rec.partner_id.id
            })
            #ctx['default_partner_id'] = rec.partner_id.id
            #ctx['default_type'] = 'out_invoice'
            #ctx['default_fel_gt_invoice_type'] = 'nota_debito'
            # ctx['default_source_debit_note_id'] = invoice_data.id

            view_id = self.env.ref('account.view_move_form').id
            return {
                'name': _('Create invoice/bill'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'account.move',
                'view_id': self.env.ref('account.view_move_form').id,
                'context': ctx
            }

    def get_link(self):
        fel_certifier = self.env.company.fel_certifier
        for rec in self:
            rec.fel_link = ""
            if fel_certifier == 'digifact':
                digifact_user = self.env.company.digifact_username
                company_vat = self.company_id.vat
                link_fel = "felgttestaws.digifact.com.gt"
                if rec.journal_id.is_fel == "production":
                    link_fel = "felgtaws.digifact.com.gt"
                if rec.uuid_original is not False:                    
                    rec.fel_link = "https://"+str(link_fel)+"/guest/api/FEL?DATA="+str(company_vat)+"%7C"+str(rec.uuid_original)+"%7C"+str(digifact_user)
                elif rec.uuid is not False:
                    rec.fel_link = "https://"+str(link_fel)+"/guest/api/FEL?DATA="+str(company_vat)+"%7C"+str(rec.uuid)+"%7C"+str(digifact_user)
                else:
                    rec.fel_link = ""
                    
            if fel_certifier == 'infile':
                if rec.uuid_original is not False:
                    rec.fel_link = "https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid="+str(rec.uuid_original)
                elif rec.uuid is not False:
                    rec.fel_link = "https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid="+str(rec.uuid)
                else:
                    rec.fel_link = ""
            if fel_certifier == 'forcon':
                uuid = ""
                if rec.uuid_original is not False:
                    uuid = rec.uuid_original
                elif rec.uuid is not False:
                    uuid = rec.uuid
                if rec.journal_id.forcon_fel == 'development':
                    rec.fel_link =  "http://pruebasfel.eforcon.com/feldev/facturaelectronica/EfcVisorDTE?Autorizacion=%s&Emisor=%s"%(str(uuid), str(self.company_id.vat))
                else:
                    rec.fel_link = False

    def generate_g4s_pdf(self):
        
        name = 'DTE-' + str(self.dte_number)
        options = {
            'invoice_id': self.id,
            'uuid': self.uuid,
            'pdf_name': name
        }

        """return {
            'type': 'ir_actions_pt_multicert_felgt_download',
            'data': {
                'model': 'account.move',
                'options': json.dumps(options),
                'output_format': 'pdf_g4s'
            }
        }"""
        return {
            'type': 'ir.actions.report',
            'report_name':'report_g4s',
            'model':'pt_multicert_felgt.g4s_pdf.report',
            'options': json.dumps(options),
            'report_type':"g4s_pdf"
        } 

    def get_g4s_pdf(self, options, response):
        uuid = options['uuid']
        invoice_id = options['invoice_id']
        
        invoice_data = self.env['account.move'].search([
            ('id', '=', invoice_id)
        ])
        
        if invoice_data and invoice_data.company_id:
            company_id = invoice_data.company_id
            
            company_vat = company_id.vat
            requestor_id = company_id.requestor_id
            username = company_id.g4s_username
            active_env = company_id.g4s_environment
            env_url = company_id.g4s_dev_url
            if active_env == 'production':
                env_url = company_id.g4s_prod_url

            second_wsdl = env_url+'?wsdl'
            client = zeep.Client(wsdl=second_wsdl)
            
            request_data = {
                'Requestor': requestor_id,
                'Transaction': 'GET_DOCUMENT',
                'Country': 'GT',
                'Entity': company_vat,
                'User': requestor_id,
                'UserName': username,
                'Data1': uuid,
                'Data2': '',
                'Data3': 'PDF'
            }
            
            service_response = client.service.RequestTransaction(**request_data)
            
            if 'ResponseData' in service_response:
                if 'ResponseData3' in service_response['ResponseData']:
                    pdf_b64_data = service_response['ResponseData']['ResponseData3']
                    bytes = base64.b64decode(pdf_b64_data, validate=True)
            
                    if bytes[0:4] != b'%PDF':
                        raise ValueError('Missing the PDF file signature')

                    output = io.BytesIO()
                    
                    output.seek(0)
                    response.stream.write(bytes)
                    output.close()           
                

    def set_credit_note(self):
        for rec in self:
            rec.credit_note = False
            if rec.is_receipt:
                rec.credit_note = True

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        current_currency = self.currency_id
        if self.partner_id.invoice_currency:
            self.currency_id = self.partner_id.invoice_currency
        else:
            if self.journal_id.currency_id:
                self.currency_id = self.journal_id.currency_id
            else:
                self.currency_id = self.env.company.currency_id

    @api.onchange('fel_gt_invoice_type')
    def onchange_fel_gt_invoice_type(self):
        if 'type_invoice' in self.env['account.move']._fields:
            
            if self.fel_gt_invoice_type == "especial":
                self.type_invoice = 'special_invoice'
            elif self.fel_gt_invoice_type == "normal":
                self.type_invoice = 'normal_invoice'
            else:
                self.type_invoice = self.fel_gt_invoice_type

    def get_type_journal(self):

        for rec in self:

            if 'is_receipt_journal' in self.env['account.journal']._fields:
                if rec.journal_id.is_receipt_journal:
                    rec.is_receipt = True
                else:
                    rec.is_receipt = False
            else:
                rec.is_receipt = False

    @api.onchange('journal_id')
    def onchange_journal_id(self):

        if 'is_receipt_journal' in self.env['account.journal']._fields:
            if self.journal_id.is_receipt_journal:
                self.is_receipt = True
            else:
                self.is_receipt = False
        else:
            self.is_receipt = False

    def _post(self, soft=True):
        fel_certifier = self.env.company.fel_certifier
        uuid = ""
        serie = ""
        dte_number = ""
        dte_date = ""
        sat_ref_id = ""
        if soft:
            return super(AccountMove, self)._post(soft)
        if len(self) == 0:
            return super(AccountMove, self)._post(soft)
        for move in self:
            is_receipt = False
            if 'is_receipt_journal' in self.env['account.journal']._fields:
                is_receipt = move.is_receipt
            if not move.is_invoice(include_receipts=True):
                return super(AccountMove, self)._post(soft)
            if move.is_invoice(include_receipts=True):
                if fel_certifier == "digifact":
                    # Updated to process the data returned by the DIGIFACT WS
                    if move.journal_id.is_fel == 'inactive':
                        return super(AccountMove, self)._post(soft)
                if fel_certifier == "infile":
                    if move.journal_id.infile_fel_active is False:
                        return super(AccountMove, self)._post(soft)
                if fel_certifier == "g4s":
                    if move.journal_id.g4s_fel_active is False:
                        return super(AccountMove, self)._post()
                
                if fel_certifier == "guatefacturas":
                    if move.journal_id.guatefacturas_fel == 'inactive':
                        return super(AccountMove, self)._post()
                if fel_certifier == "forcon":
                    if move.journal_id.forcon_fel_active is False:
                        return super(AccountMove, self)._post(soft)
                invoice_response = super(AccountMove, self)._post(soft)

                if move.move_type == "in_invoice":
                    move.total_in_letters = str(number2text(move.amount_total + move.isr_withold_amount + move.iva_withold_amount))
                    if not is_receipt:
                        if move.fel_gt_invoice_type == 'especial':

                            if fel_certifier == "guatefacturas":
                                xml_data = move.set_data_for_invoice_guatefacturas(5)
                                uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data, 'fel', 5)
                            else:
                                xml_data = move.set_data_for_invoice_special(fel_certifier)
                                uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                            message = _("Facturación Electrónica Especial: Serie %s  Número %s") % (serie, dte_number)
                            move.message_post(body=message)
                            move.uuid = uuid
                            move.serie = serie
                            move.dte_number = dte_number
                            move.sat_ref_id = sat_ref_id
                            dte_given_time = dateutil.parser.parse(dte_date)
                            timezone_gt_adjust = timedelta(hours=6)
                            gt_time = dte_given_time + timezone_gt_adjust
                            dte_timedate_format = "%Y-%m-%d %H:%M:%S"
                            gt_time = gt_time.strftime(dte_timedate_format)
                            move.dte_date = gt_time
                            if dte_number:
                                move.name = "DTE-" + str(dte_number)

                if move.move_type == "out_invoice":
                    move.total_in_letters = str(number2text(move.amount_total + move.isr_withold_amount + move.iva_withold_amount))
                    if not is_receipt:
                        if move.fel_gt_invoice_type == 'normal':
                            
                            if fel_certifier == "guatefacturas":
                                xml_data = move.set_data_for_invoice_guatefacturas()
                            else:
                                xml_data = move.set_data_for_invoice(fel_certifier)
                                
                            uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                            message = _("Facturación Electrónica: Serie %s  Número %s") % (serie, dte_number)
                        if move.fel_gt_invoice_type == 'especial':
                            message = ""
                            raise UserError("Las facturas especiales FEL solo pueden ser emitidas desde la facturación de proveedores")                            
                        if move.fel_gt_invoice_type == 'cambiaria':
                            #if move.dte_number:
                            #    raise UserError('Esta factura ya posee un número de DTE')
                            if fel_certifier == "guatefacturas":
                                xml_data = move.set_data_for_invoice_guatefacturas(2)
                                uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data, 'fel', 2)
                            else:
                                xml_data = move.set_data_for_invoice_cambiaria(fel_certifier)
                                uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                            message = _("Facturación Electrónica Cambiaria: Serie %s  Número %s") % (serie, dte_number)
                        if move.fel_gt_invoice_type == 'cambiaria_exp':
                            #if move.dte_number:
                            #    raise UserError('Esta factura ya posee un número de DTE')
                            xml_data = move.set_data_for_invoice_cambiaria_exp(fel_certifier)
                            uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                            message = _("Facturación Electrónica: Serie %s  Número %s") % (serie, dte_number)

                        if move.fel_gt_invoice_type == 'nota_debito':
                            if fel_certifier == "guatefacturas":
                                xml_data = move.set_data_for_invoice_guatefacturas(9)
                                uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data, 'fel', 9)
                            else:
                                xml_data = move.set_data_for_invoice_nota_debito(fel_certifier)
                            uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                            message = _("Nota de Débito: Serie %s  Número %s") % (serie, dte_number)

                    if is_receipt:
                        if fel_certifier == "guatefacturas":
                            xml_data = move.set_data_for_invoice_guatefacturas(8)
                            uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data, 'fel', 8)
                        else:
                            xml_data = move.set_data_for_invoice_recibo(fel_certifier)
                            uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                        message = _("Recibo: Serie %s  Número %s") % (serie, dte_number)

                    move.message_post(body=message)
                    move.uuid = uuid
                    move.uuid_original = uuid
                    move.serie = serie
                    move.serie_original = serie
                    move.dte_number = dte_number
                    move.dte_number_original = dte_number
                    move.sat_ref_id = sat_ref_id
                    dte_given_time = dateutil.parser.parse(dte_date)
                    timezone_gt_adjust = timedelta(hours=6)
                    gt_time = dte_given_time + timezone_gt_adjust
                    dte_timedate_format = "%Y-%m-%d %H:%M:%S"
                    gt_time = gt_time.strftime(dte_timedate_format)
                    move.dte_date = gt_time
                    if dte_number:
                        move.name = "DTE-" + str(dte_number)

                if move.move_type == "out_refund" and not move.credit_note:
                    
                    if fel_certifier == "guatefacturas":
                        xml_data = move.set_data_for_invoice_guatefacturas(10)
                        uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data, 'fel', 10)
                    else:
                        xml_data = move.set_data_for_invoice_credit(fel_certifier)
                        uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                    message = _("Nota de Crédito: Serie %s  Número %s") % (serie, dte_number)
                    move.message_post(body=message)
                    move.uuid = uuid
                    move.uuid_original = uuid
                    move.serie = serie
                    #move.serie_original = serie
                    move.sat_ref_id = sat_ref_id
                    move.dte_number = dte_number
                    #move.dte_number_original = dte_number
                    dte_given_time = dateutil.parser.parse(dte_date)
                    timezone_gt_adjust = timedelta(hours=6)
                    gt_time = dte_given_time + timezone_gt_adjust
                    dte_timedate_format = "%Y-%m-%d %H:%M:%S"
                    gt_time = gt_time.strftime(dte_timedate_format)
                    move.dte_date = gt_time
                    if dte_number:
                        move.name = "DTE-" + str(dte_number)

                if move.move_type == "out_refund" and move.credit_note is True:

                    xml_data = move.set_data_for_invoice_abono(fel_certifier)
                    uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data)
                    message = _("Nota de Abono: Serie %s  Número %s") % (serie, dte_number)
                    move.message_post(body=message)
                    move.uuid = uuid
                    move.uuid_original = uuid
                    move.serie = serie
                    #move.serie_original = serie
                    move.dte_number = dte_number
                    #move.dte_number_original = dte_number
                    move.sat_ref_id = sat_ref_id
                    dte_given_time = dateutil.parser.parse(dte_date)
                    timezone_gt_adjust = timedelta(hours=6)
                    gt_time = dte_given_time + timezone_gt_adjust
                    dte_timedate_format = "%Y-%m-%d %H:%M:%S"
                    gt_time = gt_time.strftime(dte_timedate_format)
                    move.dte_date = gt_time
                    if dte_number:
                        move.name = "DTE-" + str(dte_number)
                
                return invoice_response

    def button_draft(self):
        for move in self:
            
            if move.is_invoice():

                is_receipt = False
                if 'is_receipt_journal' in self.env['account.journal']._fields:
                    is_receipt = move.is_receipt

                fel_certifier = self.env.company.fel_certifier
                uuid = ""
                serie = ""
                dte_number = ""
                dte_date = ""
                sat_ref_id = ""
                if fel_certifier == "digifact":
                    # Updated to process the data returned by the DIGIFACT WS
                    if move.journal_id.is_fel == 'inactive':
                        move.write({'state': 'cancel'})
                        return super(AccountMove, self).button_draft()
                if fel_certifier == "infile":
                    if move.journal_id.infile_fel_active is False:
                        move.write({'state': 'cancel'})
                        return super(AccountMove, self).button_draft()
                if fel_certifier == "guatefacturas":
                    # Updated to process the data returned by the DIGIFACT WS
                    if move.journal_id.guatefacturas_fel == 'inactive':
                        move.write({'state': 'cancel'})
                        return super(AccountMove, self).button_draft()
                if fel_certifier == "forcon":
                    if move.journal_id.forcon_fel_active is False:
                        move.write({'state': 'cancel'})
                        return super(AccountMove, self).button_draft() 
                if fel_certifier == "g4s":
                    if move.journal_id.g4s_fel_active is False:
                        move.write({'state': 'cancel'})
                        return super(AccountMove, self).button_draft() 
                
                if move.move_type == "in_invoice" and not move.fel_enable_cancel_bypass:
                    move.uuid_original = move.uuid
                    xml_data = self.set_data_for_invoice_cancel(fel_certifier)
                    uuid, serie, dte_number, dte_date, sat_ref_id = self.send_data_api(xml_data, 'cancel')
                    if is_receipt:
                        message = _("Recibo Cancelado: Serie %s  Número %s") % (serie, dte_number)
                    else:
                        message = _("Factura Cancelada: Serie %s  Número %s") % (serie, dte_number)
                    move.message_post(body=message)
                    move.uuid = uuid
                    move.serie = serie
                    move.dte_number = dte_number
                    move.sat_ref_id = sat_ref_id

                    dte_given_time = dateutil.parser.parse(dte_date)
                    timezone_gt_adjust = timedelta(hours=6)
                    gt_time = dte_given_time + timezone_gt_adjust
                    dte_timedate_format = "%Y-%m-%d %H:%M:%S"
                    gt_time = gt_time.strftime(dte_timedate_format)
                    move.dte_date = gt_time
                    self.write({'state': 'cancel'})
                
                if move.move_type == "out_invoice" and not move.fel_enable_cancel_bypass:
                    move.uuid_original = move.uuid
                    #move.serie_original = move.serie
                    #move.dte_number_original = move.dte_number
                    if fel_certifier == "guatefacturas":
                        uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api("", 'cancel')    
                    else:
                        xml_data = move.set_data_for_invoice_cancel(fel_certifier)
                        uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data, 'cancel')
                    if is_receipt:
                        message = _("Recibo Cancelado: Serie %s  Número %s") % (serie, dte_number)
                    else:
                        message = _("Factura Cancelada: Serie %s  Número %s") % (serie, dte_number)
                    move.message_post(body=message)
                    move.uuid = uuid
                    move.serie = serie
                    move.dte_number = dte_number
                    move.sat_ref_id = sat_ref_id
                    dte_given_time = dateutil.parser.parse(str(dte_date))
                    timezone_gt_adjust = timedelta(hours=6)
                    gt_time = dte_given_time + timezone_gt_adjust
                    dte_timedate_format = "%Y-%m-%d %H:%M:%S"
                    gt_time = gt_time.strftime(dte_timedate_format)
                    move.dte_date = gt_time
                    move.write({'state': 'cancel'})
                if move.move_type == "out_refund" and move.uuid:
                    move.uuid_original = move.uuid
                    #move.serie_original = move.serie
                    #move.dte_number_original = move.dte_number
                    xml_data = move.set_data_for_invoice_cancel(fel_certifier)
                    uuid, serie, dte_number, dte_date, sat_ref_id = move.send_data_api(xml_data, 'cancel')
                    if move.credit_note is True:
                        message = _("Nota de Abono Cancelada: Serie %s  Número %s") % (serie, dte_number)
                    else:
                        message = _("Nota de Crédito Cancelada: Serie %s  Número %s") % (serie, dte_number)
                    move.message_post(body=message)
                    move.uuid = uuid
                    move.serie = serie
                    move.dte_number = dte_number
                    move.sat_ref_id = sat_ref_id
                    dte_given_time = dateutil.parser.parse(dte_date)
                    timezone_gt_adjust = timedelta(hours=6)
                    gt_time = dte_given_time + timezone_gt_adjust
                    dte_timedate_format = "%Y-%m-%d %H:%M:%S"
                    gt_time = gt_time.strftime(dte_timedate_format)
                    move.dte_date = gt_time
                    move.write({'state': 'cancel'})

        res = super(AccountMove, self).button_draft()

    # FACTURA NORMAL GUATEFACTURA
    def set_data_for_invoice_guatefacturas(self, type_document=1):
        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider
        
        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        if type_document == 5:
            if not self.partner_id.dpi_number:
                raise ValidationError('Debe ingresar el número D.P.I. del proveedor')
            
            if not self.company_id.state_id:
                raise ValidationError('Debe indicar el departamento del emisión del documento')

            if not self.company_id.city:
                raise ValidationError('Debe indicar el municipio del emisión del documento')
        
        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%d/%m/%Y')
        last_5_days = date.today() - timedelta(5)
        ##if last_5_days > self.invoice_date:
        ##    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%d/%m/%Y')
        else:
            fecha_emision = self.invoice_date.__format__('%d/%m/%Y')
        currency_code = "GTQ"
        
        invoice_lines = self.invoice_line_ids
        
        BienOServicio = "B"
        for line in invoice_lines:
            if line.product_id.type == 'service':
                BienOServicio = "S"
        
        DocElectronico = Element('DocElectronico')
        Encabezado = SubElement(DocElectronico, 'Encabezado')
        Receptor = SubElement(Encabezado, 'Receptor')
        
        if type_document == 5:
                NITReceptor = SubElement(Receptor, 'NITVendedor')
                NITReceptor.text = str(vat)
                
                Nombre = SubElement(Receptor, 'Nombre')
                Nombre.text = self.partner_id.name
                
                Direccion = SubElement(Receptor, 'Direccion')
                Direccion.text = self.partner_id.street or "Ciudad"
        else:
            NITReceptor = SubElement(Receptor, 'NITReceptor')
            NITReceptor.text = str(vat)
            
            Nombre = SubElement(Receptor, 'Nombre')
            Nombre.text = self.partner_id.name
            
            Direccion = SubElement(Receptor, 'Direccion')
            Direccion.text = self.partner_id.street or "Ciudad"

        InfoDoc = SubElement(Encabezado, 'InfoDoc')
        
        TipoVenta = SubElement(InfoDoc, 'TipoVenta')
        TipoVenta.text = BienOServicio
        
        DestinoVenta = SubElement(InfoDoc, 'DestinoVenta')
        DestinoVenta.text = "1"
        
        Fecha = SubElement(InfoDoc, 'Fecha')
        Fecha.text = fecha_emision
        
        currency_fel_id = 1
        if currency_code == 'USD':
            currency_fel_id = 2
            
        Moneda = SubElement(InfoDoc, 'Moneda')
        Moneda.text = str(currency_fel_id)
        
        if type_document == 5:
            Tasa_Cambio = SubElement(InfoDoc, 'Tasa_Cambio')
            Tasa_Cambio.text = str(conversion_rate)
        else:
            Tasa = SubElement(InfoDoc, 'Tasa')
            Tasa.text = str(conversion_rate)
        
        if type_document == 5:
            TipoDocIdentificacion = SubElement(InfoDoc, 'TipoDocIdentificacion')
            TipoDocIdentificacion.text = str(2)
            
            NumeroIdentificacion = SubElement(InfoDoc, 'NumeroIdentificacion')
            NumeroIdentificacion.text = str(self.partner_id.dpi_number)
            
            PaisEmision = SubElement(InfoDoc, 'PaisEmision')
            PaisEmision.text = str(1)
            
            DepartamentoEmision = SubElement(InfoDoc, 'DepartamentoEmision')
            department_id = guatefacturas_departments_mapping(self.company_id.state_id.name.upper())
            DepartamentoEmision.text = department_id
            
            MunicipioEmision = SubElement(InfoDoc, 'MunicipioEmision')
            township_id = guatefacturas_townships_mapping(self.company_id.city, department_id)
            MunicipioEmision.text = township_id
        
        Referencia = SubElement(InfoDoc, 'Referencia')
        ts = time.time()
        odoo_reference = "DTE-" + str(self.id) + '_' + str(ts)
        Referencia.text = odoo_reference
        
        if type_document == 5:
            PorcISR = SubElement(InfoDoc, 'PorcISR')
            PorcISR.text = str(0.05)
        
        NumeroAcceso = SubElement(InfoDoc, 'NumeroAcceso')
        #NumeroAcceso.text = "1"
        NumeroAcceso.text = ""
        
        """
        NOTA: PENDIENTE DE VALIDAR RECUPERACION DE DATOS
        """
        
        SerieAdmin = SubElement(InfoDoc, 'SerieAdmin')
        #SerieAdmin.text = "DTE-"+ str(self.id)
        SerieAdmin.text = ""
        
        NumeroAdmin = SubElement(InfoDoc, 'NumeroAdmin')
        #NumeroAdmin.text = str(self.id)
        NumeroAdmin.text = ""
        
        Reversion = SubElement(InfoDoc, 'Reversion')
        Reversion.text = "N"
        
        Totales = SubElement(Encabezado, 'Totales')
        
        #Get totals and details from invoice line
        invoice_line = self.invoice_line_ids
        invoice_counter = 0
        price_tax_total = 0
        grand_total = 0
        timbre_tax_fel = False
        has_one_timbre_tax_fel = False
        # Variables para manejo de timbre de prensa
        total_iva = 0
        total_timbre = 0
        
        product_details = []
        # Precio Bruto
        gross_price = 0
        total_discounts = 0
        other_taxes_total = 0
        
        # Facturas Especiales
        isr_especial_total = 0
        iva_especial_total = 0
        
        # LineasFactura
        for line in invoice_line:
            invoice_counter += 1
            
            BienOServicio = "B"
            if line.product_id.type == 'service':
                BienOServicio = "S"

            timbre_tax_fel = False
            if line.tax_ids:
                for tax in line.tax_ids:
                    if tax.fel_timbre_tax:
                        timbre_tax_fel = True
                        has_one_timbre_tax_fel = True

            if line.tax_ids:
                tax = "IVA"

            
            else:
                raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))
            
            # ------------------------------
            # --- CHECK INOVICE CURRENCY ---
            # ------------------------------

            line_price_unit = line.price_unit
            line_price = line.quantity * line.price_unit
            line_price_total = line.price_total
            line_price_subtotal = line.price_subtotal
            price_tax = line_price_total - line_price_subtotal

            # Variables para manejo de timbre de prensa --- CIG
            iva_amount = 0
            timbre_amount = 0
            iva_timbre_total = 0

            if timbre_tax_fel:
                line_price_unit = line.price_unit / 1.125
                timbre_unit = round(line_price_unit, 2) * 0.005
                line_price_unit = line.price_unit - round(timbre_unit, 2)
                line_price = line.quantity * round(line_price_unit, 2)

                monto_gravable = round(line_price, 2) / 1.12
                base_line = round(line_price, 2) / 1.12
                iva_amount = round(base_line, 2) * 0.12
                timbre_amount = round(base_line, 2) * 0.005

                total_iva += iva_amount
                total_timbre += timbre_amount
                iva_timbre_total = line_price + timbre_amount

            tax_amount = 0
            if make_conversion:
                set_conversion_data = {
                    "line": line,
                    "conversion_rate": conversion_rate
                }
                get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                line_price_unit = get_conversion_data['line_price_unit']
                line_price = get_conversion_data['line_price']
                line_price_total = get_conversion_data['line_price_total']
                line_price_subtotal = get_conversion_data['line_price_subtotal']
                price_tax = get_conversion_data['price_tax']
                grand_total += line_price_total

            line_price = round(line_price, 2)            
            line_gross_price = round(line_price_unit * line.quantity, 2)
            line_gross_price = line_gross_price
            gross_price += line_gross_price
            product_description = line.product_id.name
            line_code_divider = self.company_id.fel_default_code_divider
            
            if line_code_divider:
                if line.product_id.default_code:
                    product_description = line.product_id.default_code + "@" + line.product_id.name
                else:
                    product_description = "@" + line.product_id.name
            else:
                product_description = line.product_id.name
            
            iva_line_amount = 0
            other_taxes = 0
            if timbre_tax_fel:
                iva_line_amount = iva_amount
                other_taxes = timbre_amount
                price_tax_total = price_tax_total + iva_amount
                price_tax_total = price_tax_total + timbre_amount
            else:
                iva_line_amount = round(price_tax, 2)
                price_tax_total = price_tax_total + price_tax
                if has_one_timbre_tax_fel:
                    total_iva += price_tax
            line_discount = round((line.discount * (line.quantity * line_price_unit))/100, 2)
            total_discounts += line_discount
            other_taxes_total += other_taxes
            impBruto = line_price_unit * line.quantity
            product_id = line.product_id.id
            isr_amount = 0
            
            if type_document == 5:
                product_id = 1
                isr_amount = line.price_unit * line.quantity /1.12 *0.05
                isr_amount = round(isr_amount, 2)
                iva_line_amount = line.price_unit * line.quantity / 1.12
                iva_line_amount = iva_line_amount * 0.12
                iva_line_amount = round(iva_line_amount, 2)
                isr_especial_total += isr_amount
                iva_especial_total += iva_line_amount
                line_price_total = line_gross_price
            product_detail = {
                "Producto": str(product_id),
                "Descripcion": str(product_description),
                "Medida": "1",
                "Cantidad": str(line.quantity),
                "Precio": str(line_price_unit),
                "PorcDesc": str(dropzeros(line.discount)),
                "ImpBruto": str(line_gross_price),
                "ImpDescuento": str(dropzeros(line_discount)),
                "ImpExento": "0",
                "ImpOtros": str(dropzeros(other_taxes)),
                "ImpNeto": str(dropzeros(line_price_subtotal)),
                "ImpIsr": str(isr_amount),
                "ImpIva": str(dropzeros(iva_line_amount)),
                "ImpTotal": str(dropzeros(round(line_price_total, 2))),
                "TipoVentaDet": BienOServicio                
            }
            product_details.append(product_detail)
        
        Bruto = SubElement(Totales, 'Bruto')
        Bruto.text = str(gross_price)
        
        Descuento = SubElement(Totales, 'Descuento')
        Descuento.text = str(dropzeros(total_discounts))
        
        Exento = SubElement(Totales, 'Exento')
        Exento.text = "0"
        
        Otros = SubElement(Totales, 'Otros')
        Otros.text = str(dropzeros(other_taxes_total))
        
        Neto = SubElement(Totales, 'Neto')
        Neto.text = str(dropzeros(self.amount_untaxed))
        
        invoice_total = self.amount_untaxed
        
        if type_document == 5:
            Isr = SubElement(Totales, 'Isr')
            invoice_total += isr_especial_total
            Isr.text = str(isr_especial_total)
        else:
        
            Isr = SubElement(Totales, 'Isr')
            invoice_total += self.isr_withold_amount
            Isr.text = str(dropzeros(self.isr_withold_amount))
        
        if type_document == 5:
            Iva = SubElement(Totales, 'Iva')
            invoice_total += iva_especial_total
            Iva.text = str(round(iva_especial_total, 2))
        else:
            if has_one_timbre_tax_fel:        
                Iva = SubElement(Totales, 'Iva')
                invoice_total += total_iva
                Iva.text = str(round(dropzeros(total_iva), 2))
            else:
                Iva = SubElement(Totales, 'Iva')
                invoice_total += price_tax_total
                Iva.text = str(round(dropzeros(price_tax_total), 2))

        if type_document == 5:
            Total = SubElement(Totales, 'Total')
            Total.text = str(gross_price)
        else:
            if (invoice_total == 0):
                invoice_total = self.amount_total
            Total = SubElement(Totales, 'Total')
            Total.text = str(dropzeros(invoice_total))
        
        if type_document != 5:
            DatosAdicionales = SubElement(Encabezado, 'DatosAdicionales')
            if type_document == 2:
                AbonosFacturaCambiaria = SubElement(Encabezado, 'AbonosFacturaCambiaria')
                
                Abono = SubElement(AbonosFacturaCambiaria, 'Abono')
                
                NumeroAbono = SubElement(Abono, 'NumeroAbono')
                NumeroAbono.text = str("1")
                
                date_due = self.invoice_date_due
                formato2 = "%Y%m%d"
                date_due = date_due.strftime(formato2)
                
                FechaVencimiento = SubElement(Abono, 'FechaVencimiento')
                FechaVencimiento.text = str(date_due)
                
                MontoAbono = SubElement(Abono, 'MontoAbono')
                MontoAbono.text = str(round(self.amount_total, 2))
                
        
        Detalles = SubElement(DocElectronico, 'Detalles')
        
        
        for product in product_details:
            Productos = SubElement(Detalles, 'Productos')
            Producto = SubElement(Productos, 'Producto')
            Producto.text = product['Producto']
            
            Descripcion = SubElement(Productos, 'Descripcion')
            Descripcion.text = product['Descripcion']
            
            Medida = SubElement(Productos, 'Medida')
            Medida.text = product['Medida']
            
            Cantidad = SubElement(Productos, 'Cantidad')
            Cantidad.text = product['Cantidad']
            
            Precio = SubElement(Productos, 'Precio')
            Precio.text = product['Precio']
            
            PorcDesc = SubElement(Productos, 'PorcDesc')
            PorcDesc.text = product['PorcDesc']
            
            ImpBruto = SubElement(Productos, 'ImpBruto')
            ImpBruto.text = product['ImpBruto']
            
            ImpDescuento = SubElement(Productos, 'ImpDescuento')
            ImpDescuento.text = product['ImpDescuento']
            
            ImpExento = SubElement(Productos, 'ImpExento')
            ImpExento.text = product['ImpExento']
                        
            ImpOtros = SubElement(Productos, 'ImpOtros')
            ImpOtros.text = product['ImpOtros']
            
            ImpNeto = SubElement(Productos, 'ImpNeto')
            ImpNeto.text = product['ImpNeto']
            
            ImpIsr = SubElement(Productos, 'ImpIsr')
            ImpIsr.text = product['ImpIsr']
            
            ImpIva = SubElement(Productos, 'ImpIva')
            ImpIva.text = product['ImpIva']
            
            ImpTotal = SubElement(Productos, 'ImpTotal')
            ImpTotal.text = product['ImpTotal']
            
            if type_document != 5:
            
                TipoVentaDet = SubElement(Productos, 'TipoVentaDet')
                TipoVentaDet.text = product['TipoVentaDet']
                
                DatosAdicionalesProd = SubElement(Productos, 'DatosAdicionalesProd')
                #DatosAdicionalesProd.text = product['DatosAdicionalesProd']
        
        if type_document != 5:
            DocAsociados = SubElement(Detalles, 'DocAsociados')
            
            DASerie = SubElement(DocAsociados, 'DASerie')
            if type_document == 10:
                DASerie.text = self.serie_original
            else:
                DASerie.text = ""
            
            DAPreimpreso = SubElement(DocAsociados, 'DAPreimpreso')
            if type_document == 10:
                DAPreimpreso.text = self.dte_number_original
            else:
                DAPreimpreso.text = ""
        
        xml_content = tostring(DocElectronico)
        date_due = self.invoice_date_due
        date_due_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_due_format)
        
        store_sent_xml(self, xml_content, vat, date_due, 'guatefacturas')
        
        return xml_content

    # FACTURA NORMAL
    def set_data_for_invoice(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        vat = ""

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False and self.company_id.street != '':
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.invoice_date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)
        if fel_certifier == 'g4s':
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        else:
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})

        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider
        
        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        ##if last_5_days > self.invoice_date:
        ##    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        currency_code = "GTQ"
        
        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code
            
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name
        
        
        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department
        
        
        #FIXME: ARREGLAR EL CÓDIGO DE ESTABLECIMIENTO
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="FACT")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=company_vat, NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        
        
        
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"
        
        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"
        #xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        # Frases

        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        company_codes = self.get_company_code() 
        for company_type in company_codes:
            
            if company_type == "1" and company_codes[company_type] == "3" and self.company_id.fel_resolution_number and self.company_id.fel_resolution_date:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=company_type, CodigoEscenario=company_codes[company_type], NumeroResolucion=self.company_id.fel_resolution_number, FechaResolucion=self.company_id.fel_resolution_date)
            else:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=company_type, CodigoEscenario=company_codes[company_type])
        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        invoice_counter = 0
        price_tax_total = 0
        grand_total = 0
        _logger.info('LINES ' + str(len(invoice_line)))
        timbre_tax_fel = False
        has_one_timbre_tax_fel = False
        # Variables para manejo de timbre de prensa
        total_iva = 0
        total_timbre = 0
        has_advance_payment = False
        advance_payment_amount = 0
        iva_advance_amount = 0
        # LineasFactura
        #FIXME:
        invoice_lines_len = len(invoice_line.filtered(lambda line: line.quantity != -1 and line.display_type not in ('line_section', 'line_note')))
        index_counter = 1 #Variable utilizada para particionar la lista de self.invoice_line_ids, con el objetivo de recorrer las lineas de facturas que estan delante de una línea para verificar cuantas son notas o secciones
        note_description = ""
        
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        
        for line in invoice_line:
            if line.display_type == 'line_note':
                note_description += line.name + " "
            if not line.display_type in ('line_section', 'line_note'):
                if line.quantity != -1:
                    invoice_counter += 1
                    BienOServicio = "B"
                    if line.product_id.type == 'service':
                        BienOServicio = "S"

                    timbre_tax_fel = False
                    if line.tax_ids:
                        for tax in line.tax_ids:
                            if tax.fel_timbre_tax:
                                timbre_tax_fel = True
                                has_one_timbre_tax_fel = True

                    # Item
                    xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))

                    if line.tax_ids:
                        tax = "IVA"
                    else:
                        if not self.company_id.fel_iva_company_exception:
                            raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

                    # ------------------------------
                    # --- CHECK INOVICE CURRENCY ---
                    # ------------------------------
                    line_price_unit = line.price_unit
                    line_price = (line.quantity * line.price_unit)
                    
                    if(self.advance_total_amount > 0):
                        line_price_total = line.price_total - self.advance_total_amount
                        line_price_subtotal = line.price_subtotal - self.advance_untaxed_amount
                        price_tax = line_price_total - line_price_subtotal
                    else:
                        line_price_total = line.price_total
                        line_price_subtotal = line.price_subtotal 
                        price_tax = line_price_total - line_price_subtotal

                    # Variables para manejo de timbre de prensa --- CIG
                    iva_amount = 0
                    timbre_amount = 0
                    iva_timbre_total = 0

                    if timbre_tax_fel:
                        line_price_unit = line.price_unit / 1.125
                        timbre_unit = round(line_price_unit, 2) * 0.005
                        line_price_unit = line.price_unit - round(timbre_unit, 2)
                        line_price = line.quantity * round(line_price_unit, 2)

                        monto_gravable = round(line_price, 2) / 1.12
                        base_line = round(line_price, 2) / 1.12
                        iva_amount = round(base_line, 2) * 0.12
                        timbre_amount = round(base_line, 2) * 0.005

                        total_iva += iva_amount
                        total_timbre += timbre_amount
                        iva_timbre_total = line_price + timbre_amount

                    tax_amount = 0
                    if make_conversion:
                        set_conversion_data = {
                            "line": line,
                            "conversion_rate": conversion_rate
                        }
                        get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                        line_price_unit = get_conversion_data['line_price_unit']
                        line_price = get_conversion_data['line_price']
                        line_price_total = get_conversion_data['line_price_total']
                        line_price_subtotal = get_conversion_data['line_price_subtotal']
                        price_tax = get_conversion_data['price_tax']
                        grand_total += line_price_total
                        
                    line_price = round(line_price, 2)

                    ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(round(line.quantity,4))
                    ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                    
                    line_description_source = self.company_id.fel_invoice_line_name
                    line_description = line.product_id.name
                    if line_description_source == 'description':
                        line_description = line.name
                    
                    discount = 0
                    disc_comment = ""

                    if self.advance_total_amount > 0:
                        discount = round((line.discount * (line.quantity * line_price_unit))/100, 2) + self.advance_total_amount
                        perc_discount = round((self.advance_total_amount/line_price)*100, 2)
                        disc_comment = " (Descuento del "+str(perc_discount)+"% por pago de anticipo)"

                    else:
                        discount = round((line.discount * (line.quantity * line_price_unit))/100, 2)

                    if line_code_divider:
                        if line.product_id.default_code:
                            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line_description
                        else:
                            ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line_description
                    else:
                        #Busca si hay una nota después de la línea actual para poder concatenarla a la descripción de la línea actual
                        note_description = self.get_description_notes(line.id, order_invoice_line)
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " " + note_description + disc_comment 
                        
                    
                    
                    ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit, 2))
                    ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(round(line_price, 2))
                    ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(discount)

                    if timbre_tax_fel:
                        # IVA
                        xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                        xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = "IVA"
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(monto_gravable, 2))
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(iva_amount, 2))
                        price_tax_total = price_tax_total + timbre_amount

                        fel_taxes['IVA'] += round(iva_amount, 2)
                        
                        # TIMBRE
                        xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = "TIMBRE DE PRENSA"
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(monto_gravable, 2))
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(timbre_amount, 2))
                        ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(iva_timbre_total, 2))
                        price_tax_total = price_tax_total + iva_amount
                        
                        fel_taxes['TIMBRE DE PRENSA'] += round(timbre_amount, 2)
                    else:

                        if line.tax_ids:
                            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                            for tax in line.tax_ids:
                                tax_name = tax.fel_tax
                        
                                xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
                                
                                if (line.discount == 0):
                                    base = line.price_unit * line.quantity
                                else:
                                    base = line.price_subtotal
                                if tax_name == "IVA":
                                    if (line.discount == 0):
                                        price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                                    else:
                                        price_tax = base * tax.amount / 100
                                else:
                                    price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)
                                
                                ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                                ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line_price_subtotal, 2))
                                price_tax = round(price_tax, 3)
                                split_num = str(price_tax).split('.')
                                if int(split_num[1]) > 0:
                                    decimal = str(split_num[1])
                                    if len(decimal) > 2:
                                        if int(decimal[2]) == 5:
                                            price_tax += 0.001

                                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(price_tax, 2))
                                fel_taxes[tax_name] += price_tax

                            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))
                            price_tax_total = price_tax_total + price_tax
                            if has_one_timbre_tax_fel:
                                total_iva += price_tax
                        else:

                            xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                            xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
                            
                            ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = "IVA"
                            ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "2"
                            ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line.price_subtotal, 2))
                            ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = "0.00"
                        
                        if not line.tax_ids:
                            ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))

            index_counter += 1 
        
        
        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        rounding_decimals = 2

        if has_one_timbre_tax_fel:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto=str(round(total_iva, 2)))
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="TIMBRE DE PRENSA", TotalMontoImpuesto=str(round(total_timbre, 2)))
            if fel_taxes['PETROLEO'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
            if fel_taxes['TURISMO HOSPEDAJE'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
            if fel_taxes['TURISMO PASAJES'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))            
            if fel_taxes['BOMBEROS'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
            if fel_taxes['TASA MUNICIPAL'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))
        else:
            if fel_taxes['IVA'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='IVA', TotalMontoImpuesto=str(round(fel_taxes['IVA'], rounding_decimals)))
            if fel_taxes['PETROLEO'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
            if fel_taxes['TURISMO HOSPEDAJE'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
            if fel_taxes['TURISMO PASAJES'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))
            if fel_taxes['TIMBRE DE PRENSA'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TIMBRE DE PRENSA', TotalMontoImpuesto=str(round(fel_taxes['TIMBRE DE PRENSA'], rounding_decimals)))
            if fel_taxes['BOMBEROS'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
            if fel_taxes['TASA MUNICIPAL'] > 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))
            if fel_taxes['IVA'] == 0:
                xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto="0.00")

        if make_conversion:
            if conversion_rate > 1.0:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva * conversion_rate
                tax_withold_amount = self.tax_withold_amount * conversion_rate
            else:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva / conversion_rate
                tax_withold_amount = self.tax_withold_amount / conversion_rate
        else:
            grand_total = self.amount_total
            tax_withholding_amount_iva = self.tax_withholding_amount_iva
            tax_withold_amount = self.tax_withold_amount

        if 'tax_withholding_amount_iva' in self.env['account.move']._fields:
            if self.tax_withholding_amount_iva > 0:
                if self.tax_withholding_iva != 'iva_forgiveness':
                    grand_total = grand_total + tax_withholding_amount_iva
                
        if 'tax_withold_amount' in self.env['account.move']._fields:
            if self.tax_withold_amount > 0:
                grand_total = grand_total + tax_withold_amount
        if timbre_tax_fel:
            ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(iva_timbre_total, 2))
        else:
            ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total, 2))
        if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
            # Adenda
            xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
            if self.company_id.fel_addendum_journal_sequence:
                ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
            if make_conversion and self.company_id.fel_addendum_currency_rate:
                # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                if conversion_rate > 1.0:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                else:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)
        date_due = self.invoice_date_due
        date_due_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_due_format)
        
        xml_content = ET.tostring(xml_root, encoding="UTF-8", method="xml")
        search_string = "ns0"
        string_remplace = "dte"
        
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')
        
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)
        _logger.info('FEL CONTENT ' + str(xml_content))
        
        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)
        return xml_content

    # NOTA DEBITO
    def set_data_for_invoice_nota_debito(self, fel_certifier):
        
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0 GT_Complemento_Referencia_Nota-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        complemento_xmlns = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.invoice_date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        if self.source_debit_note_id is False:
            raise UserError(RAISE_VALIDATION_SOURCE_UUID)

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider

        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        currency_code = "GTQ"
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name
        
        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code
        
        
        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department
        
        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")
        #fecha_emision = dt.datetime.now(gettz("America/Guatemala")).isoformat()   #dt.datetime.now().isoformat()
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        ##if last_5_days > self.invoice_date:
        ##    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        vals = {
            "codigo_postal": self.company_id.zip,
            "municipio": self.company_id.city,
            "Departamento": self.company_id.state_id.name, 
            "Pais": self.company_id.country_id.code
        }
        
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="NDEB")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=str(company_vat), NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            if self.fel_gt_invoice_type == 'especial':
                vat = company_vat
            else:
                vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"
        
        # Frases

        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        company_codes = self.get_company_code() 
        for company_type in company_codes:
            
            if company_type == "1" and company_codes[company_type] == "3" and self.company_id.fel_resolution_number and self.company_id.fel_resolution_date:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=company_type, CodigoEscenario=company_codes[company_type], NumeroResolucion=self.company_id.fel_resolution_number, FechaResolucion=self.company_id.fel_resolution_date)
            else:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=company_type, CodigoEscenario=company_codes[company_type])

        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        cnt = 0
        price_tax_total = 0
        grand_total = 0
        # LineasFactura
        
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        
        for line in invoice_line:
            if not line.display_type in ('line_section', 'line_note'):
                cnt += 1
                p_type = 0
                BienOServicio = "B"
                if line.product_id.type == 'service':
                    p_type = 1
                    BienOServicio = "S"
                for tax in line.tax_ids:
                    if tax.price_include:
                        tax_in_ex = 0

                # ------------------------------
                # --- CHECK INOVICE CURRENCY ---
                # ------------------------------

                line_price_unit = line.price_unit
                line_price = line.quantity * line.price_unit
                line_price_total = line.price_total
                line_price_subtotal = line.price_subtotal
                price_tax = line_price_total - line_price_subtotal
                tax_amount = 0
                if make_conversion:
                    set_conversion_data = {
                        "line": line,
                        "conversion_rate": conversion_rate
                    }
                    get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                    line_price_unit = get_conversion_data['line_price_unit']
                    line_price = get_conversion_data['line_price']
                    line_price_total = get_conversion_data['line_price_total']
                    line_price_subtotal = get_conversion_data['line_price_subtotal']
                    price_tax = get_conversion_data['price_tax']
                    grand_total += line_price_total

                # Item
                xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(cnt))

                line_price = round(line_price, 2)

                ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
                ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                
                line_description_source = self.company_id.fel_invoice_line_name
                line_description = line.product_id.name
                if line_description_source == 'description':
                    line_description = line.name
                
                if line_code_divider:
                    if line.product_id.default_code:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line_description
                    else:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line_description
                else:
                    note_description = self.get_description_notes(line.id, order_invoice_line)
                    ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " "+note_description
                
                    
                ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit,2))
                ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
                ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line_price_unit))/100, 2))

                if line.tax_ids:
                    tax = "IVA"
                else:
                    if not self.company_id.fel_iva_company_exception:
                        raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

                if line.tax_ids:
                    xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                    for tax in line.tax_ids:
                        tax_name = tax.fel_tax
                        xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
                        
                        if (line.discount == 0):
                            base = line.price_unit * line.quantity
                        else:
                            base = line.price_subtotal
                        if tax_name == "IVA":
                            if (line.discount == 0):
                                price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                            else:
                                price_tax = base * tax.amount / 100
                        else:
                            price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)

                        ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line_price_subtotal, 2))
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(price_tax, 2))
                        fel_taxes[tax_name] += price_tax
                        price_tax_total = price_tax_total + price_tax
                        
                ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))
                    

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        rounding_decimals = 2
        if fel_taxes['IVA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='IVA', TotalMontoImpuesto=str(round(fel_taxes['IVA'], rounding_decimals)))
        if fel_taxes['PETROLEO'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='PETROLEO', TotalMontoImpuesto=str(round(fel_taxes['PETROLEO'], rounding_decimals)))
        if fel_taxes['TURISMO HOSPEDAJE'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO HOSPEDAJE', TotalMontoImpuesto=str(round(fel_taxes['TURISMO HOSPEDAJE'], rounding_decimals)))
        if fel_taxes['TURISMO PASAJES'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TURISMO PASAJES', TotalMontoImpuesto=str(round(fel_taxes['TURISMO PASAJES'], rounding_decimals)))
        if fel_taxes['TIMBRE DE PRENSA'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TIMBRE DE PRENSA', TotalMontoImpuesto=str(round(fel_taxes['TIMBRE DE PRENSA'], rounding_decimals)))
        if fel_taxes['BOMBEROS'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='BOMBEROS', TotalMontoImpuesto=str(round(fel_taxes['BOMBEROS'], rounding_decimals)))
        if fel_taxes['TASA MUNICIPAL'] > 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto='TASA MUNICIPAL', TotalMontoImpuesto=str(round(fel_taxes['TASA MUNICIPAL'], rounding_decimals)))
        if fel_taxes['IVA'] == 0:
            xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto="0.00")
        if make_conversion:
            if conversion_rate > 1.0:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva * conversion_rate
                tax_withold_amount = self.tax_withold_amount * conversion_rate
            else:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva / conversion_rate
                tax_withold_amount = self.tax_withold_amount / conversion_rate
        else:
            grand_total = self.amount_total
            tax_withholding_amount_iva = self.tax_withholding_amount_iva
            tax_withold_amount = self.tax_withold_amount
        if self.fel_gt_invoice_type == 'especial':
            ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total + price_tax_total, 2))
        else:
            ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total, 2))

        # Complementos
        debit_note_name = "Nota de debito " + str(self.source_debit_note_id.dte_number)
        dte_date = self.source_debit_note_id.dte_date
        if not dte_date:
            raise UserError('La factura no posee una fecha de DTE, si desea realizar cambios sobre la misma desactive la facturación electrónica en el diario asociado a la misma.')
        # dte_date = datetime.strptime(dte_date, '%Y-%m-%d %H:%M:%S')
        racion_de_6h = timedelta(hours=6)
        dte_date = dte_date - racion_de_6h
        date_format = "%Y-%m-%d"
        dte_date = dte_date.strftime(date_format)
        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento=self.name, URIComplemento='http://www.sat.gob.gt/fel/notas.xsd', attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        ET.register_namespace('cno', complemento_xmlns)
        if self.old_tax_regime is False:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, MotivoAjuste=debit_note_name, NumeroAutorizacionDocumentoOrigen=str(self.source_debit_note_id.uuid), NumeroDocumentoOrigen=str(self.source_debit_note_id.dte_number), SerieDocumentoOrigen=str(self.source_debit_note_id.serie), Version="0.1")
        if self.old_tax_regime is True:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, RegimenAntiguo="Antiguo", MotivoAjuste=debit_note_name, NumeroAutorizacionDocumentoOrigen=str(self.source_debit_note_id.uuid), NumeroDocumentoOrigen=str(self.source_debit_note_id.dte_number), SerieDocumentoOrigen=str(self.source_debit_note_id.serie), Version="0.1")
        
        # Adenda
        #xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
            xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
            if self.company_id.fel_addendum_journal_sequence:
                ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
            if make_conversion and self.company_id.fel_addendum_currency_rate:
                # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                if conversion_rate > 1.0:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                else:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)
        date_due = self.invoice_date_due
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        #ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due
        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        search_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, search_replace)
        xml_content = xml_content.encode('utf_8')

        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if self.id:
            self.source_debit_note_id.write({'debit_note_id': self.id})

        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)
        return xml_content
    # FACTURA ESPECIAL
    def set_data_for_invoice_special(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0 GT_Complemento_Fac_Especial-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.invoice_date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider

        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        currency_code = "GTQ"
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name

        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code
        
        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department
        
        if fel_certifier == 'g4s':
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        else:
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        ET.register_namespace('cfe', cno)
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        ##if last_5_days > self.invoice_date:
        ##    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
            
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="FESP")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=company_vat, NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            # vat = "CF"
            has_cui = False
            if self.partner_id.dpi_number:
                vat = self.partner_id.dpi_number
                has_cui = True
            else:
                vat = company_vat
        if has_cui:
            xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name, TipoEspecial="CUI")
        else:
            xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)

        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        invoice_counter = 0
        price_tax_total = 0
        items_grand_total = 0
        grand_total = 0
        total_iva = 0
        fel_gran_total = 0
        # LineasFactura
        for line in invoice_line:
            if not line.display_type in ('line_section', 'line_note'):
                invoice_counter += 1
                p_type = 0
                BienOServicio = "B"
                if line.product_id.type == 'service':
                    p_type = 1
                    BienOServicio = "S"
                for tax in line.tax_ids:
                    if tax.price_include:
                        tax_in_ex = 0

                # Item
                xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))

                # ------------------------------
                # --- CHECK INOVICE CURRENCY ---
                # ------------------------------

                line_price_unit = line.price_unit
                line_price = line.quantity * line.price_unit
                line_price_total = line.price_total
                line_price_subtotal = line.price_subtotal
                # price_tax = line_price_total - line_price_subtotal
                price_tax = line.price_subtotal * 0.12
                total_iva += price_tax
                price_iva_total_line = line.price_subtotal + price_tax
                fel_gran_total += price_iva_total_line
                tax_amount = 0
                if make_conversion:
                    set_conversion_data = {
                        "line": line,
                        "conversion_rate": conversion_rate
                    }
                    get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                    line_price_unit = get_conversion_data['line_price_unit']
                    line_price = get_conversion_data['line_price']
                    line_price_total = get_conversion_data['line_price_total']
                    line_price_subtotal = get_conversion_data['line_price_subtotal']
                    price_tax = get_conversion_data['price_tax']
                    grand_total += line_price_total
                else:
                    grand_total += line_price_total

                line_price = round(line_price, 2)
                ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
                ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                
                line_description_source = self.company_id.fel_invoice_line_name
                line_description = line.product_id.name
                if line_description_source == 'description':
                    line_description = line.name
                
                if line_code_divider:
                    if line.product_id.default_code:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line_description
                    else:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line_description
                else:
                    note_description = self.get_description_notes(line.id, order_invoice_line)
                    ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " " + note_description
                
                ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
                ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line_price_unit))/100, 2))
                items_grand_total += line_price

                if line.tax_ids:
                    tax = "IVA"
                else:
                    raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

                xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")

                ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax
                ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line_price_subtotal, 2))
                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(price_tax, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(price_iva_total_line, 2))
                price_tax_total = price_tax_total + price_tax

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto=str(round(total_iva, 2)))

        # ISR CALCULATIONS
        # TODO: Replicate calculation in invoice calculate amount
        fel_gt_withhold_amount = self.fel_gt_withhold_amount
        amount_untaxed = self.amount_untaxed
        invoice_base_amount = round(amount_untaxed - fel_gt_withhold_amount, 2)
        if make_conversion:
            invoice_base_amount = grand_total - price_tax
            if conversion_rate > 1.0:
                tax_withold_amount = self.tax_withold_amount * conversion_rate
                fel_gt_withhold_amount = fel_gt_withhold_amount * conversion_rate
                amount_untaxed = amount_untaxed * conversion_rate
            else:
                tax_withold_amount = self.tax_withold_amount / conversion_rate
                fel_gt_withhold_amount = fel_gt_withhold_amount / conversion_rate
                amount_untaxed = amount_untaxed / conversion_rate
        else:
            tax_withholding_amount_iva = self.tax_withholding_amount_iva
            tax_withold_amount = self.tax_withold_amount

        isr_withold = 0
        isr_withold = invoice_base_amount * 0.05
        
        isr_withold = round(isr_withold, 2)
        fel_gt_withhold_amount = isr_withold

        if 'tax_withold_amount' in self.env['account.move']._fields:
            if self.tax_withold_amount > 0:
                grand_total = items_grand_total
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(fel_gran_total, 2))

        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="FacturaEspecial", URIComplemento="FESP", attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        xml_retenciones = ET.SubElement(xml_complemento, "{" + cno + "}RetencionesFacturaEspecial", Version="1")
        ET.SubElement(xml_retenciones, "{" + cno + "}RetencionISR").text = str(fel_gt_withhold_amount)
        ET.SubElement(xml_retenciones, "{" + cno + "}RetencionIVA").text = str(round(total_iva, 2))
        if make_conversion:
            ET.SubElement(xml_retenciones, "{" + cno + "}TotalMenosRetenciones").text = str(round(invoice_base_amount - fel_gt_withhold_amount, 2))
        else:
            ET.SubElement(xml_retenciones, "{" + cno + "}TotalMenosRetenciones").text = str(round(amount_untaxed - fel_gt_withhold_amount, 2))

        if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
            # Adenda
            xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
            if self.company_id.fel_addendum_journal_sequence:
                ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
            if make_conversion and self.company_id.fel_addendum_currency_rate:
                # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                if conversion_rate > 1.0:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                else:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)
        date_due = self.invoice_date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        # ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        search_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, search_replace)
        xml_content = xml_content.encode('utf_8')

        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    # NOTA DE ABONO
    def set_data_for_invoice_abono(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        version = "0.4"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.invoice_date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider

        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        currency_code = "GTQ"
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name
        
        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code
        
        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department

        if fel_certifier == 'g4s':
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        else:
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")
        # fecha_emision = dt.datetime.now(gettz("America/Guatemala")).isoformat()   #dt.datetime.now().isoformat()
        
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        #if last_5_days > self.invoice_date:
        #    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="NABN")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=company_vat, NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            if self.fel_gt_invoice_type == 'especial':
                vat = company_vat
            else:
                vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        cnt = 0
        price_tax_total = 0
        grand_total = 0
        # LineasFactura
        for line in invoice_line:
            if not line.display_type in ('line_section', 'line_note'):
                cnt += 1
                p_type = 0
                BienOServicio = "B"
                if line.product_id.type == 'service':
                    p_type = 1
                    BienOServicio = "S"
                for tax in line.tax_ids:
                    if tax.price_include:
                        tax_in_ex = 0

                # ------------------------------
                # --- CHECK INOVICE CURRENCY ---
                # ------------------------------

                line_price_unit = line.price_unit
                line_price = line.quantity * line.price_unit
                line_price_total = line.price_total
                line_price_subtotal = line.price_subtotal
                price_tax = line_price_total - line_price_subtotal
                tax_amount = 0
                if make_conversion:
                    set_conversion_data = {
                        "line": line,
                        "conversion_rate": conversion_rate
                    }
                    get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                    line_price_unit = get_conversion_data['line_price_unit']
                    line_price = get_conversion_data['line_price']
                    line_price_total = get_conversion_data['line_price_total']
                    line_price_subtotal = get_conversion_data['line_price_subtotal']
                    price_tax = get_conversion_data['price_tax']
                    grand_total += line_price_total

                # Item
                xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(cnt))
                line_price = round(line_price, 2)
                ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
                ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                
                line_description_source = self.company_id.fel_invoice_line_name
                line_description = line.product_id.name
                if line_description_source == 'description':
                    line_description = line.name
                
                if line_code_divider:
                    if line.product_id.default_code:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line_description
                    else:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line_description
                else:
                    note_description = self.get_description_notes(line.id, order_invoice_line)
                    ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " " + note_description
                
                ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
                ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))

        if make_conversion:
            if conversion_rate > 1.0:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva * conversion_rate
                tax_withold_amount = self.tax_withold_amount * conversion_rate
            else:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva / conversion_rate
                tax_withold_amount = self.tax_withold_amount / conversion_rate
        else:
            grand_total = self.amount_total
            tax_withholding_amount_iva = self.tax_withholding_amount_iva
            tax_withold_amount = self.tax_withold_amount
        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total, 2))

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
            if self.company_id.fel_addendum_journal_sequence:
                ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
            if make_conversion and self.company_id.fel_addendum_currency_rate:
                # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                if conversion_rate > 1.0:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                else:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)
        date_due = self.invoice_date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        search_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, search_replace)
        xml_content = xml_content.encode('utf_8')

        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)

        return xml_content
    
    # ANULACIÓN DE FACTURA
    def set_data_for_invoice_cancel(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.1.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        if fel_certifier == 'g4s':
            schemaLocation = schemaLocation = "http://www.sat.gob.gt/dte/fel/0.1.0 GT_AnulacionDocumento-0.1.0.xsd"
            ds = "http://www.w3.org/2000/09/xmldsig#"
        else:
            schemaLocation = "http://www.sat.gob.gt/dte/fel/0.1.0"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.uuid is False:
            raise UserError(RAISE_VALIDATION_UUID_CANCEL)

        xml_root = ET.Element("{" + xmlns + "}GTAnulacionDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}AnulacionDTE", ID="DatosCertificados")
        date_invoice = self.invoice_date or datetime.now()

        # if self.dte_date is not False:
            # date_invoice = datetime.strptime(date_invoice, '%Y-%m-%d %H:%M:%S')

        racion_de_6h = timedelta(hours=6)
        date_invoice = date_invoice - racion_de_6h
        #invoice_date_format = "%Y-%m-%dT%H:%M:%S.%f"
        #date_invoice = date_invoice.strftime(invoice_date_format)[:-3]
        if fel_certifier == 'g4s':
            invoice_date_format = "%Y-%m-%dT%H:%M:%S"
            date_invoice = date_invoice.strftime(invoice_date_format)
        else:
            invoice_date_format = "%Y-%m-%dT%H:%M:%S.%f"
            date_invoice = date_invoice.strftime(invoice_date_format)[:-3]
        
        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            if self.fel_gt_invoice_type == 'especial':
                has_cui = False
                if self.partner_id.dpi_number:
                    vat = self.partner_id.dpi_number
                    has_cui = True
                else:
                    vat = company_vat
            else:
                vat = "CF"
        
        if fel_certifier == 'g4s':
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S')
            fecha_anulacion = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S')
        else:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
            fecha_anulacion = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        #if last_5_days > self.invoice_date:
        #    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        
        dge = ET.SubElement(xml_dte, "{" + xmlns + "}DatosGenerales", FechaEmisionDocumentoAnular=fecha_emision, FechaHoraAnulacion=fecha_anulacion, ID="DatosAnulacion", IDReceptor=vat, MotivoAnulacion="Anulacion", NITEmisor=company_vat, NumeroDocumentoAAnular=str(self.uuid))
        
        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        attribute_replace = "dte"
        ds_search_string = "xsi:ds"
        ds_replace_string = "xmlns:ds"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, attribute_replace)
        xml_content = xml_content.replace(ds_search_string, ds_replace_string)
        xml_content = xml_content.encode('utf_8')
        date_due = ""
        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)
        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)
        return xml_content
    
    # NOTA DE CRÉDITO
    def set_data_for_invoice_credit(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0 GT_Complemento_Referencia_Nota-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        complemento_xmlns = "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.uuid is False:
            raise UserError(RAISE_VALIDATION_UUID_CANCEL)

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()

        line_code_divider = self.company_id.fel_default_code_divider
        
        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        currency_code = "GTQ"
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name

        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code
        
        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department
        
        
        xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")
        # fecha_emision = dt.datetime.now(gettz("America/Guatemala")).isoformat()   #dt.datetime.now().isoformat()
        #fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        #if last_5_days > self.invoice_date:
        #    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        
        
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="NCRE")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=company_vat, NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            if self.fel_gt_invoice_type == 'especial':
                vat = company_vat
            else:
                vat = "CF"

        
        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"
        
        # Frases

        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        company_codes = self.get_company_code() 
        for company_type in company_codes:
            
            if company_type == "1" and company_codes[company_type] == "3" and self.company_id.fel_resolution_number and self.company_id.fel_resolution_date:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=company_type, CodigoEscenario=company_codes[company_type], NumeroResolucion=self.company_id.fel_resolution_number, FechaResolucion=self.company_id.fel_resolution_date)
            else:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=company_type, CodigoEscenario=company_codes[company_type])

        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        cnt = 0
        price_tax_total = 0
        grand_total = 0
        
        fel_taxes = {
            "IVA": 0,
            "PETROLEO": 0,
            "TURISMO HOSPEDAJE": 0,
            "TURISMO PASAJES": 0,
            "TIMBRE DE PRENSA": 0,
            "BOMBEROS": 0,
            "TASA MUNICIPAL": 0,
        }
        
        # LineasFactura
        for line in invoice_line:
            if not line.display_type in ('line_section', 'line_note'):
                cnt += 1
                p_type = 0
                BienOServicio = "B"
                if line.product_id.type == 'service':
                    p_type = 1
                    BienOServicio = "S"
                for tax in line.tax_ids:
                    if tax.price_include:
                        tax_in_ex = 0

                # ------------------------------
                # --- CHECK INOVICE CURRENCY ---
                # ------------------------------

                line_price_unit = line.price_unit
                line_price = line.quantity * line.price_unit
                line_price_total = line.price_total
                line_price_subtotal = line.price_subtotal
                price_tax = line_price_total - line_price_subtotal
                tax_amount = 0
                if make_conversion:
                    set_conversion_data = {
                        "line": line,
                        "conversion_rate": conversion_rate
                    }
                    get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                    line_price_unit = get_conversion_data['line_price_unit']
                    line_price = get_conversion_data['line_price']
                    line_price_total = get_conversion_data['line_price_total']
                    line_price_subtotal = get_conversion_data['line_price_subtotal']
                    price_tax = get_conversion_data['price_tax']
                    grand_total += line_price_total

                # Item
                xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(cnt))

                line_price = round(line_price, 2)

                ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(round(line.quantity,4))
                ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                
                line_description_source = self.company_id.fel_invoice_line_name
                line_description = line.product_id.name
                if line_description_source == 'description':
                    line_description = line.name
                
                if line_code_divider:
                    if line.product_id.default_code:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line_description
                    else:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line_description
                else:
                    note_description = self.get_description_notes(line.id, order_invoice_line)
                    ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " " + note_description
                
                
                ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
                ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line_price_unit))/100, 2))

                if line.tax_ids:
                    tax = "IVA"
                else:
                    if not self.company_id.fel_iva_company_exception:
                        raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

                if line.tax_ids:
                    xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                    for tax in line.tax_ids:
                        tax_name = tax.fel_tax
                        xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
                        
                        if (line.discount == 0):
                            base = line.price_unit * line.quantity
                        else:
                            base = line.price_subtotal
                        if tax_name == "IVA":
                            if (line.discount == 0):
                                price_tax = tax._compute_amount(base, line.price_unit, line.quantity, line.product_id, self.partner_id)
                            else:
                                price_tax = base * tax.amount / 100
                        else:
                            price_tax = tax._compute_amount(line.price_subtotal, line.price_unit, line.quantity, line.product_id, self.partner_id)

                        ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax_name
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line_price_subtotal, 2))
                        price_tax = round(price_tax, 3)
                        split_num = str(price_tax).split('.')
                        if int(split_num[1]) > 0:
                            decimal = str(split_num[1])
                            if len(decimal) > 2:
                                if int(decimal[2]) == 5:
                                    price_tax += 0.001
                                    
                        ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(price_tax, 2))
                        price_tax_total = price_tax_total + price_tax
                
                ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))
                        

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto=str(round(price_tax_total, 2)))
        if make_conversion:
            if conversion_rate > 1.0:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva * conversion_rate
                tax_withold_amount = self.tax_withold_amount * conversion_rate
            else:
                tax_withholding_amount_iva = self.tax_withholding_amount_iva / conversion_rate
                tax_withold_amount = self.tax_withold_amount / conversion_rate
        else:
            grand_total = self.amount_total
            tax_withholding_amount_iva = self.tax_withholding_amount_iva
            tax_withold_amount = self.tax_withold_amount
        if self.fel_gt_invoice_type == 'especial':
            ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total + price_tax_total, 2))
        else:
            ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total, 2))

        # Complementos
        dte_date = self.dte_date
        if not dte_date:
            raise UserError('La factura no posee una fecha de DTE, si desea realizar cambios sobre la misma desactive la facturación electrónica en el diario asociado a la misma.')
        # dte_date = datetime.strptime(dte_date, '%Y-%m-%d %H:%M:%S')
        racion_de_6h = timedelta(hours=6)
        dte_date = dte_date - racion_de_6h
        date_format = "%Y-%m-%d"
        dte_date = dte_date.strftime(date_format)
        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento=self.name, URIComplemento='http://www.sat.gob.gt/fel/notas.xsd', attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        ET.register_namespace('cno', complemento_xmlns)
        if self.old_tax_regime is False:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, MotivoAjuste=self.name, NumeroAutorizacionDocumentoOrigen=str(self.uuid), NumeroDocumentoOrigen=str(self.dte_number), SerieDocumentoOrigen=str(self.serie), Version="0.1")
        if self.old_tax_regime is True:
            ET.SubElement(xml_complemento, "{" + complemento_xmlns + "}ReferenciasNota", FechaEmisionDocumentoOrigen=dte_date, RegimenAntiguo="Antiguo", MotivoAjuste=self.name, NumeroAutorizacionDocumentoOrigen=str(self.uuid), NumeroDocumentoOrigen=str(self.dte_number), SerieDocumentoOrigen=str(self.serie), Version="0.1")

        date_due = self.invoice_date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        if fel_certifier == 'infile':
            # Adenda
            xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
            if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
                if self.company_id.fel_addendum_journal_sequence:
                    ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
                if make_conversion and self.company_id.fel_addendum_currency_rate:
                    # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                    if conversion_rate > 1.0:
                        ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                    else:
                        ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)
            
            ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        search_replace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, search_replace)
        xml_content = xml_content.encode('utf_8')

        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    def set_data_for_invoice_cambiaria_exp(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0 GT_Complemento_Cambiaria-0.1.0.xsd"
        #schemaLocation_complementos_exportaciones = "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0 GT_Complemento_Cambiaria-0.1.0.xsd"
        schemaLocation_complementos_exportaciones = "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0 GT_Complemento_Exportaciones-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:

            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        #if self.partner_id.buyer_code is False:
        #    raise UserError(RAISE_VALIDATION_PARTNER_BUYER_CODE)

        #if self.company_id.consignatary_code is False:
        #    raise UserError(RAISE_VALIDATION_COMPANY_CONSIGNATARY_CODE)

        #if self.company_id.exporter_code is False:
        #    raise UserError(RAISE_VALIDATION_COMPANY_EXPORTER_CODE)

        if self.partner_id.street is False:
            raise UserError(RAISE_VALIDATION_PARTNER_ADDRESS)

        #cno = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0"
        cno = "http://www.sat.gob.gt/fel/exportacion.xsd"
        cna = "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0"

        if fel_certifier == 'g4s':
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        else:
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        ET.register_namespace('cex', cna)
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider

        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        currency_code = "GTQ"
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name
        
        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code

        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department
        
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        #if last_5_days > self.invoice_date:
        #    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code, Exp="SI", FechaHoraEmision=fecha_emision, Tipo="FACT")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=company_vat, NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")    
    
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text =  self.partner_id.country_id.code or "GT"

        # Frases
        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        company_codes = self.get_company_code() 
        for company_type in company_codes:
            if self.company_id.fel_company_type == "1" and self.company_id.fel_company_code == "3" and self.company_id.fel_resolution_number and self.company_id.fel_resolution_date:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code, NumeroResolucion=self.company_id.fel_resolution_number, FechaResolucion=self.company_id.fel_resolution_date)
            else:
                ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=company_type, CodigoEscenario=company_codes[company_type])
        #ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase="2", CodigoEscenario="1")
        ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase="4", CodigoEscenario="1")

        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        invoice_counter = 0
        price_tax_total = 0
        grand_total = 0
        # LineasFactura
        for line in invoice_line:
            if not line.display_type in ('line_section', 'line_note'):
                invoice_counter += 1
                p_type = 0
                BienOServicio = "B"
                if line.product_id.type == 'service':
                    p_type = 1
                    BienOServicio = "S"
                for tax in line.tax_ids:
                    if tax.price_include:
                        tax_in_ex = 0

                # ------------------------------
                # --- CHECK INOVICE CURRENCY ---
                # ------------------------------

                line_price_unit = line.price_unit
                line_price = line.quantity * line.price_unit
                line_price_total = line.price_total
                line_price_subtotal = line.price_subtotal
                price_tax = line_price_total - line_price_subtotal
                tax_amount = 0
                if make_conversion:
                    set_conversion_data = {
                        "line": line,
                        "conversion_rate": conversion_rate
                    }
                    get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                    line_price_unit = get_conversion_data['line_price_unit']
                    line_price = get_conversion_data['line_price']
                    line_price_total = get_conversion_data['line_price_total']
                    line_price_subtotal = get_conversion_data['line_price_subtotal']
                    price_tax = get_conversion_data['price_tax']
                    grand_total += line_price_total

                # Item
                xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))
                line_price = round(line_price, 2)
                ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
                ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                
                line_description_source = self.company_id.fel_invoice_line_name
                line_description = line.product_id.name
                if line_description_source == 'description':
                    line_description = line.name
                
                if line_code_divider:
                    if line.product_id.default_code:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line_description
                    else:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line_description
                else:
                    note_description = self.get_description_notes(line.id, order_invoice_line)
                    ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " " + note_description
                
                ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
                ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line_price_unit))/100, 2))
                tax = "IVA"
                if line.tax_ids:
                    tax = "IVA"
                #else:
                #    raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

                xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")
                ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax
                ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "2"
                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line_price, 2))
                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = "0"
                #ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto")
                #ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable")
                #ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable")
                #ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto")
                ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))
                #ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(0)
                price_tax_total = price_tax_total + price_tax

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto="0")
        if not make_conversion:
            grand_total = self.amount_total

        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total, 2))

        date_due = self.invoice_date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        formato2 = "%Y-%m-%d"
        date_due = date_due.strftime(formato2)

        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        #xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="AbonosFacturaCambiaria", URIComplemento=cno, attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="Exportacion", URIComplemento=cno)
        #xml_retenciones = ET.SubElement(xml_complemento, "{" + cno + "}AbonosFacturaCambiaria", Version="1")
        #xml_abono = ET.SubElement(xml_retenciones, "{" + cno + "}Abono")
        #ET.SubElement(xml_abono, "{" + cno + "}NumeroAbono").text = "1"
        #ET.SubElement(xml_abono, "{" + cno + "}FechaVencimiento").text = date_due
        #ET.SubElement(xml_abono, "{" + cno + "}MontoAbono").text = str(round(grand_total, 2))

        #xml_complemento_secondary = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="AbonosFacturaCambiariaExp", URIComplemento=cna, attrib={"{" + xsi + "}schemaLocation":    schemaLocation_complementos})
        #xml_retenciones_secondary = ET.SubElement(xml_complemento_secondary, "{" + cna + "}Exportacion", Version="1", attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos_exportaciones})
        xml_retenciones_secondary = ET.SubElement(xml_complemento, "{" + cna + "}Exportacion", Version="1", attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos_exportaciones})
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}NombreConsignatarioODestinatario").text = self.partner_id.consignatary_name
        ET.SubElement(xml_retenciones_secondary, "{" + cna + "}DireccionConsignatarioODestinatario").text = self.partner_id.consignatary_address
        #ET.SubElement(xml_retenciones_secondary, "{" + cna + "}DireccionConsignatarioODestinatario").text = self.company_id.street
        #ET.SubElement(xml_retenciones_secondary, "{" + cna + "}CodigoConsignatarioODestinatario").text = self.company_id.consignatary_code
        if self.partner_id.consignatary_code:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}CodigoConsignatarioODestinatario").text = self.partner_id.consignatary_code
        if self.partner_id.name:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}NombreComprador").text = self.partner_id.name
        if self.partner_id.buyer_address:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}DireccionComprador").text = self.partner_id.buyer_address
        if self.partner_id.buyer_code:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}CodigoComprador").text = self.partner_id.buyer_code
        if self.partner_id.ref:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}OtraReferencia").text = self.partner_id.ref
        if self.invoice_incoterm_id.code:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}INCOTERM").text = self.invoice_incoterm_id.code
        if self.partner_id.exporter_name:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}NombreExportador").text = self.partner_id.exporter_name
        if self.partner_id.exporter_code:
            ET.SubElement(xml_retenciones_secondary, "{" + cna + "}CodigoExportador").text = self.partner_id.exporter_code

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
            if self.company_id.fel_addendum_journal_sequence:
                ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
            if make_conversion and self.company_id.fel_addendum_currency_rate:
                # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                if conversion_rate > 1.0:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                else:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)
        date_due = self.invoice_date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        string_remplace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')

        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)
        
        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)
        
        return xml_content

    def set_data_for_invoice_cambiaria(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        schemaLocation_complementos = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0 GT_Complemento_Cambiaria-0.1.0.xsd"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        cno = "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0"

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.invoice_date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider

        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        currency_code = "GTQ"
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name

        
        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code
        
        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department
        
        if fel_certifier == 'g4s':
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        else:
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        ET.register_namespace('cfc', cno)
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")
        
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        #if last_5_days > self.invoice_date:
        #    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="FCAM")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=company_vat, NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        # Frases
        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        if self.company_id.fel_company_type == "1" and self.company_id.fel_company_code == "3" and self.company_id.fel_resolution_number and self.company_id.fel_resolution_date:
            ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code, NumeroResolucion=self.company_id.fel_resolution_number, FechaResolucion=self.company_id.fel_resolution_date)
        else:
            ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code)

        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)

        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        tax_in_ex = 1
        invoice_counter = 0
        price_tax_total = 0
        grand_total = 0
        # LineasFactura
        for line in invoice_line:
            if not line.display_type in ('line_section', 'line_note'):
                invoice_counter += 1
                p_type = 0
                BienOServicio = "B"
                if line.product_id.type == 'service':
                    p_type = 1
                    BienOServicio = "S"
                for tax in line.tax_ids:
                    if tax.price_include:
                        tax_in_ex = 0

                # ------------------------------
                # --- CHECK INOVICE CURRENCY ---
                # ------------------------------

                line_price_unit = line.price_unit
                line_price = line.quantity * line.price_unit
                line_price_total = line.price_total
                line_price_subtotal = line.price_subtotal
                price_tax = line_price_total - line_price_subtotal
                tax_amount = 0
                if make_conversion:
                    set_conversion_data = {
                        "line": line,
                        "conversion_rate": conversion_rate
                    }
                    get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                    line_price_unit = get_conversion_data['line_price_unit']
                    line_price = get_conversion_data['line_price']
                    line_price_total = get_conversion_data['line_price_total']
                    line_price_subtotal = get_conversion_data['line_price_subtotal']
                    price_tax = get_conversion_data['price_tax']
                    grand_total += line_price_total

                # Item
                grand_total += line_price_total
                xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))

                line_price = round(line_price, 2)
                ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
                ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                
                line_description_source = self.company_id.fel_invoice_line_name
                line_description = line.product_id.name
                if line_description_source == 'description':
                    line_description = line.name
                
                if line_code_divider:
                    if line.product_id.default_code:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line.product_id.name
                    else:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line.product_id.name
                else:
                    note_description = self.get_description_notes(line.id, order_invoice_line)
                    ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " " + note_description
                
                ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
                ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line_price_unit))/100, 2))

                if line.tax_ids:
                    tax = "IVA"
                #Se cambió debido a un problema que dió para Analytecs 08/11/2021
                #else:
                #    raise UserError(_("Las líneas de Factura deben de llevar impuesto (IVA)."))

                xml_impuestos = ET.SubElement(xml_item, "{" + xmlns + "}Impuestos")
                xml_impuesto = ET.SubElement(xml_impuestos, "{" + xmlns + "}Impuesto")

                ET.SubElement(xml_impuesto, "{" + xmlns + "}NombreCorto").text = tax
                ET.SubElement(xml_impuesto, "{" + xmlns + "}CodigoUnidadGravable").text = "1"
                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoGravable").text = str(round(line_price_subtotal, 2))
                ET.SubElement(xml_impuesto, "{" + xmlns + "}MontoImpuesto").text = str(round(price_tax, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))
                price_tax_total = price_tax_total + price_tax

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        xml_total_impuestos = ET.SubElement(xml_totales, "{" + xmlns + "}TotalImpuestos")
        xml_total_impuesto = ET.SubElement(xml_total_impuestos, "{" + xmlns + "}TotalImpuesto", NombreCorto="IVA", TotalMontoImpuesto=str(round(price_tax_total, 2)))
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total, 2))

        # Complementos

        date_due = self.invoice_date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        formato2 = "%Y-%m-%d"
        date_due = date_due.strftime(formato2)
        xml_complementos = ET.SubElement(xml_data_emision, "{" + xmlns + "}Complementos")
        xml_complemento = ET.SubElement(xml_complementos, "{" + xmlns + "}Complemento", IDComplemento=str(randint(1, 99999)), NombreComplemento="AbonosFacturaCambiaria", URIComplemento="FCAM", attrib={"{" + xsi + "}schemaLocation": schemaLocation_complementos})
        xml_retenciones = ET.SubElement(xml_complemento, "{" + cno + "}AbonosFacturaCambiaria", Version="1")
        xml_abono = ET.SubElement(xml_retenciones, "{" + cno + "}Abono")
        ET.SubElement(xml_abono, "{" + cno + "}NumeroAbono").text = "1"
        ET.SubElement(xml_abono, "{" + cno + "}FechaVencimiento").text = date_due
        ET.SubElement(xml_abono, "{" + cno + "}MontoAbono").text = str(round(self.amount_total, 2))

        if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
            # Adenda
            xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
            if self.company_id.fel_addendum_journal_sequence:
                ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
            if make_conversion and self.company_id.fel_addendum_currency_rate:
                # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                if conversion_rate > 1.0:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                else:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)
        date_due = self.invoice_date_due
        # date_due = datetime.strptime(date_due, '%Y-%m-%d')
        date_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_format)
        # ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method='xml')
        search_string = "ns0"
        string_remplace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')

        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    def set_data_for_invoice_recibo(self, fel_certifier):
        xmlns = "http://www.sat.gob.gt/dte/fel/0.2.0"
        xsi = "http://www.w3.org/2001/XMLSchema-instance"
        schemaLocation = "http://www.sat.gob.gt/dte/fel/0.2.0"
        version = "0.1"
        ns = "{xsi}"
        DTE = "dte"
        vat = ""

        if self.company_id.company_registry is False:
            raise UserError(RAISE_VALIDATION_COMPANY_REGISTRY)

        if self.company_id.email is False:
            raise UserError(RAISE_VALIDATION_COMPANY_EMAIL)

        if self.company_id.vat is False:
            raise UserError(RAISE_VALIDATION_COMPANY_VAT)

        if self.company_id.street is False:
            raise UserError(RAISE_VALIDATION_COMPANY_STREET)

        if self.company_id.fel_company_code is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_CODE)

        if self.company_id.fel_company_type is False:
            raise UserError(RAISE_VALIDATION_COMPANY_FEL_COMPANY_TYPE)

        if self.invoice_date_due is False:
            raise UserError(RAISE_VALIDATION_INVOICE_DATE_DUE)

        if self.partner_id.name.strip() == "":
            raise UserError(RAISE_VALIDATION_INVOICE_PARTNER_NAME)

        company_vat = self.company_id.vat
        company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
        company_vat = company_vat.upper()
        
        line_code_divider = self.company_id.fel_default_code_divider

        make_conversion = False
        conversion_rate = 1
        if self.company_id.fel_invoice_currency and not self.company_id.fel_currency_from_invoice:
            if self.currency_id != self.company_id.fel_invoice_currency:
                if not self.invoice_date:
                    raise ValidationError('Debe seleccionar la fecha de la factura para asignar la tasa de conversión correcta')
                make_conversion = True
                conversion_rate = self.currency_id.with_context(date=self.invoice_date).rate

        currency_code = "GTQ"
        if self.company_id.fel_currency_from_invoice:
            currency_code = self.currency_id.name
        else:
            currency_code = self.company_id.fel_invoice_currency.name
        
        establishment_code = self.company_id.fel_establishment_code
        if self.journal_id.fel_establishment_code:
            establishment_code = self.journal_id.fel_establishment_code

        commercial_name = self.company_id.name
        if self.journal_id.fel_commercial_name:
            commercial_name = self.journal_id.fel_commercial_name
        
        fel_address = self.get_company_address()
        if self.journal_id.fel_address:
            fel_address = self.journal_id.fel_address
        
        fel_zip_code = self.company_id.zip
        if self.journal_id.fel_zip_code:
            fel_zip_code = self.journal_id.fel_zip_code
        
        fel_township = self.company_id.city
        if self.journal_id.fel_township:
            fel_township = self.journal_id.fel_township
        
        fel_department = self.company_id.state_id.name
        if self.journal_id.fel_department:
            fel_department = self.journal_id.fel_department
        
        if fel_certifier == 'g4s':
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1")
        else:
            xml_root = ET.Element("{" + xmlns + "}GTDocumento", Version="0.1", attrib={"{" + xsi + "}schemaLocation": schemaLocation})
        xml_doc = ET.SubElement(xml_root, "{" + xmlns + "}SAT", ClaseDocumento="dte")
        xml_dte = ET.SubElement(xml_doc, "{" + xmlns + "}DTE", ID="DatosCertificados")
        xml_data_emision = ET.SubElement(xml_dte, "{" + xmlns + "}DatosEmision", ID="DatosEmision")

        
        fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        last_5_days = date.today() - timedelta(5)
        #if last_5_days > self.invoice_date:
        #    raise UserError('La fecha de la factura excede el límite de 5 dias hacia atrás autorizados para la emisión de documentos en el regimen FEL.')
        if not self.invoice_date:
            fecha_emision = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        else:
            fecha_emision = self.invoice_date.__format__('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        
        xml_datos_generales = ET.SubElement(xml_data_emision, "{" + xmlns + "}DatosGenerales", CodigoMoneda=currency_code,  FechaHoraEmision=fecha_emision, Tipo="RECI")
        xml_emisor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Emisor", AfiliacionIVA="GEN", CodigoEstablecimiento=establishment_code, CorreoEmisor=self.company_id.email, NITEmisor=company_vat, NombreComercial=commercial_name, NombreEmisor=self.company_id.company_registry)
        xml_emisor_address = ET.SubElement(xml_emisor, "{" + xmlns + "}DireccionEmisor")
        
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Direccion").text = fel_address or "Ciudad"  # "4 Avenida 19-26 zona 10"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}CodigoPostal").text = fel_zip_code or "01009"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Municipio").text = fel_township or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Departamento").text = fel_department or "Guatemala"
        ET.SubElement(xml_emisor_address, "{" + xmlns + "}Pais").text = self.company_id.country_id.code or "GT"

        if self.partner_id.vat:
            vat = self.partner_id.vat
            vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', vat)
            vat = vat.upper()
        else:
            vat = "CF"

        xml_receptor = ET.SubElement(xml_data_emision, "{" + xmlns + "}Receptor", CorreoReceptor=self.partner_id.email or "", IDReceptor=vat, NombreReceptor=self.partner_id.name)
        xml_receptor_address = ET.SubElement(xml_receptor, "{" + xmlns + "}DireccionReceptor")
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Direccion").text = self.partner_id.street or "Ciudad"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}CodigoPostal").text = self.partner_id.zip or "01009"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Municipio").text = self.partner_id.city or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Departamento").text = self.partner_id.state_id.name or "Guatemala"
        ET.SubElement(xml_receptor_address, "{" + xmlns + "}Pais").text = self.partner_id.country_id.code or "GT"

        xml_frases = ET.SubElement(xml_data_emision, "{" + xmlns + "}Frases")
        tipo_frase_recibo = "4"
        codigo_escenario_recibo = "8"
        if self.company_id.fel_company_type == "1" and self.company_id.fel_company_code == "3" and self.company_id.fel_resolution_number and self.company_id.fel_resolution_date:
            ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code, NumeroResolucion=self.company_id.fel_resolution_number, FechaResolucion=self.company_id.fel_resolution_date)
        else:
            ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=tipo_frase_recibo, CodigoEscenario=codigo_escenario_recibo)
        # TODO: Buscar manera de poder poner los escenarios dinamicamente
        # ET.SubElement(xml_frases, "{" + xmlns + "}Frase", TipoFrase=self.company_id.fel_company_type, CodigoEscenario=self.company_id.fel_company_code)
        invoice_line = self.invoice_line_ids
        order_invoice_line = sorted(self.invoice_line_ids, key=lambda x: x.sequence)
        _logger.info('LINES ' + str(len(invoice_line)))
        xml_items = ET.SubElement(xml_data_emision, "{" + xmlns + "}Items")
        invoice_counter = 0
        grand_total = 0
        # LineasFactura
        for line in invoice_line:
            if not line.display_type in ('line_section', 'line_note'):
                invoice_counter += 1

                BienOServicio = "B"
                if line.product_id.type == 'service':
                    BienOServicio = "S"

                # ------------------------------
                # --- CHECK INOVICE CURRENCY ---
                # ------------------------------

                line_price_unit = line.price_unit
                line_price = line.quantity * line.price_unit
                line_price_total = line.price_total
                line_price_subtotal = line.price_subtotal
                price_tax = line_price_total - line_price_subtotal
                tax_amount = 0
                if make_conversion:
                    set_conversion_data = {
                        "line": line,
                        "conversion_rate": conversion_rate
                    }
                    get_conversion_data = conversion_rate_manager(self, "line", set_conversion_data)

                    line_price_unit = get_conversion_data['line_price_unit']
                    line_price = get_conversion_data['line_price']
                    line_price_total = get_conversion_data['line_price_total']
                    line_price_subtotal = get_conversion_data['line_price_subtotal']
                    price_tax = get_conversion_data['price_tax']
                    grand_total += line_price_total
                else:
                    grand_total += line_price_total

                # Item
                xml_item = ET.SubElement(xml_items, "{" + xmlns + "}Item", BienOServicio=BienOServicio, NumeroLinea=str(invoice_counter))

                line_price = round(line_price, 2)
                ET.SubElement(xml_item, "{" + xmlns + "}Cantidad").text = str(line.quantity)
                ET.SubElement(xml_item, "{" + xmlns + "}UnidadMedida").text = "UND"
                
                line_description_source = self.company_id.fel_invoice_line_name
                line_description = line.product_id.name
                if line_description_source == 'description':
                    line_description = line.name
                
                if line_code_divider:
                    if line.product_id.default_code:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line.product_id.default_code + "@" + line_description
                    else:
                        ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = "@" + line_description
                else:
                    note_description = self.get_description_notes(line.id, order_invoice_line)
                    ET.SubElement(xml_item, "{" + xmlns + "}Descripcion").text = line_description + " " + note_description
                
                    
                
                
                ET.SubElement(xml_item, "{" + xmlns + "}PrecioUnitario").text = str(round(line_price_unit, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Precio").text = str(line_price)
                ET.SubElement(xml_item, "{" + xmlns + "}Descuento").text = str(round((line.discount * (line.quantity * line.price_unit))/100, 2))
                ET.SubElement(xml_item, "{" + xmlns + "}Total").text = str(round(line_price_total, 2))

        # Totales
        xml_totales = ET.SubElement(xml_data_emision, "{" + xmlns + "}Totales")
        ET.SubElement(xml_totales, "{" + xmlns + "}GranTotal").text = str(round(grand_total, 2))

        # Adenda
        xml_adenda = ET.SubElement(xml_doc, "{" + xmlns + "}Adenda")
        if self.company_id.fel_addendum_currency_rate or self.company_id.fel_addendum_journal_sequence:
            if self.company_id.fel_addendum_journal_sequence:
                ET.SubElement(xml_adenda, "SERIE").text = self.journal_id.code
            if make_conversion and self.company_id.fel_addendum_currency_rate:
                # ET.SubElement(ade, "NITEXTRANJERO").text = "111111"
                if conversion_rate > 1.0:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 * conversion_rate)
                else:
                    ET.SubElement(xml_adenda, "TASADECAMBIO").text = str(1 / conversion_rate)

        date_due = self.invoice_date_due

        date_due_format = "%d-%m-%Y"
        date_due = date_due.strftime(date_due_format)
        ET.SubElement(xml_adenda, "FechaVencimiento").text = date_due

        xml_content = ET.tostring(xml_root, encoding="UTF-8", method="xml")
        search_string = "ns0"
        string_remplace = "dte"
        xml_content = xml_content.decode('utf_8')
        xml_content = xml_content.replace(search_string, string_remplace)
        xml_content = xml_content.encode('utf_8')

        _logger.info('FEL CONTENT ' + str(xml_content))
        store_sent_xml(self, xml_content, vat, date_due, fel_certifier)

        if fel_certifier == 'infile' or fel_certifier == 'g4s':
            xml_content = base64.b64encode(xml_content)

        return xml_content

    def send_data_api(self, xml_data=None, type_document='fel', fel_type=1):
        company_nit = self.env.company.vat
        fel_certifier = self.env.company.fel_certifier
        uuid = ""
        serie = ""
        dte_number = ""
        dte_date = ""
        sat_ref_id = ""
        
        # GUATEFACTURAS
        if fel_certifier == 'guatefacturas':
            company_vat = self.env.company.vat
            soap_username = self.env.company.guatefacturas_soap_username
            soap_password = self.env.company.guatefacturas_soap_password
            username = self.env.company.guatefacturas_username
            password = self.env.company.guatefacturas_password
            active_env = self.journal_id.guatefacturas_fel
            env_url = self.env.company.guatefacturas_url_dev
            fel_establishment_code = self.journal_id.fel_establishment_code
            if not fel_establishment_code:
                fel_establishment_code = self.env.company.fel_establishment_code                
            if active_env == 'production':
                env_url = self.env.company.guatefacturas_url_prod
                
            second_wsdl = env_url+'?wsdl'
            
            ts = time.time()
            data3 = self.name + '_' + str(ts)
            
            session = Session()
            session.auth = HTTPBasicAuth(soap_username, soap_password)            
            client = zeep.Client(wsdl=second_wsdl, transport=Transport(session=session))
            
            if type_document == 'cancel':
                company_vat = self.company_id.vat
                company_vat = re.sub(r'\ |\?|\.|\!|\/|\;|\:|\-', '', company_vat)
                company_vat = company_vat.upper()
                fecha_anulacion = dt.datetime.now(gettz("America/Guatemala")).__format__('%Y%m%d')
                service_response = client.service.anulaDocumento(username, password, company_vat, self.serie, self.dte_number, self.partner_id.vat, fecha_anulacion, "Anulación")
                
                xml_response = ET.ElementTree(ET.fromstring(str(service_response)))
                
                root = xml_response.getroot()

                for child in root:
                    if child.tag == 'ESTADO' and child.text == "ANULADO":
                        uuid = self.uuid
                        serie = self.serie
                        dte_number = self.dte_number
                        dte_date = fecha_anulacion
                
            else:

                service_response = client.service.generaDocumento(username, password, company_vat, fel_establishment_code, fel_type, 1, 'D', xml_data)
                
                service_response = service_response.replace('<Resultado>', "")
                service_response = service_response.replace('</Resultado>', "")
                
                valid_response = False
                if service_response.find('dte:NumeroAutorizacion') > 0:
                    valid_response = True
                
                if not valid_response:
                    raise UserError(_("La factura no pudo ser validada en la SAT\n Error:%s." % (service_response)))
                
                xml_response = ET.ElementTree(ET.fromstring(str(service_response)))
                
                root = xml_response.getroot()

                for child in root:
                    #print(child.tag)
                    if child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}SAT':
                        #sat_root 
                        for sat_child in child:
                            #print('CHUILDS', sat_child.tag)
                            if sat_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}DTE':
                                for dte_child in sat_child:
                                    #print('DTE CHILD', dte_child.tag)
                                    if dte_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}Certificacion':
                                        for cert_child in dte_child:
                                            #print('CERT CHILD', cert_child.tag)
                                            if cert_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}NumeroAutorizacion':
                                                #print('AUHT CHILD', cert_child.attrib['Serie'])
                                                uuid = cert_child.text
                                                serie = cert_child.attrib['Serie']
                                                dte_number = cert_child.attrib['Numero']
                                            if cert_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}FechaHoraCertificacion':
                                                dte_date = cert_child.text
            
        # G4S
        if fel_certifier == 'g4s':
            company_vat = self.env.company.vat
            requestor_id = self.env.company.requestor_id
            username = self.env.company.g4s_username
            active_env = self.env.company.g4s_environment
            env_url = self.env.company.g4s_dev_url
            if active_env == 'production':
                env_url = self.env.company.g4s_prod_url

            second_wsdl = env_url+'?wsdl'
            client = zeep.Client(wsdl=second_wsdl)
            ts = time.time()
            type_request = 'POST_DOCUMENT_SAT'
            data3 = self.name + '_' + str(ts)
            ran = str(randint(1, 99999))

            if type_document == 'cancel':
                type_request = 'VOID_DOCUMENT'
                data3 = 'XML'
            request_data = {
                'Requestor': requestor_id,
                'Transaction': 'SYSTEM_REQUEST',
                'Country': 'GT',
                'Entity': company_vat,
                'User': requestor_id,
                'UserName': username,
                'Data1': type_request,
                'Data2': xml_data,
                'Data3': data3
            }
            #print('Data Sent', request_data)
            service_response = client.service.RequestTransaction(**request_data)
            #print('RESPUESTA--------------------------------------------------------------------------')
            #print(service_response)
            if 'Response' in service_response:
                if 'Code' in service_response['Response']:
                    if service_response['Response']['Code'] != 1:
                        _logger.info("La factura no pudo ser validada en la SAT\n Error No:%s\n %s." % (service_response['Response']['Code'], service_response['Response']['Description']))
                        uuid = str(service_response['Response']['Description'])
                        serie = False
                        dte_number = False
                        today_date = datetime.now()
                        today_date = str(today_date)
                        dte_date = today_date
                        #raise UserError()
                    if service_response['Response']['Code'] == 1:
                        if 'ResponseData' in service_response:
                            if 'ResponseData1' in service_response['ResponseData']:
                                success_response = service_response['ResponseData']['ResponseData1']
                                xml_content = base64.b64decode(success_response)
                                xml_response = ET.ElementTree(ET.fromstring(xml_content))
                                root = xml_response.getroot()

                                if type_document == 'cancel':
                                    uuid = self.uuid
                                    serie = self.serie
                                    dte_number = self.dte_number
                                    dte_date = self.dte_date

                                else:
                                    for child in root:
                                        #print(child.tag)
                                        if child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}SAT':
                                            #sat_root 
                                            for sat_child in child:
                                                #print('CHUILDS', sat_child.tag)
                                                if sat_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}DTE':
                                                    for dte_child in sat_child:
                                                        #print('DTE CHILD', dte_child.tag)
                                                        if dte_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}Certificacion':
                                                            for cert_child in dte_child:
                                                                #print('CERT CHILD', cert_child.tag)
                                                                if cert_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}NumeroAutorizacion':
                                                                    #print('AUHT CHILD', cert_child.attrib['Serie'])
                                                                    uuid = cert_child.text
                                                                    serie = cert_child.attrib['Serie']
                                                                    dte_number = cert_child.attrib['Numero']
                                                                if cert_child.tag == '{http://www.sat.gob.gt/dte/fel/0.2.0}FechaHoraCertificacion':
                                                                    dte_date = cert_child.text
                                #for element in root.find("dte:SAT"):
                                #    DTE = element.find("DTE")
                                #    print('ELEMENTOS', element, DTE)
                                # print('XML SUCCESS', xml_content)

        # INFILE
        if fel_certifier == 'infile':
            infile_user = self.env.company.infile_user
            infile_xml_url_signature = self.env.company.infile_xml_url_signature
            infile_xml_key_signature = self.env.company.infile_xml_key_signature
            infile_url_certificate = self.env.company.infile_url_certificate
            infile_key_certificate = self.env.company.infile_key_certificate
            infile_url_cancel = self.env.company.infile_url_anulation

            XML = xml_data
            ran = str(randint(1, 99999))
            ts = time.time()
            codigo_firma = str(ts)+str(self.id)
            is_anullment = "N"
            if type_document == 'cancel':
                is_anullment = 'S'
            data_send = {
                'llave': infile_xml_key_signature,
                'archivo': XML,
                'codigo': codigo_firma,
                'alias': infile_user,
                'es_anulacion': is_anullment
            }
            
            
            response = requests.request("POST", infile_xml_url_signature, data=data_send)
            JSON_response_signature = response.json()
            
            if not JSON_response_signature["resultado"]:
                message = "Ha ocurrido un error al intentar firmar el documento. \n %s" % (JSON_response_signature["descripcion"])
                
                raise ValidationError(message)
            xml_dte = JSON_response_signature["archivo"]
            payload = {
                'nit_emisor': self.company_id.vat,
                'correo_copia': self.company_id.email,
                'xml_dte': xml_dte,
            }

            ident = str(randint(1111111, 9999999))
            ts = time.time()
            identificador = str(self.id)+'-'+str(ts)
            headers = {
                'usuario': infile_user,
                'llave': infile_key_certificate,
                'content-type': "application/json",
                'identificador': identificador,
            }

            api_url = infile_url_certificate
            if type_document == 'cancel':
                api_url = infile_url_cancel

            response = requests.request("POST", api_url, data=json.dumps(payload), headers=headers)
            JSON_response_certificate = response.json()

            uuid = JSON_response_certificate["uuid"]
            serie = JSON_response_certificate["serie"]
            dte_number = JSON_response_certificate["numero"]
            dte_date = JSON_response_certificate["fecha"]
            error_count = JSON_response_certificate["cantidad_errores"]
            error_description = JSON_response_certificate["descripcion_errores"]
            # resulta_codigo = tree_res.find('ERROR').attrib['Codigo']
            # resulta_descripcion = tree_res.find('ERROR').text

            if error_count > 0:
                print('ERROR FEL', JSON_response_certificate, JSON_response_signature)
                raise UserError(_("La factura no pudo ser validada en la SAT\n Error No:%s\n %s." % (error_count, error_description)))

        # DIGIFACT
        if fel_certifier == 'digifact':
            digifact_user = self.env.company.digifact_username
            digifact_password = self.env.company.digifact_password
            if self.journal_id.is_fel == 'development':
                digifact_api_login = self.env.company.digifact_api_dev_login
                digifact_api_certificate = self.env.company.digifact_api_dev_certificate
            if self.journal_id.is_fel == 'production':
                digifact_api_login = self.env.company.digifact_api_prod_login
                digifact_api_certificate = self.env.company.digifact_api_prod_certificate

            digifact_access_code = company_nit.zfill(12)

            # GET ACTIVE TOKENS
            today_date = datetime.now()
            today_date = str(today_date)

            tokens_query = self.env['pt_multicert_felgt.digifact_auth_tokens'].search([
                ('expiration_date', '>', today_date)
            ])

            auth_token = ""
            for token in tokens_query:
                auth_token = token['auth_token']

            if auth_token == "":

                username = "GT."+str(digifact_access_code)+"."+str(digifact_user)

                login_data = {
                    "Username": username,
                    "Password": digifact_password
                }

                login_headers = {
                    'content-type': "application/json"
                }

                # GET AUTH TOKEN
                try:
                    login_response = requests.request("POST", digifact_api_login, data=json.dumps(login_data), headers=login_headers, verify=False)
                    json_login_response = login_response.json()
                except Exception as e:
                    _logger.info('LOGIN ERROR ' + str(login_response))
                    store_sent_xml(self, login_response, "ERROR-LOGIN"+str(e), "LOGIN", fel_certifier)
                    raise UserError('Ha ocurrido un error al realizar el login al servicio de Digifact (%s - %s)' % (login_response, str(e)))
                    
                auth_token = ""
                if "Token" in json_login_response:
                    auth_token = json_login_response['Token']
                    expiration_date = datetime.strptime(json_login_response['expira_en'][:-3], '%Y-%m-%dT%H:%M:%S.%f')                     
                    new_token = {
                        "name": "authToken"+str(today_date),
                        "auth_token": auth_token,
                        "expiration_date": expiration_date
                    }                    
                    self.env['pt_multicert_felgt.digifact_auth_tokens'].create(new_token)
                else:
                    raise ValidationError("Error de autenticación con el Certficador FEL: \n "+str(json_login_response["message"]))

            certificate_headers = {
                'content-type': "application/xml",
                'Authorization': 'Bearer ' + auth_token
            }

            type_document_sent = "CERTIFICATE_DTE_XML_TOSIGN"
            if type_document == 'cancel':
                type_document_sent = 'ANULAR_FEL_TOSIGN'

            complete_url_certificate = str(digifact_api_certificate) + "?NIT="+str(digifact_access_code)+"&TIPO="+str(type_document_sent)+"&FORMAT=XML"

            try:
                certificate_response = requests.request("POST", complete_url_certificate, data=xml_data, headers=certificate_headers, verify=False)
                print(certificate_response)
                json_certificate_response = certificate_response.json()
            except Exception as e:
                _logger.info('CERFTICATE ERROR ' + str(login_response))
                store_sent_xml(self, login_response, "CERFTICATE-LOGIN"+str(e), "LOGIN", fel_certifier)
                raise UserError('Ha ocurrido un error al realizar el login al servicio de Digifact (%s - %s)' % (login_response, str(e)))

            uuid = ""
            serie = ""
            dte_number = ""
            dte_date = ""
            sat_ref_id = ""

            if type_document == 'cancel':
                if 'Codigo' in json_certificate_response:
                    if json_certificate_response['Codigo'] == 1:
                        if 'AcuseReciboSAT' in json_certificate_response:
                            sat_ref_id = json_certificate_response['AcuseReciboSAT']

                        if 'Autorizacion' in json_certificate_response:
                            uuid = json_certificate_response['Autorizacion']

                        if 'Serie' in json_certificate_response:
                            serie = json_certificate_response['Serie']

                        if 'NUMERO' in json_certificate_response:
                            dte_number = json_certificate_response['NUMERO']

                        if 'Fecha_DTE' in json_certificate_response:
                            dte_date = json_certificate_response['Fecha_DTE']
                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))
                else:
                    if 'Mensaje' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))
                    elif 'Message' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al comunicarse con el CERTIFICADOR: \n Mensaje: '+str(json_certificate_response['Message'])+'\n Detalle técnico:\n'+str(json_certificate_response['ExceptionMessage'] + '\n StackTrace:' + str(json_certificate_response['StackTrace'])))
                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT (Error de CERTFICADOR)')

            if type_document == 'fel':

                if 'Codigo' in json_certificate_response:
                    if json_certificate_response['Codigo'] == 1:
                        if 'AcuseReciboSAT' in json_certificate_response:
                            sat_ref_id = json_certificate_response['AcuseReciboSAT']

                        if 'Autorizacion' in json_certificate_response:
                            uuid = json_certificate_response['Autorizacion']

                        if 'Serie' in json_certificate_response:
                            serie = json_certificate_response['Serie']

                        if 'NUMERO' in json_certificate_response:
                            dte_number = json_certificate_response['NUMERO']

                        if 'Fecha_DTE' in json_certificate_response:
                            dte_date = json_certificate_response['Fecha_DTE']

                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))

                else:
                    if 'Mensaje' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT: \n Codigo: '+str(json_certificate_response['Codigo'])+' \n Mensaje: '+str(json_certificate_response['Mensaje'])+'\n Detalle técnico:\n'+str(json_certificate_response['ResponseDATA1']))
                    elif 'Message' in json_certificate_response:
                        raise ValidationError('Ha ocurrido un error al comunicarse con el CERTIFICADOR: \n Mensaje: '+str(json_certificate_response['Message'])+'\n Detalle técnico:\n'+str(json_certificate_response['ExceptionMessage'] + '\n StackTrace:' + str(json_certificate_response['StackTrace'])))
                    else:
                        raise ValidationError('Ha ocurrido un error al generar la factura en la SAT (Error de CERTFICADOR)')

        #FORCON
        if fel_certifier == 'forcon':
            user = self.env.company.forcon_user
            password = self.env.company.forcon_password
            

            env_url = ""
            second_wsdl = ""
            if self.journal_id.forcon_fel == 'development':
                env_url = self.env.company.forcon_url_dev
                if not env_url:
                    raise ValidationError("No ha configurado link para la certificación en ambiente de pruebas.")
                second_wsdl = env_url+'?wsdl'
            else:
                env_url = self.env.company.forcon_url_prod
                if not env_url:
                    raise ValidationError("No ha configurado link para la certificación en ambiente de producción.")
                second_wsdl = env_url+'?wsdl'

            client = zeep.Client(wsdl=second_wsdl)
            request_data = {
                'sUsuario': user,
                'sClave': password,
                'sXmlDte': xml_data
            }
            if type_document == 'cancel':
                service_response = client.service.AnularDteOficialV2(user, password, xml_data)
                if 'rwsResultado' in service_response:
                    if not service_response['rwsResultado']:
                        raise UserError(_("La factura no pudo ser anulada en la SAT\n %s." % (service_response['rwsDescripcion'])))          
                    uuid = self.uuid
                    serie = self.serie
                    dte_number = self.dte_number
                    dte_date = self.dte_date
                    sat_ref_id = self.sat_ref_id      
            else:
                service_response = client.service.EmitirDteOficialV2(user, password, xml_data)
                if 'rwsResultado' in service_response:
                    if not service_response['rwsResultado']:
                        raise UserError(_("La factura no pudo ser validada en la SAT\n %s." % (service_response['rwsDescripcion'])))

                    if service_response['rwsResultado']:
                        uuid = service_response['rwsAutorizacionUUID']
                        serie = service_response['rwsSerieDTE']
                        dte_number = service_response['rwsNumeroDTE']
                        sat_ref_id = service_response['rwsAcuseReciboSAT']
                        dte_date = service_response['rwsFechaCertificaDTE']
        return uuid, serie, dte_number, dte_date, sat_ref_id

    def get_company_address(self):
        street = self.company_id.street or "Ciudad"
        street2 = self.company_id.street2 or ""
        address = "%s %s"%(street, street2)

        return address
    #FIXME:
    """
        Función que devuelve una descripción formada con las notas que se encuentren dentro de una factura.
        La función recibe una lista de lineas de facturas, esta lista estan conformadas por todas
        aquellas lineas de factura estan delante de la linea que esta siendo evaluada dentro del for que llama
        a esta función. Tomará todas aquellas líneas que son de tipo nota y concatenara su texto para formar una descripción
        y así devolverla. De esta forma sabemos que todas las notas que esten delante de la linea en cuestión son notas 
        que forman parte de la descripción de la misma.
    """
    def get_description_notes(self, id, line_ids):
        description = ""
        index = 1
        for line in line_ids:
            if id == line.id:
                sublist = line_ids[index:]
                for sub in sublist:
                    if sub.display_type == 'line_note':
                        description += sub.name + " "
                    else:
                        break
                break
            index += 1
        
        return description

    def get_company_code(self):
        company_codes = {}
        if self.env.company.fel_company_configuration:
            company_codes[str(self.env.company.fel_company_type)] = str(self.env.company.fel_company_code)
            if self.env.company.fel_iva_company_exception:
                company_codes["4"] = "10"
        else:
            if self.env.company.tax_withholding_isr != 'definitive_withholding':
                company_codes["1"] = "1"    
            if self.env.company.tax_withholding_isr == 'definitive_withholding':
                company_codes["1"] = "2"    
            if self.env.company.tax_withholding_iva != 'no_witholding':
                company_codes["2"] = "1"
            if self.env.company.fel_iva_company_exception:
                company_codes["4"] = "10"
        return company_codes
def number2text(number_in):

    converted = ''
    if type(number_in) != 'str':
        number = str(number_in)
    else:
        number = number_in

    number_str = number
    number_str = number_str.replace(',', '')
    try:
        number_int, number_dec = number_str.split(".")
    except ValueError:
        number_int = number_str
        number_dec = ""

    number_str = number_int.zfill(9)
    millones = number_str[:3]
    miles = number_str[3:6]
    cientos = number_str[6:]

    if(millones):
        if(millones == '001'):
            converted += 'UN MILLON '
        elif(int(millones) > 0):
            converted += '%sMILLONES ' % __convertNumber(millones)

    if(miles):
        if(miles == '001'):
            converted += 'MIL '
        elif(int(miles) > 0):
            converted += '%sMIL ' % __convertNumber(miles)
    if(cientos):
        if(cientos == '001'):
            converted += 'UN '
        elif(int(cientos) > 0):
            converted += '%s ' % __convertNumber(cientos)

    if number_dec == "":
        number_dec = "00"
    if (len(number_dec) < 2):
        number_dec += '0'

    converted += 'CON ' + number_dec + "/100."
    return converted.title()


UNIDADES = (
    '',
    'UNO ',
    'DOS ',
    'TRES ',
    'CUATRO ',
    'CINCO ',
    'SEIS ',
    'SIETE ',
    'OCHO ',
    'NUEVE ',
    'DIEZ ',
    'ONCE ',
    'DOCE ',
    'TRECE ',
    'CATORCE ',
    'QUINCE ',
    'DIECISEIS ',
    'DIECISIETE ',
    'DIECIOCHO ',
    'DIECINUEVE ',
    'VEINTE '
)
DECENAS = (
    'VEINTI',
    'TREINTA ',
    'CUARENTA ',
    'CINCUENTA ',
    'SESENTA ',
    'SETENTA ',
    'OCHENTA ',
    'NOVENTA ',
    'CIEN '
)
CENTENAS = (
    'CIENTO ',
    'DOSCIENTOS ',
    'TRESCIENTOS ',
    'CUATROCIENTOS ',
    'QUINIENTOS ',
    'SEISCIENTOS ',
    'SETECIENTOS ',
    'OCHOCIENTOS ',
    'NOVECIENTOS '
)


def conversion_rate_manager(self, data_type, data):

    if data_type == 'line':
        line = data['line']
        line_price_unit = line.price_unit
        line_price = line.quantity * line.price_unit
        line_price_total = line.price_total
        line_price_subtotal = line.price_subtotal
        conversion_rate = data['conversion_rate']
        conversion_rate = 1 / conversion_rate
        tax_amount = 0
        if conversion_rate > 1.0:
            subtotal_conversion = 0
            subtotal_conversion = line.price_subtotal * conversion_rate
            if line.tax_ids:
                if line.tax_ids.amount_type == 'percent':
                    tax_amount = (line.tax_ids.amount * subtotal_conversion) / 100

            line_price = line_price * conversion_rate
            line_price_unit = line.price_unit * conversion_rate
            line_price_subtotal = line.price_subtotal * conversion_rate
            line_price_total = line.price_total * conversion_rate
            price_tax = tax_amount
            line_price_subtotal = line_price_total - price_tax

        else:
            subtotal_conversion = 0
            subtotal_conversion = line.price_subtotal / conversion_rate
            if line.tax_ids:
                if line.tax_ids.amount_type == 'percent':
                    tax_amount = (line.tax_ids.amount * subtotal_conversion) / 100

            line_price = line_price / conversion_rate
            line_price_unit = line.price_unit / conversion_rate
            line_price_subtotal = line.price_subtotal / conversion_rate
            line_price_total = line.price_total / conversion_rate
            price_tax = tax_amount
            line_price_subtotal = line_price_total - price_tax

        conversion_data = {
            "line_price": line_price,
            "line_price_unit": line_price_unit,
            "line_price_total": line_price_total,
            "line_price_subtotal": line_price_subtotal,
            "price_tax": price_tax
        }

        return conversion_data


def store_sent_xml(self, xml_content, vat, date_due, certifier="digifact"):

    if certifier == "digifact":
        api_sent = self.env.company.digifact_api_dev_certificate
        if self.journal_id.is_fel == 'development':
            api_sent = self.env.company.digifact_api_dev_certificate
        if self.journal_id.is_fel == 'production':
            api_sent = self.env.company.digifact_api_prod_certificate

        new_xml_sent = {
                "name": str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due),
                "xml_content": xml_content,
                "api_sent": api_sent
        }
        self.env['pt_multicert_felgt.digifact_xml_sent'].create(new_xml_sent)

    if certifier == "infile":
        api_sent = self.env.company.infile_xml_url_signature

        sql = "INSERT INTO pt_multicert_felgt_infile_xml_sent(name, data_content, api_sent, create_uid, create_date, write_uid, write_date)"
        sql += " VALUES(%s, %s, %s, %s, %s, %s, %s)"

        db_name = self.env.cr.dbname
        cr_log = sql_db.db_connect(self.env.cr.dbname).cursor()
        # create transaction cursor
        name = str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due)
        final_xml = xml_content.decode('utf-8')
        params = [name, final_xml, api_sent, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
        cr_log.execute(sql, params)
        cr_log.commit()

    if certifier == "guatefacturas":
        api_sent = self.env.company.guatefacturas_url_dev
        if self.journal_id.is_fel == 'development':
            api_sent = self.env.company.guatefacturas_url_dev
        if self.journal_id.is_fel == 'production':
            api_sent = self.env.company.guatefacturas_url_prod

        sql = "INSERT INTO pt_multicert_felgt_guatefacturas_xml_sent(name, data_content, api_sent, create_uid, create_date, write_uid, write_date)"
        sql += " VALUES(%s, %s, %s, %s, %s, %s, %s)"

        db_name = self.env.cr.dbname
        cr_log = sql_db.db_connect(self.env.cr.dbname).cursor()
        # create transaction cursor
        name = str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due)
        final_xml = xml_content.decode('utf-8')
        params = [name, final_xml, api_sent, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
        cr_log.execute(sql, params)
        cr_log.commit()
    
    if certifier == "g4s":
        api_sent = self.env.company.infile_xml_url_signature

        sql = "INSERT INTO pt_multicert_felgt_g4s_xml_sent(name, data_content, api_sent, create_uid, create_date, write_uid, write_date)"
        sql += " VALUES(%s, %s, %s, %s, %s, %s, %s)"

        db_name = self.env.cr.dbname
        cr_log = sql_db.db_connect(self.env.cr.dbname).cursor()
        # create transaction cursor
        name = str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due)
        final_xml = xml_content.decode('utf-8')
        params = [name, final_xml, api_sent, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
        cr_log.execute(sql, params)
        cr_log.commit()
    if certifier == "megaprint":
        api_sent = self.env.company.megaprint_api_dev_url_invoices
        if self.journal_id.is_fel == 'development':
            api_sent = self.env.company.megaprint_api_dev_url_invoices
        if self.journal_id.is_fel == 'production':
            api_sent = self.env.company.megaprint_api_prod_url_invoices

        new_xml_sent = {
                "name": str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due),
                "data_content": xml_content,
                "api_sent": api_sent
        }

        self.env['pt_multicert_felgt.megaprint_json_sent'].create(new_xml_sent)
    if certifier == "forcon":
        api_sent = ""
        if self.journal_id.forcon_fel == 'development':
            api_sent = "http://pruebasfel.eforcon.com/feldev/WSForconFel.asmx"
        else:
            api_sent =  "http://fel.eforcon.com/feldev/WSForconFel.asmx"
        

        sql = "INSERT INTO pt_multicert_felgt_forcon_xml_sent(name, data_content, api_sent, create_uid, create_date, write_uid, write_date)"
        sql += " VALUES(%s, %s, %s, %s, %s, %s, %s)"

        db_name = self.env.cr.dbname
        cr_log = sql_db.db_connect(self.env.cr.dbname).cursor()
        # create transaction cursor
        name = str(vat) + '-'+str(self.company_id.vat)+'-'+str(date_due)
        final_xml = xml_content.decode('utf-8')
        params = [name, final_xml, api_sent, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
        cr_log.execute(sql, params)
        cr_log.commit()

def dropzeros(number):
    mynum = decimal.Decimal(number).normalize()
    # e.g 22000 --> Decimal('2.2E+4')
    return mynum.__trunc__() if not mynum % 1 else float(mynum)

def __convertNumber(n):
    output = ''

    if(n == '100'):
        output = "CIEN"
    elif(n[0] != '0'):
        output = CENTENAS[int(n[0])-1]

    k = int(n[1:])
    if(k <= 20):
        output += UNIDADES[k]
    else:
        if((k > 30) & (n[2] != '0')):
            output += '%sY %s' % (DECENAS[int(n[1])-2], UNIDADES[int(n[2])])
        else:
            output += '%s%s' % (DECENAS[int(n[1])-2], UNIDADES[int(n[2])])

    return output

def guatefacturas_departments_mapping(name):
    department = "1"
    switcher = {
        "GUATEMALA": "1",
        "EL PROGRESO": "2",
        "SACATEPEQUEZ": "3",
        "CHIMALTENANGO": "4",
        "ESCUINTLA": "5",
        "SANTA ROSA": "6",
        "SOLOLA": "7",
        "TOTONICAPAN": "8",
        "QUETZALTENANGO": "9",
        "SUCHITEPEQUEZ": "10",
        "RETALHULEU": "11",
        "SAN MARCOS": "12",
        "HUEHUETENANGO": "13",
        "QUICHE": "14",
        "BAJA VERAPAZ": "15",
        "ALTA VERAPAZ": "16",
        "PETEN": "17",
        "IZABAL": "18",
        "ZACAPA": "19",
        "CHIQUIMULA": "20",
        "JALAPA": "21",
        "JUTIAPA": "22",
        "BELICE": "23"
    }
    if switcher.get(name, ""):
        department = switcher.get(name, "")
    
    return department

def guatefacturas_townships_mapping(name, department_id):
    township = "1"
    if department_id == 1:
        switcher = {
            "Guatemala": "1",
            "Santa Catarina Pinula": "2",
            "San Jose Pinula": "3",
            "San Jose del Golfo": "4",
            "Palencia": "5",
            "Chinautla": "6",
            "San Pedro Ayampuc": "7",
            "Mixco": "8",
            "San Pedro Sacatepequez": "9",
            "San Juan Sacatepequez": "10",
            "San Raymundo": "11",
            "Chuarrancho": "12",
            "Fraijanes": "13",
            "Amatitlan": "14",
            "Villa Nueva": "15",
            "Villa Canales": "16",
            "San Miguel Petapa": "17"
        }
        if switcher.get(name, ""):
            township = switcher.get(name, "")
    
    return township