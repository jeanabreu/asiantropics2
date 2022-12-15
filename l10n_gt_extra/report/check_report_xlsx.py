# -*- coding: utf-8 -*-
import json
import io

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, date
import logging


_logger = logging.getLogger(__name__)

class AdjustInventoryReport(models.AbstractModel):
    _name = 'report.l10n_gt_extra.check_report_xlsx' 
    _inherit = 'report.report_xlsx.abstract'
    _description = "Check Report"
    
    def generate_xlsx_report(self, workbook, data, lines):
        sheet = workbook.add_worksheet('Reporte de Cheques')
        sheet.set_column('A2:A2', 2)
        sheet.set_column('B2:B2', 4)
        sheet.set_column('C2:C2', 17)
        sheet.set_column('D2:D2', 15)
        sheet.set_column('E8:E8', 35)
        sheet.set_column('F2:F2', 22)
        sheet.set_column('G2:G2', 13)
        sheet.set_column('H2:H2', 11)
        sheet.set_column('I2:I2', 12)
        sheet.set_column('J2:J2', 25)
        sheet.set_row(1, 40)
        sheet.set_row(4, 35)
        sheet.freeze_panes(5, 0)
                
        titule_center = workbook.add_format({'font_name': 'Arial', 'font_size': 24, 'font_color': 'black', 'align': 'center'})
        sub_titule_center = workbook.add_format({'font_name': 'Arial', 'font_size': 16, 'font_color': 'black', 'align': 'center'})
        titule_center_u = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': 'black', 'align': 'center'})
        header_center = workbook.add_format({'font_name': 'Arial', 'bold': True, 'text_wrap': True, 'font_size': 10, 'font_color': 'black', 'align': 'center', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        signal_data = workbook.add_format({'font_name': 'Arial', 'bold': True, 'text_wrap': True, 'font_size': 10, 'font_color': 'black', 'align': 'center', 'bottom': 1, 'valign': 'vcenter'})
        data_left = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'left', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        data_left_black = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': 'black', 'align': 'left', 'valign': 'vcenter'})
        data_right = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'right', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter', 'num_format': '###,##0.00'})
        data_right_clean = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'right', 'valign': 'vcenter', 'num_format': '###,##0.00'})
        data_right_black = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': 'black', 'align': 'right', 'valign': 'vcenter', 'num_format': '###,##0.00'})
        data_center = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'center', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        
        date_range = ''
        if lines.date_from and lines.date_to:
            date_range = 'Desde: ' + str(lines.date_from.strftime('%d/%m/%Y')) + ' Hasta: ' + str(lines.date_to.strftime('%d/%m/%Y'))
        if lines.date_from and not lines.date_to:
            date_range = 'Desde: ' + str(lines.date_from.strftime('%d/%m/%Y'))
        if not lines.date_from and lines.date_to:
            date_range = ' Hasta: ' + str(lines.date_to.strftime('%d/%m/%Y'))
            
        sheet.merge_range('B2:G2', self.env.company.name, titule_center)
        sheet.merge_range('B3:G3', 'Reporte de Cheques', sub_titule_center)
        sheet.merge_range('B4:G4', date_range, sub_titule_center)
        
        sheet.write('B5', 'No.', header_center)
        sheet.write('C5', 'Número de Cheque', header_center)
        sheet.write('D5', 'Fecha', header_center)
        sheet.write('E5', 'Cliente/Proveedor', header_center)
        sheet.write('F5', 'Diario', header_center)
        sheet.write('G5', 'Fecha anulación', header_center)
        sheet.write('H5', 'Moneda', header_center)
        sheet.write('I5', 'Importe', header_center)
        sheet.write('J5', 'Memo', header_center)
        if lines.journal_id:
            journal_ids = [x.id for x in lines.journal_id]
        else:
            journal_ids = self.env['account.journal'].search([])
        data_payment = self.env['account.payment'].search([('journal_id','in', journal_ids),('state','in',('posted','discarded')),('check_number','!=',False)])
        
        sequence = 0; y = 6
        for payment in data_payment:
            if lines.date_from and lines.date_to:
                if payment.date <= lines.date_to and payment.date >= lines.date_from:
                    sequence += 1
                    sheet.write('B'+str(y), sequence, data_center)
                    sheet.write('C'+str(y), payment.check_number, data_left)
                    sheet.write('D'+str(y), str(payment.date.strftime('%d/%m/%Y')), data_center)
                    if payment.nombre_impreso:
                        sheet.write('E'+str(y), payment.nombre_impreso, data_left)
                    else:
                        sheet.write('E'+str(y), payment.partner_id.name, data_left)
                    sheet.write('F'+str(y), payment.journal_id.name, data_left)
                    if payment.discarded_date:
                        sheet.write('G'+str(y), str(payment.discarded_date.strftime('%d/%m/%Y')), data_center)
                    else:
                        sheet.write('G'+str(y), '', data_left)
                    sheet.write('H'+str(y), payment.currency_id.name, data_center)
                    sheet.write('I'+str(y), str(payment.currency_id.symbol) + ' ' + str(round(payment.amount,2)), data_right)
                    sheet.write('J'+str(y), payment.ref, data_left)
                    y += 1
            if lines.date_from and not lines.date_to:
                if payment.date >= lines.date_from:
                    sequence += 1
                    sheet.write('B'+str(y), sequence, data_center)
                    sheet.write('C'+str(y), payment.check_number, data_left)
                    sheet.write('D'+str(y), str(payment.date.strftime('%d/%m/%Y')), data_center)
                    if payment.nombre_impreso:
                        sheet.write('E'+str(y), payment.nombre_impreso, data_left)
                    else:
                        sheet.write('E'+str(y), payment.partner_id.name, data_left)
                    sheet.write('F'+str(y), payment.journal_id.name, data_left)
                    if payment.discarded_date:
                        sheet.write('G'+str(y), str(payment.discarded_date.strftime('%d/%m/%Y')), data_center)
                    else:
                        sheet.write('G'+str(y), '', data_left)
                    sheet.write('H'+str(y), payment.currency_id.name, data_center)
                    sheet.write('I'+str(y), str(payment.currency_id.symbol) + ' ' + str(round(payment.amount,2)), data_right)
                    sheet.write('J'+str(y), payment.ref, data_left)
                    y += 1
            if not lines.date_from and lines.date_to:
                if payment.date <= lines.date_to:
                    sequence += 1
                    sheet.write('B'+str(y), sequence, data_center)
                    sheet.write('C'+str(y), payment.check_number, data_left)
                    sheet.write('D'+str(y), str(payment.date.strftime('%d/%m/%Y')), data_center)
                    if payment.nombre_impreso:
                        sheet.write('E'+str(y), payment.nombre_impreso, data_left)
                    else:
                        sheet.write('E'+str(y), payment.partner_id.name, data_left)
                    sheet.write('F'+str(y), payment.journal_id.name, data_left)
                    if payment.discarded_date:
                        sheet.write('G'+str(y), str(payment.discarded_date.strftime('%d/%m/%Y')), data_center)
                    else:
                        sheet.write('G'+str(y), '', data_left)
                    sheet.write('H'+str(y), payment.currency_id.name, data_center)
                    sheet.write('I'+str(y), str(payment.currency_id.symbol) + ' ' + str(round(payment.amount,2)), data_right)
                    sheet.write('J'+str(y), payment.ref, data_left)
                    y += 1
            if not lines.date_from and not lines.date_to:
                sequence += 1
                sheet.write('B'+str(y), sequence, data_center)
                sheet.write('C'+str(y), payment.check_number, data_left)
                sheet.write('D'+str(y), str(payment.date.strftime('%d/%m/%Y')), data_center)
                if payment.nombre_impreso:
                    sheet.write('E'+str(y), payment.nombre_impreso, data_left)
                else:
                    sheet.write('E'+str(y), payment.partner_id.name, data_left)
                sheet.write('F'+str(y), payment.journal_id.name, data_left)
                if payment.discarded_date:
                    sheet.write('G'+str(y), str(payment.discarded_date.strftime('%d/%m/%Y')), data_center)
                else:
                    sheet.write('G'+str(y), '', data_left)
                sheet.write('H'+str(y), payment.currency_id.name, data_center)
                sheet.write('I'+str(y), str(payment.currency_id.symbol) + ' ' + str(round(payment.amount,2)), data_right)
                sheet.write('J'+str(y), payment.ref, data_left)
                y += 1
        data_currency = self.env['res.currency'].search([('active','=',True)])
        for currency in data_currency:
            amount_currency = 0
            for paymt in data_payment:
                if paymt.currency_id.id == currency.id:
                    if lines.date_from and lines.date_to:
                        if paymt.date <= lines.date_to and paymt.date >= lines.date_from:
                            amount_currency += paymt.amount
                    if lines.date_from and not lines.date_to:
                        if paymt.date >= lines.date_from:
                            amount_currency += paymt.amount
                    if not lines.date_from and lines.date_to:
                        if paymt.date <= lines.date_to:
                            amount_currency += paymt.amount
                    if not lines.date_from and not lines.date_to:
                        amount_currency += paymt.amount
            if amount_currency > 0:
                y += 1
                sheet.write('H'+str(y), 'Importe Total ' + str(currency.symbol), data_left_black)
                sheet.write('I'+str(y), str(currency.symbol) + ' ' +str(round(amount_currency,2)), data_right_black)
        y += 4
        sheet.write('C'+str(y), 'Hecho por:', data_right_clean)
        sheet.write('D'+str(y), '', signal_data)
        sheet.write('F'+str(y), 'Autorizado por:', data_right_clean)
        sheet.merge_range('G'+str(y)+':H'+str(y), '', signal_data)
        workbook.close()