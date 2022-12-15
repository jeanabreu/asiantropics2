# -*- coding: utf-8 -*-

from odoo import api, models, sql_db, fields, _
from decimal import Decimal, ROUND_HALF_UP
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare
from datetime import datetime

# SAT LAW REFERENCE AS 2019-11-25 for Agentes Retenedores de IVA
# ---------------------------------------------------------------------------------------------------------------
# |         AGENTE RETENCION        |      Producto / Operacion      |  % Retencion  |    Retener a partir de   |
# |-------------------------------------------------------------------------------------------------------------|
# | Exportadores                    | Agrícolas y pecuarios          |       65 %    |       Q 2,500.00         |
# |                                 | Producto no agropecuarios      |       15 %    |       Q 2,500.00         |
# |                                 | Bienes o servicios             |       15 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Beneficiarios del Decreto 29-89 | Bienes o servicios             |       65 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Sector publico                  | Bienes o servicios             |       25 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Operadores de tarjetas de       | Pagos de tarjetahabientes      |       15 %    |    Cualquier Monto       |
# | Credito                         | Pago de combustibles           |      1.5 %    |    Cualquier Monto       |
# |-------------------------------------------------------------------------------------------------------------|
# | Contribuyentes especiales       | Bienes o servicios             |       15 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
# | Otros Agentes de retencion      | Bienes o servicios             |       15 %    |       Q 2,500.00         |
# |-------------------------------------------------------------------------------------------------------------|
#
# Escenarios adicionales
# En caso de ser pequeño contribuyente se aplica un 5% en todos los casos
# En caso de ser ambos agentes retenedores de IVA no se aplica retención

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    
    payment_type_document = fields.Many2one('l10n_gt_extra.type.document.payment', string='Tipo de Documento', compute="get_payment_document_type")
    
    
    def get_payment_document_type(self):
        
        for rec in self:
            if rec.payment_id.type_document:
                rec.payment_type_document = rec.payment_id.type_document
            else:
                rec.payment_type_document = False


class AccountMove(models.Model):
    _inherit = 'account.move'

    tax_withholding_isr = fields.Selection(
        [
            ('quarter_witholding', 'Sujeto a Pagos Trimestrales'),
            ('definitive_withholding', 'Sujeto a Retención Definitiva'),
            ('small_taxpayer_withholding',
             'P.C. No genera Devolución de Crédito Fiscal')
        ], string="Retención ISR", default="quarter_witholding"
    )

    tax_withholding_price = fields.Float(string='Monto de retención')
    tax_withholding_iva = fields.Selection(
        [
            ('no_witholding', 'No es agente rentenedor de IVA'),
            ('export', 'Exportadores'),
            ('decree_28_89', 'Beneficiarios del Decreto 28-89'),
            ('public_sector', 'Sector Público'),
            ('credit_cards_companies', 'Operadores de Tarjetas de Crédito y/o Débito'),
            ('special_taxpayer', 'Contribuyente Especiales'),
            ('special_taxpayer_export', 'Contribuyente Especial y Exportador'),
            ('others', 'Otros Agentes de Retención'),
            ('iva_forgiveness', 'Exención de IVA')
        ], string='Retención IVA', default=lambda self: self._set_initial_values())

    tipo_gasto = fields.Selection([('compra', 'Compra/Bien'), ('servicio', 'Servicio'), ('importacion', 'Importación/Exportación'), ('combustible', 'Combustible'), ('mixto', 'Mixto')], string="Tipo de Gasto", default="compra")
    numero_viejo = fields.Char(string="Numero Viejo")
    serie_rango = fields.Char(string="Serie Rango")
    inicial_rango = fields.Integer(string="Inicial Rango")
    final_rango = fields.Integer(string="Final Rango")
    tax_withold_amount = fields.Monetary(string='Retención ISR')
    
    isr_withold_amount = fields.Monetary(string='Retención ISR')
    iva_withold_amount = fields.Monetary(string='Retención/Exención IVA')
    tax_withholding_amount_iva = fields.Monetary(string='Retención IVA')
    diario_facturas_por_rangos = fields.Boolean(string='Las facturas se ingresan por rango', help='Cada factura realmente es un rango de factura y el rango se ingresa en Referencia/Descripción', related="journal_id.facturas_por_rangos")

    user_country_id = fields.Char(string="UserCountry", default=lambda self: self.env.company.country_id.code)

    type_invoice = fields.Selection(
        [
            ('normal_invoice', 'Factura normal'),
            ('special_invoice', 'Factura especial'),
            ('cambiaria', 'Factura Cambiaria'),
            ('cambiaria_exp', 'Factura Cambiaria Exp.'),
            ('nota_debito', 'Nota de Débito')
        ], string='Tipo de factura', default='normal_invoice')

    ref_analytic_line_ids = fields.One2many('account.analytic.line', 'id', string='Analytic lines', compute="get_analytic_lines")
    show_analytic_lines = fields.Boolean(compute="get_show_analytic_lines", store=False)
    bank_operation_ref = fields.Char(string="Referencia bancaria")
    provider_invoice_serial = fields.Char(string="Factura serie")
    provider_invoice_number = fields.Char(string="Factura número")
    belongs_to_bank_statement = fields.Boolean(string="Pertenece a extracto bancario")
    
    """
    #############################
    ### Assets Capitalization ###
    #############################
    """
    # Invoice reference for the capitalization move
    capitalization_invoice_id = fields.Many2one('account.move', string="Factura de capitalización")
    
    # Move reference for the capitalization invoice
    capitalization_move_id = fields.Many2one('account.move', string="Asiento de capitalización")
    
    @api.constrains('provider_invoice_serial', 'provider_invoice_number')
    def _validate_unique_serial_invoice_number(self):
        if self.provider_invoice_serial and self.provider_invoice_number:
            invoice_data = self.search([
                ('provider_invoice_serial', '=', self.provider_invoice_serial), 
                ('provider_invoice_number', '=', self.provider_invoice_number), 
                ('partner_id', '=', self.partner_id.id), 
                ('move_type', '=', 'in_invoice')
            ])
            if len(invoice_data) > 1:
                raise ValidationError("Ya existe una factura de proveedor creada con ese numero de serie y factura")
    
    """
    def write(self, vals):
        for rec in self:
            
            changed_amount = False

            if 'isr_withold_amount' in vals:
                sum_validation = float(vals['isr_withold_amount']) - float(rec.isr_withold_amount)
                print('Sum validation', sum_validation, float(vals['isr_withold_amount']), float(rec.isr_withold_amount))
                if sum_validation!= 0:
                    changed_amount = True
                    
            print('Changed Amount', changed_amount)
            res = super(AccountMove, rec).write(vals)
            
            #if rec.move_type == "in_invoice":
            #    if changed_amount:
            #        rec.check_isr_lines()
                
            return res
    """
    
    def check_isr_iva_lines(self):
        
        company_id = self.env.company
        
        #self._onchange_partner_id()
        if self.partner_id:
            isr_withold_type = ""
            iva_withold_type = "no_witholding"

            if self.partner_id.company_type == "company":
                isr_withold_type = self.partner_id.tax_withholding_isr
            else:
                if self.partner_id.parent_id:
                    isr_withold_type = self.partner_id.parent_id.tax_withholding_isr
                else:
                    isr_withold_type = self.partner_id.tax_withholding_isr

            self.tax_withholding_isr = isr_withold_type
            
            if self.move_type == 'out_invoice':
                if self.partner_id.company_type == "company":
                    company_iva_agent_type = self.partner_id.tax_withholding_iva
                else:
                    if self.partner_id.parent_id:
                        company_iva_agent_type = self.partner_id.parent_id.tax_withholding_iva
                    else:
                        company_iva_agent_type = self.partner_id.tax_withholding_iva

                if company_iva_agent_type != 'no_witholding':
                    self.tax_withholding_iva = company_iva_agent_type
                else:
                    self.tax_withholding_iva = company_iva_agent_type
            
            if self.move_type == 'in_invoice':
                company_iva_agent_type = self.env.company.tax_withholding_iva
                if company_iva_agent_type != 'no_witholding':
                    self.tax_withholding_iva = company_iva_agent_type                    
                else:
                    self.tax_withholding_iva = company_iva_agent_type
        
        ############
        ### IVA ####
        ############
        
        isr_amount = 0
        iva_amount = 0
        iva_retencion_account_data = False
        iva_retencion_account_id = False
        iva_retencion_account_root_id = False
        if company_id.iva_retencion_account_id:
            account_id = False
            
            if self.move_type == 'in_invoice':
                if not company_id.iva_retencion_account_id.iva_purchase_account_id:
                    raise ValidationError('Debe seleccionar el la cuenta a utilizar con retencion de IVA en compras')
                iva_retencion_account_id = company_id.iva_retencion_account_id.iva_purchase_account_id.id
                iva_retencion_account_root_id = company_id.iva_retencion_account_id.iva_purchase_account_id.root_id
                
            if self.move_type == 'out_invoice':
                if not company_id.iva_retencion_account_id.iva_sales_account_id:
                    raise ValidationError('Debe seleccionar el la cuenta a utilizar con retencion de IVA en ventas')
            
                iva_retencion_account_id = company_id.iva_retencion_account_id.iva_sales_account_id.id
                iva_retencion_account_root_id = company_id.iva_retencion_account_id.iva_sales_account_id.root_id
                if self.partner_id.tax_withholding_iva == "iva_forgiveness":
                    if not self.env.company.iva_retencion_account_id.iva_forgiveness_account_id:
                        raise ValidationError('Debe seleccionar el la cuenta de exención en el diario de retenciones de IVA.')
                    else:
                        iva_retencion_account_id = self.env.company.iva_retencion_account_id.iva_forgiveness_account_id.id
                        iva_aml_label = "Exención de IVA"
            
        else:
            raise ValidationError('Debe seleccionar el diario a utilizar con IVA')
        
        print('------------------')
        print('IVA - 1')
        print('------------------')
        
        if self.iva_withold_amount > 0:
            iva_amount = self.iva_withold_amount
            if self.isr_withold_amount > 0:
                isr_amount = self.isr_withold_amount
            has_query_iva_line = False
            has_rec_iva_line = False     
            self.invalidate_cache()
            
            sql = ""
            sql += "SELECT id"
            sql += " FROM account_move_line"
            sql += " WHERE account_id = %s" % (iva_retencion_account_id)
            sql += " AND   move_id = %s" % (self.id)
            
            cr_log = sql_db.db_connect(self._cr.dbname).cursor()
            cr_log.execute(sql)
            
            operation_total = 0
            self.invalidate_cache()
            
            
            if self.move_type == 'in_invoice':
                sql = ""
                sql += "SELECT debit"
                sql += " FROM account_move_line"
                sql += " WHERE debit > 0"
                sql += " AND   move_id = %s" % (self.id)
                
                cr_total = sql_db.db_connect(self.env.cr.dbname).cursor()
                cr_total.execute(sql)
                
                for query_data in cr_total.dictfetchall():
                    operation_total += query_data['debit']
                
                iva_line_counter = 0
                
                
                for query_data in cr_log.dictfetchall():

                    has_query_iva_line = True
                    iva_line_counter += 1
                    
                    
                    if iva_line_counter > 1:
                        sql = ""
                        sql = "DELETE FROM account_move_line WHERE id = %s;" % (query_data['id'])
                        
                        print('------------------')
                        print('IVA - 2')
                        print('------------------')
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                    else:
                        
                        sql = ""
                        sql += "UPDATE account_move_line"
                        sql += " SET price_unit = %s," % (iva_amount * -1)
                        sql += " credit = %s," % (iva_amount)
                        sql += " amount_currency = %s," % (iva_amount*-1)
                        sql += " balance = %s," % (iva_amount*-1)
                        sql += " price_subtotal = %s," % (iva_amount * -1)
                        sql += " price_total = %s," % (iva_amount * -1)
                        sql += " write_uid = %s," % (self.env.user.id)
                        sql += " write_date = '%s'" % (datetime.now())
                        sql += " WHERE id = %s" % (query_data['id'])
                        
                        print('------------------')
                        print('IVA - 3')
                        print('------------------')
                        
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                        
                for line in self.line_ids:
                    print('lines', line.name)
                    print(line.account_id.id, '=', self.partner_id.property_account_payable_id.id)

                    if line.account_id.id == self.partner_id.property_account_payable_id.id:
                        partner_amount = operation_total - iva_amount - isr_amount
                        price_unit = partner_amount * -1
                        credit = partner_amount
                        amount_currency = partner_amount*-1
                        balance = partner_amount * -1
                        price_subtotal = partner_amount * -1
                        amount_residual = partner_amount * -1
                        amount_residual_currency = partner_amount
                        price_total = partner_amount * -1
                        
                        print('------------------')
                        print('IVA - UPDATE PARTNER')
                        print(operation_total)
                        print(iva_amount)
                        print(partner_amount)
                        print('------------------')
                        
                        
                        sql = ""
                        sql += "UPDATE account_move_line"
                        sql += " SET price_unit = %s," % (price_unit)
                        sql += " credit = %s," % (credit)
                        sql += " amount_currency = %s," % (amount_currency)
                        sql += " balance = %s," % (balance)
                        sql += " price_subtotal = %s," % (price_subtotal)
                        sql += " amount_residual = %s," % (amount_residual)
                        sql += " amount_residual_currency = %s," % (amount_residual_currency)
                        sql += " price_total = %s," % (price_total)
                        sql += " write_uid = %s," % (self.env.user.id)
                        sql += " write_date = '%s'" % (datetime.now())
                        sql += " WHERE id = %s" % (line.id)
                        
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                        self.invalidate_cache()
                        
                        print('------------------')
                        print('IVA - 3.1')
                        print('------------------')
                                
                            
                        #return True

                for line in self.line_ids:
                    
                    if iva_retencion_account_id == line.account_id.id:
                        has_rec_iva_line = True
                        break
            
            if self.move_type == 'out_invoice':
                sql = ""
                sql += "SELECT credit"
                sql += " FROM account_move_line"
                sql += " WHERE credit > 0"
                sql += " AND   move_id = %s" % (self.id)
                
                cr_total = sql_db.db_connect(self.env.cr.dbname).cursor()
                cr_total.execute(sql)
                
                for query_data in cr_total.dictfetchall():
                    operation_total += query_data['credit']
                
                iva_line_counter = 0
                for query_data in cr_log.dictfetchall():

                    has_query_iva_line = True
                    iva_line_counter += 1
                    if iva_line_counter > 1:
                        sql = ""
                        sql = "DELETE FROM account_move_line WHERE id = %s;" % (query_data['id'])
                        
                        print('------------------')
                        print('IVA - 2')
                        print('------------------')
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                    else:
                        
                        sql = ""
                        sql += "UPDATE account_move_line"
                        sql += " SET price_unit = %s," % (iva_amount * -1)
                        sql += " debit = %s," % (iva_amount)
                        sql += " amount_currency = %s," % (iva_amount)
                        sql += " balance = %s," % (iva_amount)
                        sql += " price_subtotal = %s," % (iva_amount * -1)
                        sql += " price_total = %s," % (iva_amount * -1)
                        sql += " write_uid = %s," % (self.env.user.id)
                        sql += " write_date = '%s'" % (datetime.now())
                        sql += " WHERE id = %s" % (query_data['id'])
                        
                        print('------------------')
                        print('IVA - 3')
                        print('------------------')
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                        
                        
                        for line in self.line_ids:
                            print('lines', line.name)
                            print(line.account_id.id, '=', self.partner_id.property_account_receivable_id.id)

                            if line.account_id.id == self.partner_id.property_account_receivable_id.id:
                                partner_amount = operation_total - iva_amount - isr_amount
                                price_unit = partner_amount * -1
                                credit = partner_amount
                                amount_currency = partner_amount
                                balance = partner_amount
                                price_subtotal = partner_amount * -1
                                amount_residual = partner_amount
                                
                                amount_residual_currency = partner_amount
                                price_total = partner_amount * -1
                                
                                print('------------------')
                                print('IVA - UPDATE PARTNER')
                                print(operation_total)
                                print(iva_amount)
                                print(partner_amount)
                                print('------------------')
                                
                                
                                sql = ""
                                sql += "UPDATE account_move_line"
                                sql += " SET price_unit = %s," % (price_unit)
                                sql += " debit = %s," % (credit)
                                sql += " amount_currency = %s," % (amount_currency)
                                sql += " balance = %s," % (balance)
                                sql += " price_subtotal = %s," % (price_subtotal)
                                sql += " amount_residual = %s," % (amount_residual)
                                sql += " amount_residual_currency = %s," % (amount_residual_currency)
                                sql += " price_total = %s," % (price_total)
                                sql += " write_uid = %s," % (self.env.user.id)
                                sql += " write_date = '%s'" % (datetime.now())
                                sql += " WHERE id = %s" % (line.id)
                                
                                
                                self._cr.execute(sql)
                                self._cr.commit()
                                self.invalidate_cache()
                                
                                print('------------------')
                                print('IVA - 3.1')
                                print('------------------')
                                
                            
                        #return True

                for line in self.line_ids:
                    if iva_retencion_account_id == line.account_id.id:
                        has_rec_iva_line = True
                        break
            
            if not has_rec_iva_line and not has_query_iva_line:
                
                
                for line in self.line_ids:
                    print('lines', line.name)
                    if line.account_id.id == self.partner_id.property_account_receivable_id.id:
                        price_unit = line.price_unit + iva_amount
                        credit = line.debit - iva_amount
                        amount_currency = line.amount_currency - iva_amount
                        balance = line.balance - iva_amount
                        price_subtotal = line.price_subtotal + iva_amount
                        amount_residual = line.amount_residual - iva_amount
                        amount_residual_currency = line.amount_residual_currency - iva_amount
                        price_total = line.price_total + iva_amount
                        
                        print('------------------')
                        print('IVA - 4.1')
                        print('------------------')
                        
                        sql = ""
                        sql += "UPDATE account_move_line"
                        sql += " SET price_unit = %s," % (price_unit)
                        sql += " debit = %s," % (credit)
                        sql += " amount_currency = %s," % (amount_currency)
                        sql += " balance = %s," % (balance)
                        sql += " price_subtotal = %s," % (price_subtotal)
                        sql += " amount_residual = %s," % (amount_residual)
                        sql += " amount_residual_currency = %s," % (amount_residual_currency)
                        sql += " price_total = %s," % (price_total)
                        sql += " write_uid = %s," % (self.env.user.id)
                        sql += " write_date = '%s'" % (datetime.now())
                        sql += " WHERE id = %s" % (line.id)
                        
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                        
                        self.invalidate_cache()
                        
                        print('------------------')
                        print('IVA - 5')
                        print('------------------')
                  
                sql = ""
                sql += "INSERT INTO account_move_line"
                sql += " (move_id, move_name, date, parent_state, journal_id, company_id, company_currency_id,"
                sql += " account_id, account_root_id, sequence, name, quantity, price_unit, discount, debit, "
                sql += " credit, balance, amount_currency, price_subtotal, price_total, currency_id, partner_id,"
                sql += " exclude_from_invoice_tab, create_uid, create_date, write_uid, write_date"
                sql += ")"
                #sql += " VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
                
                sql += " VALUES(%(move_id)s, %(move_name)s, %(date)s, %(parent_state)s, %(journal_id)s, %(company_id)s, %(company_currency_id)s, %(account_id)s, %(account_root_id)s, %(sequence)s, %(name)s, %(quantity)s, %(price_unit)s, %(discount)s, %(debit)s, %(credit)s, %(balance)s, %(amount_currency)s, %(price_subtotal)s, %(price_total)s, %(currency_id)s, %(partner_id)s, %(exclude_from_invoice_tab)s, %(create_uid)s, %(create_date)s, %(write_uid)s, %(write_date)s);"
                                
                move_date = datetime.now().date()
                if self.date:
                        move_date = self.date
                
                if self.move_type == 'out_invoice':
                    debit = iva_amount
                    credit = 0
                    balance = iva_amount
                    amount_currency = iva_amount
                    
                if self.move_type == 'in_invoice':
                    debit = 0
                    credit = iva_amount
                    balance = iva_amount *-1
                    amount_currency = iva_amount*-1
                
                params = {
                    "move_id": self.id, 
                    "move_name": self.name, 
                    "date":move_date, 
                    "parent_state": self.state, 
                    "journal_id":self.journal_id.id, 
                    "company_id":company_id.id, 
                    "company_currency_id": company_id.currency_id.id, 
                    "account_id": iva_retencion_account_id, 
                    "account_root_id": iva_retencion_account_root_id.id, 
                    "sequence":"10", 
                    "name": "Retencion de IVA", 
                    "quantity":1, 
                    "price_unit": iva_amount * -1, 
                    "discount":0, 
                    "debit":debit, 
                    "credit": credit,
                    "balance": balance, 
                    "amount_currency": amount_currency, 
                    "price_subtotal": iva_amount * -1, 
                    "price_total": iva_amount * -1, 
                    "currency_id": self.currency_id.id, 
                    "partner_id": self.partner_id.id, 
                    "exclude_from_invoice_tab": True, 
                    "create_uid": self.env.user.id, 
                    "create_date": datetime.now(), 
                    "write_uid": self.env.user.id, 
                    "write_date": datetime.now()
                }
                
                #params = [self.id, self.name, move_date, self.state, self.journal_id.id, company_id.id, company_id.currency_id.id, iva_retencion_account_id, iva_retencion_account_root_id.id, "10", "Retencion de IVA", 1, iva_amount * -1, 0, iva_amount, 0, iva_amount, iva_amount, iva_amount * -1, iva_amount * -1, self.currency_id.id, self.partner_id.id, True, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
                
                self._cr.execute(sql, params)
                self._cr.commit()
                
                print('------------------')
                print('IVA - 6')
                print('------------------')
                
                
            #cr_log.close()
            self.invalidate_cache()
                        
                                
        ############
        ### ISR ####
        ############
        
        print('----------------------')
        print(self.isr_withold_amount)
        print('----------------------')

        if self.isr_withold_amount > 0:
            if self.move_type == "in_invoice":
                isr_retencion_account_data = False
                isr_retencion_account_id = False
                isr_retencion_account_root_id = False
                if company_id.isr_retencion_account_id:
                    if not company_id.isr_retencion_account_id.isr_purchase_account_id:
                        raise ValidationError('Debe seleccionar la cuenta ISR compras en el diario de retención del ISR')
                    isr_retencion_account_id = company_id.isr_retencion_account_id.isr_purchase_account_id.id
                    isr_retencion_account_root_id = company_id.isr_retencion_account_id.isr_purchase_account_id.root_id
                else:
                    raise ValidationError('Debe seleccionar el diario a utilizar con ISR')
                
            
                isr_amount = self.isr_withold_amount
                has_query_isr_line = False
                has_rec_isr_line = False     
                self.invalidate_cache()
                
                sql = ""
                sql += "SELECT id, credit"
                sql += " FROM account_move_line"
                sql += " WHERE account_id = %s" % (isr_retencion_account_id)
                sql += " AND   move_id = %s" % (self.id)
                
                cr_log = sql_db.db_connect(self.env.cr.dbname).cursor()
                cr_log.execute(sql)
                
                operation_total = 0
                self.invalidate_cache()
                
                sql = ""
                sql += "SELECT debit"
                sql += " FROM account_move_line"
                sql += " WHERE debit > 0"
                sql += " AND   move_id = %s" % (self.id)
                
                cr_total = sql_db.db_connect(self.env.cr.dbname).cursor()
                cr_total.execute(sql)
                
                for query_data in cr_total.dictfetchall():
                    operation_total += query_data['debit']
                    
                
                isr_line_counter = 0
                for query_data in cr_log.dictfetchall():
                    
                    if query_data['credit'] != isr_amount:
                    
                        has_query_isr_line = True
                        isr_line_counter += 1
                        if isr_line_counter > 1:                            
                            sql = ""
                            sql = "DELETE FROM account_move_line WHERE id = %s;" % (query_data['id'])
                            
                            self._cr.execute(sql)
                            self._cr.commit()
                        else:
                            
                            print('------------------')
                            print('ISR - 1')
                            print(operation_total)
                            print('------------------')
                            
                            sql = ""
                            sql += "UPDATE account_move_line"
                            sql += " SET price_unit = %s," % (isr_amount * -1)
                            sql += " credit = %s," % (isr_amount)
                            sql += " amount_currency = %s," % (isr_amount * -1)
                            sql += " balance = %s," % (isr_amount * -1)
                            sql += " price_subtotal = %s," % (isr_amount * -1)
                            sql += " price_total = %s," % (isr_amount * -1)
                            sql += " write_uid = %s," % (self.env.user.id)
                            sql += " write_date = '%s'" % (datetime.now())
                            sql += " WHERE id = %s" % (query_data['id'])
                            
                            self._cr.execute(sql)
                            self._cr.commit()
                            
                            for line in self.line_ids:
                                
                                
                                print('------------------')
                                print('ISR - Provider validation')
                                print(line.account_id.id, self.partner_id.property_account_payable_id.id)
                                print('------------------')

                                if line.account_id.id == self.partner_id.property_account_payable_id.id:
                                    partner_amount = operation_total - isr_amount - iva_amount
                                    price_unit = partner_amount * -1
                                    credit = partner_amount
                                    amount_currency = partner_amount * -1
                                    balance = partner_amount
                                    price_subtotal = partner_amount * -1
                                    amount_residual = partner_amount * -1
                                    amount_residual_currency = partner_amount * -1
                                    price_total = partner_amount * -1
                                    
                                    sql = ""
                                    sql += "UPDATE account_move_line"
                                    sql += " SET price_unit = %s," % (price_unit)
                                    sql += " credit = %s," % (credit)
                                    sql += " amount_currency = %s," % (amount_currency)
                                    sql += " balance = %s," % (balance)
                                    sql += " price_subtotal = %s," % (price_subtotal)
                                    sql += " amount_residual = %s," % (amount_residual)
                                    sql += " amount_residual_currency = %s," % (amount_residual_currency)
                                    sql += " price_total = %s," % (price_total)
                                    sql += " write_uid = %s," % (self.env.user.id)
                                    sql += " write_date = '%s'" % (datetime.now())
                                    sql += " WHERE id = %s" % (line.id)
                                    
                                    self._cr.execute(sql)
                                    self._cr.commit()
                                    self.invalidate_cache()
                                    
                                    print('------------------')
                                    print('ISR - 2')
                                    print('------------------')
                
                for line in self.line_ids:
                    if isr_retencion_account_id == line.account_id.id:
                        has_rec_isr_line = True
                        break
                
                if not has_rec_isr_line and not has_query_isr_line:
                    
                    
                    for line in self.line_ids:
                        
                        if line.account_id.id == self.partner_id.property_account_payable_id.id:
                            price_unit = line.price_unit + isr_amount
                            credit = line.credit - isr_amount
                            amount_currency = line.amount_currency + isr_amount
                            balance = line.balance + isr_amount
                            price_subtotal = line.price_subtotal + isr_amount
                            amount_residual = line.amount_residual + isr_amount
                            
                            amount_residual_currency = line.amount_residual_currency + isr_amount
                            price_total = line.price_total + isr_amount
                            
                            print('------------------')
                            print('ISR - 3')
                            print('------------------')
                            
                            sql = ""
                            sql += "UPDATE account_move_line"
                            sql += " SET price_unit = %s," % (price_unit)
                            sql += " credit = %s," % (credit)
                            sql += " amount_currency = %s," % (amount_currency)
                            sql += " balance = %s," % (balance)
                            sql += " price_subtotal = %s," % (price_subtotal)
                            sql += " amount_residual = %s," % (amount_residual)
                            sql += " amount_residual_currency = %s," % (amount_residual_currency)
                            sql += " price_total = %s," % (price_total)
                            sql += " write_uid = %s," % (self.env.user.id)
                            sql += " write_date = '%s'" % (datetime.now())
                            sql += " WHERE id = %s" % (line.id)
                            
                            self._cr.execute(sql)
                            self._cr.commit()
                            
                            self.invalidate_cache()

                    print('------------------')
                    print('ISR - 4')
                    print('------------------')

                    sql = ""
                    sql += "INSERT INTO account_move_line"
                    sql += " (move_id, move_name, date, parent_state, journal_id, company_id, company_currency_id,"
                    sql += " account_id, account_root_id, sequence, name, quantity, price_unit, discount, debit, "
                    sql += " credit, balance, amount_currency, price_subtotal, price_total, currency_id, partner_id,"
                    sql += " exclude_from_invoice_tab, create_uid, create_date, write_uid, write_date"
                    sql += ")"
                    sql += " VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
                    
                    move_date = datetime.now().date()
                    if self.date:
                        move_date = self.date
                    params = [self.id, self.name, move_date, self.state, self.journal_id.id, company_id.id, company_id.currency_id.id, isr_retencion_account_id, isr_retencion_account_root_id.id, "10", "Retencion de ISR", 1, isr_amount * -1, 0, 0, isr_amount, isr_amount * -1, isr_amount * -1, isr_amount * -1, isr_amount * -1, self.currency_id.id, self.partner_id.id, True, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
                    
                    self._cr.execute(sql, params)
                    self._cr.commit()
                    
                    print('------------------')
                    print('ISR - 5')
                    print('------------------')
                    
                self.invalidate_cache()
                
            else:
                
                print('----------------------')
                print('CLIENTE')
                print('----------------------')
                
                isr_retencion_account_data = False
                isr_retencion_account_id = False
                isr_retencion_account_root_id = False
                if company_id.isr_retencion_account_id:
                    if not company_id.isr_retencion_account_id.isr_sales_account_id:
                        raise ValidationError('Debe seleccionar la cuenta ISR ventas en el diario de retención del ISR')
                    isr_retencion_account_id = company_id.isr_retencion_account_id.isr_sales_account_id.id
                    isr_retencion_account_root_id = company_id.isr_retencion_account_id.isr_sales_account_id.root_id
                else:
                    raise ValidationError('Debe seleccionar el diario a utilizar con ISR')
                
            
                isr_amount = self.isr_withold_amount
                has_query_isr_line = False
                has_rec_isr_line = False     
                self.invalidate_cache()
                
                sql = ""
                sql += "SELECT id"
                sql += " FROM account_move_line"
                sql += " WHERE account_id = %s" % (isr_retencion_account_id)
                sql += " AND   move_id = %s" % (self.id)
                
                cr_log = sql_db.db_connect(self.env.cr.dbname).cursor()
                cr_log.execute(sql)
                
                operation_total = 0
                self.invalidate_cache()
                
                sql = ""
                sql += "SELECT credit"
                sql += " FROM account_move_line"
                sql += " WHERE credit > 0"
                sql += " AND   move_id = %s" % (self.id)
                
                cr_total = sql_db.db_connect(self.env.cr.dbname).cursor()
                cr_total.execute(sql)
                
                for query_data in cr_total.dictfetchall():
                    operation_total += query_data['credit']
                
                
                isr_line_counter = 0
                for query_data in cr_log.dictfetchall():
                    
                    print('------------------')
                    print(query_data)
                    print('------------------')

                    has_query_isr_line = True
                    isr_line_counter += 1
                    if isr_line_counter > 1:
                        sql = ""
                        sql = "DELETE FROM account_move_line WHERE id = %s;" % (query_data['id'])
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                    else:
                        
                        print('------------------')
                        print('ISR - 111111')
                        print('------------------')
                        
                        sql = ""
                        sql += "UPDATE account_move_line"
                        sql += " SET price_unit = %s," % (isr_amount * -1)
                        sql += " debit = %s," % (isr_amount)
                        sql += " amount_currency = %s," % (isr_amount)
                        sql += " balance = %s," % (isr_amount * -1)
                        sql += " price_subtotal = %s," % (isr_amount * -1)
                        sql += " price_total = %s," % (isr_amount * -1)
                        sql += " write_uid = %s," % (self.env.user.id)
                        sql += " write_date = '%s'" % (datetime.now())
                        sql += " WHERE id = %s" % (query_data['id'])
                        
                        self._cr.execute(sql)
                        self._cr.commit()
                        
                        print('------------------')
                        print('ISR - 2')
                        print('------------------')
                        
                        for line in self.line_ids:

                            if line.account_id.id == self.partner_id.property_account_receivable_id.id:
                                partner_amount = operation_total - isr_amount - iva_amount
                                price_unit = partner_amount * -1
                                credit = partner_amount
                                amount_currency = partner_amount
                                balance = partner_amount
                                price_subtotal = partner_amount * -1
                                amount_residual = partner_amount * -1
                                amount_residual_currency = partner_amount
                                
                                print('------------------')
                                print('ISR - 3')
                                print(operation_total, isr_amount, iva_amount)
                                print(partner_amount)
                                print('------------------')
                                
                                sql = ""
                                sql += "UPDATE account_move_line"
                                sql += " SET price_unit = %s," % (price_unit)
                                sql += " debit = %s," % (credit)
                                sql += " amount_currency = %s," % (amount_currency)
                                sql += " balance = %s," % (balance)
                                sql += " price_subtotal = %s," % (price_subtotal)
                                sql += " amount_residual = %s," % (amount_residual)
                                sql += " amount_residual_currency = %s," % (amount_residual_currency)
                                sql += " price_total = %s," % (price_total)
                                sql += " write_uid = %s," % (self.env.user.id)
                                sql += " write_date = '%s'" % (datetime.now())
                                sql += " WHERE id = %s" % (line.id)
                                
                                self._cr.execute(sql)
                                self._cr.commit()
                                self.invalidate_cache()
                                
                                print('------------------')
                                print('ISR - 4')
                                print('------------------')
                                
                
                for line in self.line_ids:
                    if isr_retencion_account_id == line.account_id.id:
                        has_rec_isr_line = True
                        break
                
                if not has_rec_isr_line and not has_query_isr_line:
                    
                    
                    for line in self.line_ids:
                        
                        if line.account_id.id == self.partner_id.property_account_receivable_id.id:
                            price_unit = line.price_unit + isr_amount
                            debit = line.debit - isr_amount
                            amount_currency = line.amount_currency - isr_amount
                            balance = line.balance - isr_amount
                            price_subtotal = line.price_subtotal + isr_amount
                            amount_residual = line.amount_residual - isr_amount
                            amount_residual_currency = line.amount_residual_currency - isr_amount
                            price_total = line.price_total + isr_amount
                            
                            print('------------------')
                            print('ISR - 5')
                            print('------------------')
                            
                            sql = ""
                            sql += "UPDATE account_move_line"
                            sql += " SET price_unit = %s," % (price_unit)
                            sql += " debit = %s," % (debit)
                            sql += " amount_currency = %s," % (amount_currency)
                            sql += " balance = %s," % (balance)
                            sql += " price_subtotal = %s," % (price_subtotal)
                            sql += " amount_residual = %s," % (amount_residual)
                            sql += " amount_residual_currency = %s," % (amount_residual_currency)
                            sql += " price_total = %s," % (price_total)
                            sql += " write_uid = %s," % (self.env.user.id)
                            sql += " write_date = '%s'" % (datetime.now())
                            sql += " WHERE id = %s" % (line.id)
                            
                            print('-------------- UPDATE PARTNER CLIENT')
                            print(sql)
                            print('-------------- UPDATE PARTNER CLIENT')
                            
                            self._cr.execute(sql)
                            self._cr.commit()
                            
                            self.invalidate_cache()

                    sql = ""
                    sql += "INSERT INTO account_move_line"
                    sql += " (move_id, move_name, date, parent_state, journal_id, company_id, company_currency_id,"
                    sql += " account_id, account_root_id, sequence, name, quantity, price_unit, discount, debit, "
                    sql += " credit, balance, amount_currency, price_subtotal, price_total, currency_id, partner_id,"
                    sql += " exclude_from_invoice_tab, create_uid, create_date, write_uid, write_date"
                    sql += ")"
                    sql += " VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
                    
                    move_date = datetime.now().date()
                    if self.date:
                        move_date = self.date
                    params = [self.id, self.name, move_date, self.state, self.journal_id.id, company_id.id, company_id.currency_id.id, isr_retencion_account_id, isr_retencion_account_root_id.id, "10", "Retencion de ISR", 1, isr_amount * -1, 0, isr_amount, 0, isr_amount, isr_amount, isr_amount * -1, isr_amount * -1, self.currency_id.id, self.partner_id.id, True, self.env.user.id, datetime.now(), self.env.user.id, datetime.now()]
                    
                    self._cr.execute(sql, params)
                    self._cr.commit()
                    
                
                self.invalidate_cache()
        
        if self.iva_withold_amount > 0 or self.isr_withold_amount > 0:
            if not self.invoice_date:
                self.invoice_date = fields.Date.context_today(self)
        
        
        return True

    @api.model_create_multi
    def create(self, vals_list):
        company_id = self.env.company
        
        for vals in vals_list:
            
            # IVA Process
            if "iva_withold_amount" in vals:
                invoice_type = "out_invoice"
                if "provider_invoice_number" in vals:
                    if vals["provider_invoice_number"]:
                        invoice_type = "in_invoice"
                
                if vals['iva_withold_amount']:
                    iva_retencion_account_data = False
                    iva_retencion_account_id = False
                    iva_retencion_account_root_id = False
                    if company_id.iva_retencion_account_id:
                        account_id = False
            
                        if invoice_type == 'in_invoice':
                            if not company_id.iva_retencion_account_id.iva_purchase_account_id:
                                raise ValidationError('Debe seleccionar el la cuenta a utilizar con retencion de IVA en compras')
                            iva_retencion_account_id = company_id.iva_retencion_account_id.iva_purchase_account_id.id
                            iva_retencion_account_root_id = company_id.iva_retencion_account_id.iva_purchase_account_id.root_id
                            
                        if invoice_type == 'out_invoice':
                            if not company_id.iva_retencion_account_id.iva_sales_account_id:
                                raise ValidationError('Debe seleccionar el la cuenta a utilizar con retencion de IVA en ventas')
                        
                            iva_retencion_account_id = company_id.iva_retencion_account_id.iva_sales_account_id.id
                            iva_retencion_account_root_id = company_id.iva_retencion_account_id.iva_sales_account_id.root_id
                    else:
                        raise ValidationError('Debe seleccionar el diario a utilizar con IVA')
                    
                    iva_amount = vals['iva_withold_amount']
                    if 'currency_id' in vals and 'company_id':
                        company_currency = company_id.currency_id.id
                        has_foreign_currency = vals['currency_id'] and vals['currency_id'] != company_currency
                        if has_foreign_currency:
                            currency_amount = iva_amount
                            line_currency = company_currency
                        else:
                            line_currency = vals['currency_id']
                            currency_amount = iva_amount
                    else:
                        currency_amount = iva_amount
                        company_currency = company_id.currency_id.id
                        line_currency = company_currency
                    
                    current_lines = vals['line_ids']
                    partner_data = self.env['res.partner'].search([
                        ('id', '=', vals['partner_id'])
                    ])
                    partner_account_id = False
                    if partner_data:
                        if 'provider_invoice_serial' in vals:
                            if vals['provider_invoice_serial']:
                                partner_account_id = partner_data.property_account_payable_id.id
                            else:
                                partner_account_id = partner_data.property_account_receivable_id.id
                    
                    if partner_data.tax_withholding_iva == "iva_forgiveness" and move_type == 'out_invoice':
                        if not company_id.iva_retencion_account_id:
                            raise ValidationError('Debe seleccionar el diario a utilizar con IVA')
                        else:
                            if not company_id.iva_retencion_account_id.iva_forgiveness_account_id:
                                raise ValidationError('Debe seleccionar el la cuenta de exención en el diario de retenciones de IVA.')
                            else:
                                iva_retencion_account_id = company_id.iva_retencion_account_id.iva_forgiveness_account_id.id
                                partner_account_id = partner_data.property_account_payable_id.id
                                
                                
                                print(partner_account_id)
                                for line in current_lines:
                                    
                                    if line[2]['account_id'] == partner_account_id:
                                        positive_amount = iva_amount
                                        negative_amount = iva_amount * -1
                                        price_unit = line[2]['price_unit'] + iva_amount
                                        credit = line[2]['credit'] - iva_amount
                                        amount_currency = line[2]['amount_currency'] + iva_amount
                                        line[2].update(
                                            {
                                                "price_unit": price_unit, 
                                                "credit": credit,
                                                "amount_currency": amount_currency
                                            }
                                        )    
                                vals.update({"line_ids": current_lines})
                                
                                inv_lines = vals['line_ids']
                                print(inv_lines)
                                new_lines = []
                                for line in inv_lines:
                                    line_data = line[2]
                                    new_lines.append(line_data)
                                
                                move_date = datetime.now().date()
                                if 'date' in vals:
                                    move_date = vals['date']
                                
                                ex_iva_line = {
                                    "account_id": iva_retencion_account_id,
                                    "name": "Exención de ISR",
                                    "quantity": 1,
                                    "price_unit": iva_amount * -1,
                                    "discount": 0,
                                    "debit": 0,
                                    "credit": iva_amount,
                                    "amount_currency": iva_amount * -1,
                                    "currency_id": line_currency,
                                    "partner_id": vals["partner_id"],
                                    "date": move_date,
                                    "tax_exigible": True,
                                    "exclude_from_invoice_tab": True,
                                    
                                }
                                new_lines.append(ex_iva_line)
                                print(new_lines)
                                vals.update({"line_ids": [(0, 0, line) for line in new_lines]})
                                
                                print('------------------- EXC IVA')
                                        
                            
                    print('----------------------')
                    print(vals)
                    print(partner_account_id)
                    print('----------------------')
                    
                    for line in current_lines:
                        
                        if line[2]['account_id'] == partner_account_id:
                            if 'provider_invoice_serial' in vals:
                                if vals['provider_invoice_serial']:
                                    if vals['type_invoice'] != 'special_invoice':
                                        positive_amount = iva_amount
                                        negative_amount = iva_amount * -1
                                        price_unit = line[2]['price_unit'] + iva_amount
                                        credit = line[2]['credit'] - iva_amount
                                        amount_currency = line[2]['amount_currency'] + iva_amount
                                        
                                        print('--------------- PROV')
                                        print(price_unit)
                                        print(credit)
                                        print(amount_currency)
                                        print('--------------- PROV')
                                        
                                        line[2].update(
                                            {
                                                "price_unit": price_unit, 
                                                "credit": credit, 
                                                "amount_currency": amount_currency
                                            }
                                        )    
                                else:
                                    positive_amount = iva_amount
                                    negative_amount = iva_amount * -1
                                    price_unit = line[2]['price_unit'] + iva_amount
                                    credit = line[2]['debit'] - iva_amount
                                    amount_currency = line[2]['amount_currency'] - iva_amount
                                    
                                    
                                    print('--------------- CLIENT')
                                    print(price_unit)
                                    print(credit)
                                    print(amount_currency)
                                    print('--------------- CLIENT')
                                    
                                    line[2].update(
                                        {
                                            "price_unit": price_unit, 
                                            "debit": credit, 
                                            "amount_currency": amount_currency
                                        }
                                    )    
                    vals.update({"line_ids": current_lines})
                    
                    inv_lines = vals['line_ids']
                    new_lines = []
                    for line in inv_lines:
                        line_data = line[2]
                        new_lines.append(line_data)
                    
                    if 'provider_invoice_serial' in vals:
                        move_date = datetime.now().date()
                        if 'date' in vals:
                            move_date = vals['date']
                        if vals['provider_invoice_serial']:
                            if vals['type_invoice'] != 'special_invoice':
                                iva_line = {
                                    "account_id": iva_retencion_account_id,
                                    "name": "Retencion de IVA",
                                    "quantity": 1,
                                    "price_unit": iva_amount,
                                    "discount": 0,
                                    "debit": 0,
                                    "credit": iva_amount,
                                    "amount_currency": iva_amount,
                                    "currency_id": line_currency,
                                    "partner_id": vals["partner_id"],
                                    "exclude_from_invoice_tab": True,
                                    "date": move_date
                                }
                        else:
                        
                            iva_line = {
                                "account_id": iva_retencion_account_id,
                                "name": "Retencion de IVA",
                                "quantity": 1,
                                "price_unit": iva_amount * -1,
                                "discount": 0,
                                "debit": iva_amount,
                                "credit": 0,
                                "amount_currency": iva_amount,
                                "currency_id": line_currency,
                                "partner_id": vals["partner_id"],
                                "exclude_from_invoice_tab": True,
                                "date": move_date
                            }
                    if vals['type_invoice'] != 'special_invoice':
                        new_lines.append(iva_line)
                        print('LINES DATA', new_lines)
                        #raise ValidationError('STOP!')
                        vals.update({"line_ids": [(0, 0, line) for line in new_lines]})
                    
                    
            # ISR Process
            if "isr_withold_amount" in vals and "provider_invoice_number" in vals:
            
                if vals['isr_withold_amount']:
                    if vals["provider_invoice_number"]:
                        if vals['type_invoice'] != 'special_invoice':
                            line_currency = False
                            currency_amount = 0
                            isr_amount = vals['isr_withold_amount']
                            if 'currency_id' in vals:
                                company_currency = company_id.currency_id.id
                                has_foreign_currency = vals['currency_id'] and vals['currency_id'] != company_currency
                                if has_foreign_currency:
                                    currency_amount = isr_amount
                                    line_currency = company_currency
                                else:
                                    line_currency = vals['currency_id']
                                    currency_amount = isr_amount
                            else:
                                currency_amount = isr_amount
                                company_currency = company_id.currency_id.id
                                line_currency = company_currency
                            if company_id.isr_retencion_account_id:
                                isr_retencion_account_id = company_id.isr_retencion_account_id.isr_purchase_account_id.id
                            else:
                                print('ISR----', company_id.isr_retencion_account_id, company_id.name, vals)
                                raise ValidationError('Debe seleccionar un diario de retención de ISR en la configuración general')
                            
                            current_lines = vals['line_ids']
                            partner_data = self.env['res.partner'].search([
                                ('id', '=', vals['partner_id'])
                            ])
                            partner_account_id = False
                            if partner_data:
                                partner_account_id = partner_data.property_account_payable_id.id
                            for line in current_lines:
                                
                                if line[2]['account_id'] == partner_account_id:
                                    positive_amount = isr_amount
                                    negative_amount = isr_amount * -1
                                    price_unit = line[2]['price_unit'] + isr_amount
                                    credit = line[2]['credit'] - isr_amount
                                    #balance = line[2]['balance'] + isr_amount
                                    amount_currency = line[2]['amount_currency'] + isr_amount
                                    #price_subtotal = line[2]['price_subtotal'] + isr_amount
                                    #price_total = line[2]['price_total'] + isr_amount
                                    line[2].update(
                                        {
                                            "price_unit": price_unit, 
                                            "credit": credit, 
                                            #"balance": balance, 
                                            "amount_currency": amount_currency
                                            #"price_subtotal": price_subtotal,
                                            #"price_total": price_total
                                        }
                                    )    
                            vals.update({"line_ids": current_lines})
                            
                            inv_lines = vals['line_ids']
                            new_lines = []
                            for line in inv_lines:
                                line_data = line[2]
                                new_lines.append(line_data)
                            
                            move_date = datetime.now().date()
                            if 'date' in vals:
                                move_date = vals['date']
                            isr_line = {
                                "account_id": isr_retencion_account_id,
                                "name": "Retencion de ISR",
                                "quantity": 1,
                                "price_unit": isr_amount * -1,
                                "discount": 0,
                                "debit": 0,
                                "credit": isr_amount,
                                "amount_currency": isr_amount * -1,
                                "currency_id": line_currency,
                                "partner_id": vals["partner_id"],
                                "date": move_date,
                                "exclude_from_invoice_tab": True,
                                
                            }
                            new_lines.append(isr_line)
                            print('Final Lines', new_lines)
                            vals.update({"line_ids": [(0, 0, line) for line in new_lines]})
                            
                    else:
                        line_currency = False
                        currency_amount = 0
                        isr_amount = vals['isr_withold_amount']
                        if 'currency_id' in vals:
                            company_currency = company_id.currency_id.id
                            has_foreign_currency = vals['currency_id'] and vals['currency_id'] != company_currency
                            if has_foreign_currency:
                                currency_amount = isr_amount
                                line_currency = company_currency
                            else:
                                line_currency = vals['currency_id']
                                currency_amount = isr_amount
                        else:
                            currency_amount = isr_amount
                            company_currency = company_id.currency_id.id
                            line_currency = company_currency
                        if company_id.isr_retencion_account_id:
                            isr_retencion_account_id = company_id.isr_retencion_account_id.isr_sales_account_id.id                            
                        else:
                            print('ISR----', company_id.isr_retencion_account_id, company_id.name, vals)
                            raise ValidationError('Debe seleccionar un diario de retención de ISR en la configuración general')
                        
                        current_lines = vals['line_ids']
                        partner_data = self.env['res.partner'].search([
                            ('id', '=', vals['partner_id'])
                        ])
                        partner_account_id = False
                        if partner_data:
                            partner_account_id = partner_data.property_account_receivable_id.id
                        for line in current_lines:
                            
                            if line[2]['account_id'] == partner_account_id:
                                positive_amount = isr_amount
                                negative_amount = isr_amount * -1
                                price_unit = line[2]['price_unit'] + isr_amount
                                debit = line[2]['debit'] - isr_amount
                                
                                amount_currency = line[2]['amount_currency'] - isr_amount
                                
                                line[2].update(
                                    {
                                        "price_unit": price_unit, 
                                        "debit": debit,                                         
                                        "amount_currency": amount_currency
                                    }
                                )    
                        vals.update({"line_ids": current_lines})
                        
                        inv_lines = vals['line_ids']
                        new_lines = []
                        for line in inv_lines:
                            line_data = line[2]
                            new_lines.append(line_data)
                        
                        move_date = datetime.now().date()
                        if 'date' in vals:
                            move_date = vals['date']
                            
                        isr_line = {
                            "account_id": isr_retencion_account_id,
                            #"sequence": line_data["sequence"],
                            "name": "Retencion de ISR",
                            "quantity": 1,
                            "price_unit": isr_amount * -1,
                            "discount": 0,
                            "debit": isr_amount,
                            "credit": 0,
                            "amount_currency": isr_amount * -1,
                            #"date_maturity": line_data["date_maturity"],
                            "currency_id": line_currency,
                            "partner_id": vals["partner_id"],
                            "date": move_date,
                            #"product_uom_id": line_data["product_uom_id"],
                            #"product_id": line_data["product_id"],
                            #"payment_id": line_data["payment_id"],
                            #"tax_ids": line_data["tax_ids"],
                            #"tax_base_amount": line_data['tax_base_amount'],
                            
                            #"tax_repartition_line_id": line_data["tax_repartition_line_id"],
                            #"tag_ids": line_data["tag_ids"],
                            #"analytic_account_id": new_line["analytic_account_id"],
                            #"analytic_tag_ids": line_data["analytic_tag_ids"],
                            #"recompute_tax_line": line_data["recompute_tax_line"],
                            #"display_type": line_data["display_type"],
                            #"is_rounding_line": line_data["is_rounding_line"],
                            "exclude_from_invoice_tab": True,
                            #"purchase_line_id": line_data["purchase_line_id"],
                            #"predict_from_name": line_data["predict_from_name"],
                            #"predict_override_default_account": line_data["predict_override_default_account"]
                        }
                        print('LINE ADDED----------------------------------------')
                        print(isr_line)
                        new_lines.append(isr_line)
                        print('Final Lines', new_lines)
                        vals.update({"line_ids": [(0, 0, line) for line in new_lines]})
        res = super(AccountMove, self).create(vals_list)
        #for account_move_line in res.line_ids:
        #    print('Statement', account_move_line.statement_line_id)
        return res

    def get_show_analytic_lines(self):
        for rec in self:
            rec.show_analytic_lines = self.env.user.company_id.show_analytic_lines

    def get_analytic_lines(self):
        assigned_value = False
        for rec in self:
            rec.ref_analytic_line_ids = False
            assigned_value = True
            if rec.line_ids:
                rec.ref_analytic_line_ids = rec.line_ids.analytic_line_ids

    @api.onchange('type_invoice')
    def onchange_type_invoice(self):
        if 'fel_gt_invoice_type' in self.env['account.move']._fields:
            if self.type_invoice == 'special_invoice':
                self.fel_gt_invoice_type = "especial"
            elif self.type_invoice == 'normal_invoice':
                self.fel_gt_invoice_type = "normal"
            else:
                self.fel_gt_invoice_type = self.type_invoice

    @api.model
    def _set_initial_values(self):
        initial_iva_withhold = 'no_witholding'
        default_move_type = self.default_get(['move_type'])
        
        if default_move_type['move_type'] == 'out_invoice':
            if self.partner_id:
                if self.partner_id.company_type == "company":
                    initial_iva_withhold = self.partner_id.tax_withholding_iva
                else:
                    if self.partner_id.parent_id:
                        initial_iva_withhold = self.partner_id.parent_id.tax_withholding_iva
                    else:
                        initial_iva_withhold = self.partner_id.tax_withholding_iva
                

        if default_move_type['move_type'] == 'in_invoice':
            print('Company', self.env.company.name)
            initial_iva_withhold = self.env.company.tax_withholding_iva

        return initial_iva_withhold

    @api.constrains('reference')
    def _validar_factura_proveedor(self):
        if self.reference:
            facturas = self.search([('reference', '=', self.reference), ('partner_id', '=', self.partner_id.id), ('move_type', '=', 'in_invoice')])
            if len(facturas) > 1:
                raise ValidationError("Ya existe una factura con ese mismo numero.")
    
    def _compute_base_line_taxes_gt_extra(self, base_line):
        ''' Compute taxes amounts both in company currency / foreign currency as the ratio between
            amount_currency & balance could not be the same as the expected currency rate.
            The 'amount_currency' value will be set on compute_all(...)['taxes'] in multi-currency.
            :param base_line:   The account.move.line owning the taxes.
            :return:            The result of the compute_all method.
            '''
            
        move = base_line.move_id

        if move.is_invoice(include_receipts=True):
            handle_price_include = True
            sign = -1 if move.is_inbound() else 1
            quantity = base_line.quantity
            is_refund = move.move_type in ('out_refund', 'in_refund')
            price_unit_wo_discount = sign * base_line.price_unit * (1 - (base_line.discount / 100.0))
        else:
            handle_price_include = False
            quantity = 1.0
            tax_type = base_line.tax_ids[0].type_tax_use if base_line.tax_ids else None
            is_refund = (tax_type == 'sale' and base_line.debit) or (tax_type == 'purchase' and base_line.credit)
            price_unit_wo_discount = base_line.amount_currency

        return base_line.tax_ids._origin.with_context(force_sign=move._get_tax_force_sign()).compute_all(
            price_unit_wo_discount,
            currency=base_line.currency_id,
            quantity=quantity,
            product=base_line.product_id,
            partner=base_line.partner_id,
            is_refund=is_refund,
            handle_price_include=handle_price_include,
            include_caba_tags=move.always_tax_exigible,
        )

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.debit',
        'line_ids.credit',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id')
    def _compute_amount(self):

        res = super(AccountMove, self)._compute_amount()
        
        for move in self:

            move.tax_withold_amount = 0
            
            
            if move.is_invoice(include_receipts=False):

                #company_iva_agent_type = self.env.user.company_id.tax_withholding_iva
                company_iva_agent_type = self.env.company.tax_withholding_iva
                move.tax_withold_amount = 0
                move.tax_withholding_amount_iva = 0
                
                iva_tax_id = 0
                if 'fel_tax' in self.env['account.tax'].fields_get():
                    iva_tax_data = self.env['account.tax'].search([
                        ('fel_tax', '=', 'IVA')
                    ], limit=1)
                    
                    if iva_tax_data:
                        iva_tax_id = iva_tax_data.id
                else:
                    iva_tax_data = self.env['account.tax'].search([
                        ('name', 'like', 'IVA Por Cobrar')
                    ], limit=1)
                    if iva_tax_data:
                        iva_tax_id = iva_tax_data.id
                
                tax_summary = 0
                iva_withhold_amount = 0
                company_currency = self.company_id.currency_id
                has_foreign_currency = self.currency_id and self.currency_id != company_currency

                if not has_foreign_currency:
                    move.amount_total = move.amount_untaxed + move.amount_tax - move.tax_withholding_price

                for invoice in self:
                    
                    partner_vat = invoice.partner_id.vat
                    if partner_vat:
                        partner_vat = partner_vat.upper()
                    if invoice.tax_withold_amount:
                        invoice.tax_withold_amount = 0

                    if invoice.move_type == 'out_invoice' or invoice.move_type == 'in_refund':
                        sign = 1
                    else:
                        sign = -1

                    #invoice.amount_tax = tax_summary
                    if not has_foreign_currency:
                        invoice.amount_total = sign * (invoice.amount_untaxed_signed + invoice.amount_tax_signed - invoice.tax_withholding_price)

                    isr_withold_type = ''

                    # VENTA

                    if invoice.move_type == 'out_invoice':

                        isr_withold_type = self.company_id.tax_withholding_isr
                        
                        """if invoice.partner_id.company_type == "company":
                            isr_withold_type = invoice.partner_id.tax_withholding_isr
                        else:
                            if invoice.partner_id.parent_id:
                                isr_withold_type = invoice.partner_id.parent_id.tax_withholding_isr
                            else:
                                isr_withold_type = invoice.partner_id.tax_withholding_isr"""

                        if invoice.partner_id.company_type == "company":
                            partner_iva_agent_type = invoice.partner_id.tax_withholding_iva
                        else:
                            if invoice.partner_id.parent_id:
                                partner_iva_agent_type = invoice.partner_id.parent_id.tax_withholding_iva
                            else:
                                partner_iva_agent_type = invoice.partner_id.tax_withholding_iva

                        # IVA RETENCIÓN
                        # SI AMBOS, CLIENTE Y PROVEEDOR, SON AGENTES RETENEDORES DE IVA NO SE REALIZA LA RETENCIÓN
                        
                        iva_withhold_amount = 0
                        if partner_iva_agent_type == 'iva_forgiveness':
                            for invoice_line in invoice.invoice_line_ids:
                                timbre_tax_fel = False
                                if 'fel_timbre_tax' in self.env['account.tax']._fields:
                                    if invoice_line.tax_ids:
                                        for tax in invoice_line.tax_ids:
                                            if tax.fel_timbre_tax:
                                                timbre_tax_fel = True
                                                
                                line_amount = invoice_line.price_unit * invoice_line.quantity
                                if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                    iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                    if not timbre_tax_fel:
                                        iva_withhold_amount += iva_amount
                                    else:
                                        timbre_amount = invoice_line.price_total / 1.125
                                        timbre_amount = timbre_amount * 0.005
                                        iva_amount = iva_amount - timbre_amount
                                        iva_withhold_amount += iva_amount
                                    
                                    invoice.tax_withholding_amount_iva = iva_withhold_amount
                                    invoice.iva_withold_amount = iva_withhold_amount
                        
                        if partner_iva_agent_type != 'no_witholding' and company_iva_agent_type == 'no_witholding' and invoice.journal_id.is_receipt_journal is False:
                            
                            if isr_withold_type == 'small_taxpayer_withholding' and invoice.amount_total > 2500:
                                for invoice_line in invoice.invoice_line_ids:
                                    total_amount = invoice_line.price_total
                                    iva_amount = total_amount * 0.05
                                    iva_withhold_amount += iva_amount
                            elif invoice.type_invoice == 'special_invoice' and invoice.amount_total > 2500:
                                for invoice_line in invoice.invoice_line_ids:
                                    iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                    iva_withhold_amount += iva_amount
                            else:
                                if partner_iva_agent_type == 'export' and invoice.amount_total > 2500:
                                    iva_withhold_amount = 0
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity

                                        # EVERY PRODUCT CATEGORY TAX PERCENTAGE IS SEPARATE IN CASE OF FUTHER LAW CHANGES

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'agriculture':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.65
                                            iva_withhold_amount += iva_amount

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'not_agriculture':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            print('IVA', iva_amount)
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                                
                                
                                if partner_iva_agent_type == 'decree_28_89' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.65
                                            iva_withhold_amount += iva_amount

                                if partner_iva_agent_type == 'public_sector' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.25
                                            iva_withhold_amount += iva_amount

                                if partner_iva_agent_type == 'credit_cards_companies' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'payment_creditholders':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'fuel_payments':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.015
                                            iva_withhold_amount += iva_amount

                                if partner_iva_agent_type == 'special_taxpayer' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:

                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount
                                            
                                        else:
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount
                                            
                                if partner_iva_agent_type == 'special_taxpayer_export' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:

                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.80
                                            iva_withhold_amount += iva_amount
                                            
                                        else:
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.80
                                            iva_withhold_amount += iva_amount

                                if partner_iva_agent_type == 'others' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount
                                        else:
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                            # if invoice.tax_withholding_amount_iva :
                            invoice.tax_withholding_amount_iva = iva_withhold_amount
                            invoice.iva_withold_amount = iva_withhold_amount
                            if not has_foreign_currency:
                                invoice.amount_total = invoice.amount_total - iva_withhold_amount

                    # COMPRA

                    if invoice.move_type == 'in_invoice':
                        
                        if invoice.partner_id.company_type == "company":
                            isr_withold_type = invoice.partner_id.tax_withholding_isr
                        else:
                            if invoice.partner_id.parent_id:
                                isr_withold_type = invoice.partner_id.parent_id.tax_withholding_isr
                            else:
                                isr_withold_type = invoice.partner_id.tax_withholding_isr

                        
                        if invoice.partner_id.company_type == "company":
                            partner_iva_agent_type = invoice.partner_id.tax_withholding_iva
                        else:
                            partner_iva_agent_type = invoice.partner_id.parent_id.tax_withholding_iva

                        # IVA RETENECION

                        if company_iva_agent_type != 'no_witholding' and partner_iva_agent_type == 'no_witholding' and invoice.journal_id.is_receipt_journal is False:
                            iva_withhold_amount = 0
                            iva_amount = 0
                            for invoice_line in invoice.invoice_line_ids:
                                
                                compute_all_vals = invoice._compute_base_line_taxes_gt_extra(invoice_line)
                                
                                if 'taxes' in compute_all_vals:
                                    for tax_data in compute_all_vals['taxes']:
                                        if tax_data['id'] == iva_tax_id:
                                            iva_amount += tax_data['amount']

                            if isr_withold_type == 'small_taxpayer_withholding' and invoice.amount_total > 2500:
                                for invoice_line in invoice.invoice_line_ids:
                                    
                                    total_amount = invoice_line.price_total
                                    iva_amount = total_amount * 0.05
                                    iva_withhold_amount += iva_amount
                            elif invoice.type_invoice == 'special_invoice' and invoice.amount_total > 2500:
                                for invoice_line in invoice.invoice_line_ids:
                                    if iva_amount == 0:
                                        iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                    iva_withhold_amount += iva_amount

                            else:
                                if company_iva_agent_type == 'export' and invoice.amount_total > 2500:
                                    iva_withhold_amount = 0
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity

                                        # EVERY PRODUCT CATEGORY TAX PERCENTAGE IS SEPARATE IN CASE OF FUTHER LAW CHANGES

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'agriculture':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.65
                                            iva_withhold_amount += iva_amount

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'not_agriculture':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                                if company_iva_agent_type == 'decree_28_89' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.65
                                            iva_withhold_amount += iva_amount

                                if company_iva_agent_type == 'public_sector' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.25
                                            iva_withhold_amount += iva_amount

                                if company_iva_agent_type == 'credit_cards_companies' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'payment_creditholders':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'fuel_payments':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.015
                                            iva_withhold_amount += iva_amount

                                if company_iva_agent_type == 'special_taxpayer' and invoice.amount_total > 2500:
                                    for invoice_line in invoice.invoice_line_ids:
                                        
                                        line_amount = invoice_line.price_unit * invoice_line.quantity
                                        if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                            if iva_amount == 0:
                                                iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                            iva_amount = iva_amount * 0.15
                                            iva_withhold_amount += iva_amount

                                if company_iva_agent_type == 'others' and invoice.amount_total > 2500:
                                        
                                    line_amount = invoice_line.price_unit * invoice_line.quantity
                                    if invoice_line.product_id.product_tmpl_id.categ_id.sat_iva_type_product == 'good_services':
                                        if iva_amount == 0:
                                            iva_amount = invoice_line.price_total - invoice_line.price_subtotal
                                        iva_amount = iva_amount * 0.15
                                        iva_withhold_amount += iva_amount

                            # if invoice.tax_withholding_amount_iva:
                            invoice.tax_withholding_amount_iva = iva_withhold_amount
                            invoice.iva_withold_amount = iva_withhold_amount
                            if not has_foreign_currency:
                                invoice.amount_total = invoice.amount_total - iva_withhold_amount

                    
                    if isr_withold_type == 'definitive_withholding' and invoice.journal_id.is_receipt_journal is False and invoice.partner_id.vat != False and partner_vat != "CF":
                        base_amount = invoice.amount_untaxed
                        rate = 1
                        if invoice.currency_id.id != self.env.company.currency_id.id:
                            
                            rate = 1/ invoice.conversion_rate_ref if invoice.conversion_rate_ref > 0 else 1
                            base_amount = invoice.amount_untaxed / rate  #SE HACE LA CONVERSIÓN SOLO PARA QUE CUMPLA LAS CONDICIONES PARA EL CÁLCULO
                            
                        has_taxes = False
                        for move_line in invoice.line_ids:
                            if move_line.tax_line_id:
                                has_taxes = True
                        if not has_taxes:
                            base_amount = invoice.amount_untaxed / 1.12
                            base_amount = round(base_amount, 2)
                        
                        isr_amount = 0
                        if base_amount > 30000.00:
                            isr_amount = 0
                            isr_amount = Decimal(float(isr_amount))
                            base_amount = base_amount - 30000
                            isr_amount = (((base_amount * 7) / 100.00) + 1500.00)
                            if invoice.currency_id.id != self.env.company.currency_id.id:
                                
                                isr_amount = isr_amount / invoice.conversion_rate_ref if invoice.conversion_rate_ref > 0 else 1
                                
                            isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                            invoice.tax_withold_amount = isr_amount
                            invoice.amount_total = invoice.amount_total - invoice.tax_withold_amount
                        elif base_amount >= 2500.00 and base_amount <= 30000.00:
                            isr_amount = 0
                            isr_amount = Decimal(float(isr_amount))
                            isr_amount = ((base_amount * 5) / 100.00)
                            isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                            invoice.tax_withold_amount = isr_amount
                            invoice.amount_untaxed = sum(line.price_subtotal for line in invoice.invoice_line_ids)
                            if not has_taxes:
                                invoice.amount_untaxed = invoice.amount_untaxed - float(isr_amount)
                            invoice.amount_total = invoice.amount_total - invoice.tax_withold_amount


                        if invoice.type_invoice == 'special_invoice':
                            if base_amount > 30000.00:
                                isr_amount = 0
                                isr_amount = Decimal(float(isr_amount))
                                base_amount = base_amount - 30000
                                isr_amount = (((base_amount * 7) / 100.00) + 1500.00)
                                isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                                invoice.tax_withold_amount = isr_amount
                                invoice.amount_total = invoice.amount_total - invoice.tax_withold_amount
                            elif base_amount >= 2500.00 and base_amount <= 30000.00:
                                isr_amount = 0
                                isr_amount = Decimal(float(isr_amount))
                                isr_amount = ((base_amount * 5) / 100.00)
                                isr_amount = Decimal(isr_amount).quantize(Decimal('0.01'), ROUND_HALF_UP)
                                invoice.tax_withold_amount = isr_amount
                                invoice.amount_untaxed = sum(line.price_subtotal for line in invoice.invoice_line_ids)
                                if not has_taxes:
                                    invoice.amount_untaxed = invoice.amount_untaxed - float(isr_amount)
                                invoice.amount_total = invoice.amount_total - invoice.tax_withold_amount
                            
                        invoice.isr_withold_amount = isr_amount

                    if invoice.type_invoice == "special_invoice" and iva_withhold_amount == 0:
                        invoice.amount_total = invoice.amount_untaxed + invoice.amount_tax

            if move.is_invoice(include_receipts=True) and move.capitalization_move_id:
                move.tax_withold_amount = 0
                move.tax_withholding_amount_iva = 0
            
            if not move.is_invoice(include_receipts=True) and not move.capitalization_move_id:
                move.tax_withold_amount = 0
                move.tax_withholding_amount_iva = 0        
                    #    move.amount_residual = move.amount_residual - move.tax_withold_amount

                    #if move.tax_withholding_amount_iva > 0:
            
            if move.is_invoice(include_receipts=True) and move.payment_state != 'paid' and move.payment_state != 'partial' and not move.capitalization_move_id:
                    if move.amount_residual != move.amount_total:
                        if move.iva_withold_amount > 0:
                            move.amount_residual = move.amount_total
                            move.amount_residual_signed = move.amount_total

                        if move.isr_withold_amount > 0:
                            move.amount_residual = move.amount_total
                            move.amount_residual_signed = move.amount_total
            
                    #    move.amount_residual = move.amount_residual - move.tax_withholding_amount_iva
            #    else:
            #        move.tax_withholding_amount_iva = 0
            #else:
            #    move.tax_withold_amount = 0
            #    move.tax_withholding_amount_iva = 0
 
    @api.constrains('inicial_rango', 'final_rango')
    def _validar_rango(self):
        if self.diario_facturas_por_rangos:
            if int(self.final_rango) < int(self.inicial_rango):
                raise ValidationError('El número inicial del rango es mayor que el final.')
            cruzados = self.search([('serie_rango', '=', self.serie_rango), ('inicial_rango', '<=', self.inicial_rango), ('final_rango', '>=', self.inicial_rango)])
            if len(cruzados) > 1:
                raise ValidationError('Ya existe otra factura con esta serie y en el mismo rango')
            cruzados = self.search([('serie_rango', '=', self.serie_rango), ('inicial_rango', '<=', self.final_rango), ('final_rango', '>=', self.final_rango)])
            if len(cruzados) > 1:
                raise ValidationError('Ya existe otra factura con esta serie y en el mismo rango')
            cruzados = self.search([('serie_rango', '=', self.serie_rango), ('inicial_rango', '>=', self.inicial_rango), ('inicial_rango', '<=', self.final_rango)])
            if len(cruzados) > 1:
                raise ValidationError('Ya existe otra factura con esta serie y en el mismo rango')

            self.name = "{}-{} al {}-{}".format(self.serie_rango, self.inicial_rango, self.serie_rango, self.final_rango)

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        response = super(AccountMove, self)._onchange_partner_id()
        company_iva_agent_type = self.env.user.company_id.tax_withholding_iva
        if self.partner_id:
            isr_withold_type = ""
            iva_withold_type = "no_witholding"

            if self.move_type == 'in_invoice':
                if self.partner_id.company_type == "company":
                    isr_withold_type = self.partner_id.tax_withholding_isr
                else:
                    if self.partner_id.parent_id:
                        isr_withold_type = self.partner_id.parent_id.tax_withholding_isr
                    else:
                        isr_withold_type = self.partner_id.tax_withholding_isr
            
            if self.move_type == 'out_invoice':
                isr_withold_type = self.company_id.tax_withholding_isr
                

            self.tax_withholding_isr = isr_withold_type

            if self.partner_id.tax_withholding_isr == "small_taxpayer_withholding" and self.move_type == 'in_invoice':

                for invoice_lines in self.invoice_line_ids:
                    invoice_lines.tax_ids = False

                move_lines = []
                for move_line in self.line_ids:
                    if move_line.tax_line_id.id is False:
                        move_lines.append(move_line.id)

                self.line_ids = move_lines
            else:

                default_tax = False
                if self.move_type == 'out_invoice':
                    default_tax = self.env.user.company_id.account_purchase_tax_id
                if self.move_type == 'in_invoice':
                    default_tax = self.env.user.company_id.account_sale_tax_id

                for invoice_lines in self.invoice_line_ids:
                    if len(invoice_lines.tax_ids) == 0:

                        tax_ids = []
                        if invoice_lines.product_id.product_tmpl_id.taxes_id.id is False:
                            tax_ids.append(default_tax.id)
                            invoice_lines.tax_ids = default_tax

                            for line in invoice_lines:
                                if not line.product_id or line.display_type in ('line_section', 'line_note'):
                                    continue

                                line.name = line._get_computed_name()
                                line.account_id = line._get_computed_account()
                                line.tax_ids = line._get_computed_taxes()
                                line.product_uom_id = line._get_computed_uom()
                                line.price_unit = line._get_computed_price_unit()

                        else:
                            if default_tax != False:
                                for tax in invoice_lines.product_id.product_tmpl_id.taxes_id:
                                    tax_ids.append(tax.id)
                            invoice_lines.tax_ids = tax_ids
                self._recompute_dynamic_lines(True)

            if self.journal_id.is_receipt_journal is False:

                if self.move_type == 'out_invoice':
                    if self.partner_id.company_type == "company":
                        company_iva_agent_type = self.partner_id.tax_withholding_iva
                    else:
                        if self.partner_id.parent_id:
                            company_iva_agent_type = self.partner_id.parent_id.tax_withholding_iva
                        else:
                            company_iva_agent_type = self.partner_id.tax_withholding_iva

                    if company_iva_agent_type != 'no_witholding':
                        self.tax_withholding_iva = company_iva_agent_type
                        self.amount_total = self.amount_total + self.tax_withholding_amount_iva
                        self.tax_withholding_amount_iva = 0
                    else:
                        self.tax_withholding_iva = company_iva_agent_type

                # FACTURAS COMPRA
                if self.move_type == 'in_invoice':
                    company_iva_agent_type = self.env.company.tax_withholding_iva
                    if company_iva_agent_type != 'no_witholding':
                        self.tax_withholding_iva = company_iva_agent_type
                        self.amount_total = self.amount_total + self.tax_withholding_amount_iva
                        self.tax_withholding_amount_iva = 0
                    else:
                        self.tax_withholding_iva = company_iva_agent_type

        return response

    def action_cancel(self):
        for rec in self:
            rec.numero_viejo = rec.name
        return super(AccountMove, self).action_cancel()



    @api.onchange('invoice_line_ids', 'tax_withold_amount')
    def _onchange_invoice_line_ids(self):

        res = super(AccountMove, self)._onchange_invoice_line_ids()

        type_expense = self.tipo_gasto
        #Banderas que verifican el tipo de facturas
        is_compra = False
        is_service = False
        is_mix = False
        is_import = False
        is_gas = False
        flag_gas = False
        #Recorre todos los productos que están dentro de la facturas
        #Verifica el tipo y así cambia la bandera del tipo para dejar
        #un tipo de factura
        for invoice_lines in self.invoice_line_ids:
            #Si existe incoterm
            if self.invoice_incoterm_id:
                is_import = True
                break

            #Si existe un impuesto
            if invoice_lines.tax_ids:
                for tax in invoice_lines.tax_ids:
                    if tax.sat_tax_type == 'gas':
                        if is_compra or is_service:
                            is_mix = True
                        else:
                            is_gas = True
                            flag_gas = True
                if flag_gas:
                    flag_gas = False
                    continue

            #Si la línea de factura es un producto
            if invoice_lines.product_id.type == 'product' or invoice_lines.product_id.type == 'consu':
                if is_service or is_gas:
                    is_mix = True
                else:
                    is_compra = True

            #Si la línea de factura es un servicio
            elif invoice_lines.product_id.type == 'service':
                if is_compra or is_gas:
                    is_mix = True
                else:
                    is_service = True



        #Cambia el tipo de la factura dependiendo el tipo de las líneas de la facturas
        if is_mix:
            self.tipo_gasto = 'mixto'
        elif is_compra:
            self.tipo_gasto = 'compra'
        elif is_service:
            self.tipo_gasto = 'servicio'
        elif is_import:
            self.tipo_gasto = 'importacion'
        elif is_gas:
            self.tipo_gasto = 'combustible'

        account_id = 7

        self._compute_amount()

        for move in self:
            if move.partner_id.tax_withholding_isr == "small_taxpayer_withholding" and self.move_type == 'in_invoice':
                for invoice_lines in move.invoice_line_ids:
                    invoice_lines.tax_ids = False

                move_lines = []
                for move_line in move.line_ids:
                    if move_line.tax_line_id.id is False:
                        move_lines.append(move_line.id)

                move.line_ids = move_lines

        """
        if self.type_invoice == "special_invoice":
            tax_obj = self.env['account.tax'].search(
                [('name', '=', 'IVA FACTURAS ESPECIALES'), ('company_id', '=', self.company_id.id)], limit=1)
            account_id = 7
            if tax_obj:
                account_id = tax_obj.account_id.id
            iva_create = {'invoice_id': self.id, 'name': "IVA FACTURAS ESPECIALES",
                          'amount': self.amount_tax * -1, 'manual': False,
                          'sequence': 0, 'account_analytic_id': False, 'account_id':  account_id, 'analytic_tag_ids': False,
                          }
            tax_obj = self.env['account.tax'].search([('name', '=', 'ISR FACTURAS ESPECIALES'), ('company_id', '=', self.company_id.id)], limit=1)
            account_id = 7
            if tax_obj:
                account_id = tax_obj.account_id.id
        """

        return res

    def organize_moves(self):

        provider_invoices = self.env['account.move'].search([
        ('move_type', '=', 'in_invoice')
        ])

        for invoice in provider_invoices:

            is_compra = False
            is_service = False
            is_mix = False
            is_import = False
            is_gas = False
            flag_gas = False


            for invoice_lines in invoice.invoice_line_ids:
                #Si existe incoterm
                if invoice.invoice_incoterm_id:
                    is_import = True
                    break
                #Si existe un impuesto
                if invoice_lines.tax_ids:
                    for tax in invoice_lines.tax_ids:
                        if tax.sat_tax_type == 'gas':
                            if is_compra or is_service:
                                is_mix = True
                                flag_gas = True
                            else:
                                is_gas = True
                                flag_gas = True
                    if flag_gas:
                        flag_gas = False
                        continue

                #Si la línea de factura es un producto
                if invoice_lines.product_id.type == 'product' or invoice_lines.product_id.type == 'consu':
                    if is_service or is_gas:
                        is_mix = True
                    else:
                        is_compra = True

                #Si la línea de factura es un servicio
                elif invoice_lines.product_id.type == 'service':
                    if is_compra or is_gas:
                        is_mix = True
                    else:
                        is_service = True

            if is_mix:
                invoice.write({"tipo_gasto":"mixto"})
            elif is_compra:
                invoice.write({"tipo_gasto": 'compra'})
            elif is_service:
                invoice.write({"tipo_gasto":"servicio"})
            elif is_import:
                invoice.write({"tipo_gasto":'importacion'})
            elif is_gas:
                invoice.write({"tipo_gasto":'combustible'})
