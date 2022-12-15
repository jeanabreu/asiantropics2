# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import xlwt
import base64
import io


class AsistenteReporteVentas(models.TransientModel):
    _name = 'l10n_gt_extra.asistente_reporte_ventas'
    _description = 'Asistente Report Ventas'

    diarios_id = fields.Many2many("account.journal", string="Diarios", required=True)
    impuesto_id = fields.Many2one("account.tax", string="Impuesto", required=True,  domain="[('type_tax_use', '=', 'sale')]")
    folio_inicial = fields.Integer(string="Folio Inicial", required=True, default=1)
    resumido = fields.Boolean(string="Resumido")
    fecha_desde = fields.Date(string="Fecha Inicial", required=True, default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True, default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo', size=32)
    archivo = fields.Binary('Archivo', filters='.xls')

    def print_report(self):
        data = {
             'ids': [],
             'model': 'l10n_gt_extra.asistente_reporte_ventas',
             'form': self.read()[0]
        }
        return self.env.ref('l10n_gt_extra.action_reporte_ventas').report_action(self, data=data)

    def print_report_excel(self):
        for w in self:
            dict = {}
            dict['fecha_hasta'] = w['fecha_hasta']
            dict['fecha_desde'] = w['fecha_desde']
            dict['impuesto_id'] = [w.impuesto_id.id, w.impuesto_id.name]
            dict['diarios_id'] = [x.id for x in w.diarios_id]
            dict['resumido'] = w['resumido']

            res = self.env['report.l10n_gt_extra.reporte_ventas'].lineas(dict)
            lineas = res['lineas']
            totales = res['totales']
            libro = xlwt.Workbook()
            hoja = libro.add_sheet('reporte')

            titulos_principales_style = xlwt.easyxf('borders: top_color black, bottom_color black, right_color black, left_color black,\
            left thin, right thin, top thin, bottom thin; align: horiz center; font:bold on;')
            titulos_texto_style = xlwt.easyxf('borders: top_color black, bottom_color black, right_color black, left_color black,\
            left thin, right thin, top thin, bottom thin; align: horiz left;')
            titulos_numero_style = xlwt.easyxf('borders: top_color black, bottom_color black, right_color black, left_color black,\
            left thin, right thin, top thin, bottom thin; align: horiz right;')
            xlwt.add_palette_colour("custom_colour", 0x21)
            libro.set_colour_RGB(0x21, 200, 200, 200)
            estilo = xlwt.easyxf('pattern: pattern solid, fore_colour custom_colour')
            hoja.write(0, 0, 'LIBRO DE VENTAS Y SERVICIOS')
            hoja.write(2, 0, 'NUMERO DE IDENTIFICACION TRIBUTARIA')
            hoja.write(2, 1, w.diarios_id[0].company_id.partner_id.vat)
            hoja.write(3, 0, 'NOMBRE COMERCIAL')
            hoja.write(3, 1, w.diarios_id[0].company_id.partner_id.name)
            hoja.write(2, 3, 'DOMICILIO FISCAL')
            hoja.write(2, 4, w.diarios_id[0].company_id.partner_id.street)
            hoja.write(3, 3, 'REGISTRO DEL')
            hoja.write(3, 4, str(w.fecha_desde) + ' al ' + str(w.fecha_hasta))

            y = 5
            hoja.write_merge(y, y, 0, 4, 'Documento', style=titulos_principales_style)
            hoja.write_merge(y, y, 5, 6, 'Cliente', style=titulos_principales_style)
            hoja.write_merge(y, y, 7, 10, 'Ventas', style=titulos_principales_style)
            hoja.write_merge(y, y, 11, 13, 'Total', style=titulos_principales_style)

            y = 6
            hoja.write(y, 0, 'No', style=titulos_principales_style)
            hoja.write(y, 1, 'Fecha', style=titulos_texto_style)
            hoja.write(y, 2, 'Tipo', style=titulos_texto_style)
            hoja.write(y, 3, 'Serie', style=titulos_principales_style)
            hoja.write(y, 4, 'DoctoNo', style=titulos_principales_style)
            hoja.write(y, 5, 'NIT', style=titulos_texto_style)
            hoja.write(y, 6, 'Nombre', style=titulos_principales_style)
            hoja.write(y, 7, 'Exportacion', style=titulos_principales_style)
            hoja.write(y, 8, 'Bienes', style=titulos_principales_style)
            hoja.write(y, 9, 'Servicios', style=titulos_principales_style)
            hoja.write(y, 10, 'Exentas', style=titulos_principales_style)
            hoja.write(y, 11, 'IVA', style=titulos_principales_style)
            hoja.write(y, 12, 'Venta Neta', style=titulos_principales_style)
            hoja.write(y, 13, 'Venta Total', style=titulos_principales_style)

            conteo_lineas = 0
            total_extento = 0
            total_base = 0
            total_total = 0
            for linea in lineas:
                y += 1
                conteo_lineas += 1
                hoja.write(y, 0, conteo_lineas, style=titulos_principales_style)
                hoja.write(y, 1, linea['fecha'], style=titulos_principales_style)
                hoja.write(y, 2, linea['tipo'], style=titulos_principales_style)
                hoja.write(y, 3, linea['serie'], style=titulos_texto_style)
                hoja.write(y, 4, linea['numero'], style=titulos_texto_style)
                hoja.write(y, 5, linea['nit'], style=titulos_principales_style)
                hoja.write(y, 6, linea['cliente'], style=titulos_texto_style)
                hoja.write(y, 7, linea['importacion'], style=titulos_numero_style)
                hoja.write(y, 8, linea['compra'], style=titulos_numero_style)
                hoja.write(y, 9, linea['servicio'], style=titulos_numero_style)
                hoja.write(y, 10, linea['total_extento'], style=titulos_numero_style)
                hoja.write(y, 11, linea['iva'], style=titulos_numero_style)
                hoja.write(y, 12, linea['base'], style=titulos_numero_style)
                hoja.write(y, 13, linea['total'], style=titulos_numero_style)
                total_extento += linea['total_extento']
                total_base += linea['base']
                total_total += linea['total']

            y += 1
            hoja.write(y, 6, 'Totales', style=titulos_principales_style)
            hoja.write(y, 7, totales['importacion']['neto'], style=titulos_principales_style)
            hoja.write(y, 8, totales['compra']['neto'], style=titulos_principales_style)
            hoja.write(y, 9, totales['servicio']['neto'], style=titulos_principales_style)
            hoja.write(y, 10, total_extento, style=titulos_principales_style)
            hoja.write(y, 11, totales['compra']['iva'] + totales['servicio']['iva'] + totales['importacion']['iva'], style=titulos_principales_style)
            hoja.write(y, 12, totales['venta_neta'], style=titulos_principales_style)
            hoja.write(y, 13, totales['compra']['total'] + totales['servicio']['total'] + totales['importacion']['total'], style=titulos_principales_style)

            y += 2
            hoja.write(y, 0, 'Cantidad de facturas', style=titulos_principales_style)
            hoja.write(y, 1, totales['num_facturas'], style=titulos_principales_style)
            y += 1
            hoja.write(y, 0, 'Total credito fiscal', style=titulos_principales_style)
            hoja.write(y, 1, totales['compra']['iva'] + totales['servicio']['iva'] + totales['importacion']['iva'], style=titulos_principales_style)

            y += 2
            hoja.write(y, 3, 'EXENTO', style=titulos_principales_style)
            hoja.write(y, 4, 'NETO', style=titulos_principales_style)
            hoja.write(y, 5, 'IVA', style=titulos_principales_style)
            hoja.write(y, 6, 'TOTAL', style=titulos_principales_style)
            y += 1
            hoja.write(y, 1, 'BIENES', style=titulos_principales_style)
            hoja.write(y, 3, totales['compra']['exento'], style=titulos_numero_style)
            hoja.write(y, 4, totales['compra']['neto'], style=titulos_numero_style)
            hoja.write(y, 5, totales['compra']['iva'], style=titulos_numero_style)
            hoja.write(y, 6, totales['compra']['total'], style=titulos_numero_style)
            y += 1
            hoja.write(y, 1, 'SERVICIOS', style=titulos_principales_style)
            hoja.write(y, 3, totales['servicio']['exento'], style=titulos_numero_style)
            hoja.write(y, 4, totales['servicio']['neto'], style=titulos_numero_style)
            hoja.write(y, 5, totales['servicio']['iva'], style=titulos_numero_style)
            hoja.write(y, 6, totales['servicio']['total'], style=titulos_numero_style)
            '''y += 1
            hoja.write(y, 1, 'COMBUSTIBLES')
            hoja.write(y, 3, totales['combustible']['exento'])
            hoja.write(y, 4, totales['combustible']['neto'])
            hoja.write(y, 5, totales['combustible']['iva'])
            hoja.write(y, 6, totales['combustible']['total'])'''
            y += 1
            hoja.write(y, 1, 'EXPORTACIONES', style=titulos_principales_style)
            hoja.write(y, 3, 0, style=titulos_numero_style)
            hoja.write(y, 4, totales['importacion']['neto'], style=titulos_numero_style)
            hoja.write(y, 5, totales['importacion']['iva'], style=titulos_numero_style)
            hoja.write(y, 6, totales['importacion']['total'], style=titulos_numero_style)
            y += 1
            hoja.write(y, 1, 'TOTALES', style=titulos_principales_style)
            hoja.write(y, 3, totales['compra']['exento']+totales['servicio']['exento']+totales['combustible']['exento']+0, style=titulos_numero_style)
            hoja.write(y, 4, totales['compra']['neto']+totales['servicio']['neto']+totales['combustible']['neto']+totales['importacion']['neto'], style=titulos_numero_style)
            hoja.write(y, 5, totales['compra']['iva']+totales['servicio']['iva']+totales['combustible']['iva']+totales['importacion']['iva'], style=titulos_numero_style)
            hoja.write(y, 6, totales['compra']['total']+totales['servicio']['total']+totales['combustible']['total']+totales['importacion']['total'], style=titulos_numero_style)

            f = io.BytesIO()
            libro.save(f)
            datos = base64.b64encode(f.getvalue())
            self.write({'archivo': datos, 'name': 'libro_de_ventas.xls'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'l10n_gt_extra.asistente_reporte_ventas',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def get_xlsx(self):
        data_form = self.read()[0]    
        return self.env.ref('l10n_gt_extra.reporte_ventas_xlsx').report_action(self, data=data_form)


class ReporteVentasXLSX(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_ventas_xlsx' 
    _inherit = 'report.report_xlsx.abstract'
    _description = "Reporte de Ventas Excel"

    def generate_xlsx_report(self, workbook, data, lines):
        data_lines = self.env['report.l10n_gt_extra.reporte_ventas'].lineas(data)
        sheet = workbook.add_worksheet('Libro de Ventas')
        sheet.set_column('A2:A2', 1)
        sheet.set_column('B2:B2', 5)
        sheet.set_column('C2:C2', 15)
        sheet.set_column('D2:D2', 15)
        sheet.set_column('E8:E8', 12)
        sheet.set_column('F2:F2', 12)
        sheet.set_column('G2:G2', 12)
        sheet.set_column('H2:H2', 45)
        sheet.set_column('I2:I2', 12)
        sheet.set_column('J2:J2', 12)
        sheet.set_column('K2:K2', 12)
        sheet.set_column('L2:L2', 12)
        sheet.set_column('M2:M2', 12)
        sheet.set_column('N2:N2', 12)
        sheet.set_column('O2:O2', 12)
        sheet.set_column('P2:P2', 1)
        sheet.set_column('Q2:Q2', 12)
        sheet.set_column('R2:R2', 12)
        sheet.set_column('S2:S2', 12)
        sheet.set_row(1, 35)
        sheet.set_row(10, 35)
        sheet.freeze_panes(11, 0)
        
        
        title_center = workbook.add_format({'bold':True, 'font_name': 'Arial', 'font_size': 20, 'font_color': 'black', 'align': 'center'})
        title_left = workbook.add_format({'bold':True, 'font_name': 'Arial', 'font_size': 20, 'font_color': 'black', 'align': 'left'})
        subtitle_center = workbook.add_format({'font_name': 'Arial', 'font_size': 17, 'font_color': 'black', 'align': 'center'})
        date_tile = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'font_color': 'black', 'align': 'left', 'bold': True})
        date_middle = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'font_color': 'black', 'align': 'center', 'bold': True})
        date_subtitle = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'font_color': 'black', 'align': 'right', 'num_format': 'dd/mm/yy'})
        subtitle_left = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': 'black', 'align': 'left', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        titule_center_u = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'font_color': 'black', 'align': 'center'})
        header_center = workbook.add_format({'font_name': 'Arial', 'bold': True, 'text_wrap': True, 'font_size': 10, 'font_color': 'black', 'align': 'center', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        data_left = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'left', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        data_right = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'right', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        data_center = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'center', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        data_total = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 10, 'font_color': 'black', 'align': 'center', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter'})
        date_format= workbook.add_format({ 'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'center','num_format': 'dd/mm/yy', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter' })
        amount_format = workbook.add_format({'font_name': 'Arial', 'bold': False, 'font_size': 10, 'font_color': 'black', 'align': 'center','num_format': 'dd/mm/yy', 'right': 1, 'left': 1, 'top': 1, 'bottom': 1, 'valign': 'vcenter' ,'num_format': '###,##0.00','align': 'right'})
        folio_data = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'font_color': 'black', 'align': 'right', 'right': 0, 'left': 0, 'top': 0, 'bottom':1, 'valign': 'vcenter'})
        
        sheet.merge_range('B5:O6', self.env.company.name, title_center)
        sheet.merge_range('B7:O8', 'Registro de Libro de Ventas y Servicios', subtitle_center)

        sheet.merge_range('B9:C9', 'Registro del:', date_tile)
        sheet.write('D9', data['fecha_desde'], date_subtitle)
        sheet.write('E9', 'al', date_middle)
        sheet.write('F9', data['fecha_hasta'], date_subtitle)
        sheet.write('O9', 'Folio: ' + str(data['folio_inicial']), folio_data)

        sheet.merge_range('C10:F10', 'Documento', header_center)
        sheet.merge_range('G10:H10', 'Cliente', header_center)
        sheet.merge_range('I10:L10', 'Ventas', header_center)
        sheet.merge_range('M10:O10', 'Total', header_center)

        sheet.merge_range('B10:B11', 'No.', header_center)
        sheet.write('C11', 'Fecha', header_center)
        sheet.write('D11', 'Tipo', header_center)
        sheet.write('E11', 'Serie', header_center)
        sheet.write('F11', 'Docto No.', header_center)
        sheet.write('G11', 'NIT', header_center)
        sheet.write('H11', 'Nombre', header_center)
        sheet.write('I11', 'Exportaciones', header_center)
        sheet.write('J11', 'Bienes', header_center)
        sheet.write('K11', 'Servicios', header_center)
        sheet.write('L11', 'Exentas', header_center)
        sheet.write('M11', 'IVA', header_center)
        sheet.write('N11', 'Venta Neta', header_center)
        sheet.write('O11', 'Total', header_center)
        

        row_number = 12
        line_counter = 1
        count_page = 12
        folio = data['folio_inicial'] + 1
        for line in data_lines['lineas']:
            sheet.write('B'+str(row_number), line_counter, data_right)
            sheet.write('C'+str(row_number), line['fecha'], date_format)
            sheet.write('D'+str(row_number), line['tipo'], data_left)
            sheet.write('E'+str(row_number), line['serie'] if line['serie'] else "-", data_left)
            sheet.write('F'+str(row_number), line['numero'], data_left)
            sheet.write('G'+str(row_number), line['nit'] if line['nit'] else "-", data_left)
            sheet.write('H'+str(row_number), line['cliente'], data_left)
            sheet.write('I'+str(row_number), line['importacion'], amount_format)
            sheet.write('J'+str(row_number), line['compra'], amount_format)
            sheet.write('K'+str(row_number), line['servicio'], amount_format)
            sheet.write('L'+str(row_number), line['total_extento'], amount_format)
            sheet.write('M'+str(row_number), line['iva'], amount_format)
            sheet.write('N'+str(row_number), line['base'], amount_format)
            sheet.write('O'+str(row_number), line['total'], amount_format)

            line_counter += 1
            row_number += 1
            count_page += 1
            if count_page == 60:
                row_number += 1
                sheet.write('O'+str(row_number), 'Folio: ' + str(folio), folio_data)
                folio += 1
                row_number += 1
                count_page = 2

        sheet.merge_range('B'+str(row_number)+':H'+str(row_number), 'Totales', data_total)
        total_iva = data_lines['totales']['compra']['iva'] + data_lines['totales']['servicio']['iva']  + data_lines['totales']['importacion']['iva']
        total_exento = data_lines['totales']['servicio']['exento'] + data_lines['totales']['importacion']['exento'] + data_lines['totales']['compra']['exento']
        sheet.write('I'+str(row_number), data_lines['totales']['importacion']['neto'], amount_format)
        sheet.write('J'+str(row_number), data_lines['totales']['compra']['neto'], amount_format)
        sheet.write('K'+str(row_number), data_lines['totales']['servicio']['neto'], amount_format)
        sheet.write('L'+str(row_number), data_lines['totales']['combustible']['neto'], amount_format)
        sheet.write('L'+str(row_number), total_exento, amount_format)
        sheet.write('M'+str(row_number), total_iva, amount_format)
        sheet.write('N'+str(row_number), data_lines['totales']['venta_neta'], amount_format)
        sheet.write('O'+str(row_number), data_lines['totales']['compra']['total'] + data_lines['totales']['servicio']['total'] + data_lines['totales']['importacion']['total'], amount_format)

        sheet.set_paper(1)
        sheet.set_landscape()
        sheet.print_area('A1:P'+str(row_number+1))
        list_row = []
        for x in range(60, row_number, 60):
            list_row.append(x)
        sheet.set_v_pagebreaks([16])
        sheet.set_h_pagebreaks(list_row)
        sheet.set_page_view()
        
        #sheet.set_margin(left=1, right=1, top=1, bottom=1)    
         #####################
        # Hoja de Resumen   #
       #####################
        sheet2 = workbook.add_worksheet('Resumen')
        sheet2.merge_range('B3:E4', 'Resumen', title_left)

        sheet2.set_column('A2:A2', 1)
        sheet2.set_column('B2:B2', 15)
        sheet2.set_column('C2:C2', 12)
        sheet2.set_column('D2:D2', 12)
        sheet2.set_column('E8:E8', 12)
        sheet2.set_column('F2:F2', 12)
        sheet2.set_column('G2:G2', 12)

        sheet2.merge_range('B6:D6', 'Cantidad de Facturas:', data_left)
        sheet2.merge_range('B7:D7', 'Total Débito Fiscal:', data_left)
        sheet2.write('E6', data_lines['totales']['num_facturas'], data_right)
        sheet2.write('E7', data_lines['totales']['compra']['iva'] + data_lines['totales']['servicio']['iva'] + data_lines['totales']['importacion']['iva'], data_right)

        #ENCABEZADO RESUMEN
        sheet2.write('B11', '', header_center)
        sheet2.write('C11', 'Exento', header_center)
        sheet2.write('D11', 'Neto', header_center)
        sheet2.write('E11', 'IVA', header_center)
        sheet2.write('F11', 'Total', header_center)

        #COMPRAS
        sheet2.write('B12', 'Bienes', subtitle_left)
        sheet2.write('C12', data_lines['totales']['compra']['exento'], amount_format)
        sheet2.write('D12', data_lines['totales']['compra']['neto'], amount_format)
        sheet2.write('E12', data_lines['totales']['compra']['iva'], amount_format)
        sheet2.write('F12', data_lines['totales']['compra']['total'], amount_format)
        
        #SERVICIOS
        sheet2.write('B13', 'Servicios', subtitle_left)
        sheet2.write('C13', data_lines['totales']['servicio']['exento'], amount_format)
        sheet2.write('D13', data_lines['totales']['servicio']['neto'], amount_format)
        sheet2.write('E13', data_lines['totales']['servicio']['iva'], amount_format)
        sheet2.write('F13', data_lines['totales']['servicio']['total'], amount_format)

        #IMPORTACIONES
        sheet2.write('B14', 'Exportaciones', subtitle_left)
        sheet2.write('C14', data_lines['totales']['importacion']['exento'], amount_format)
        sheet2.write('D14', data_lines['totales']['importacion']['neto'], amount_format)
        sheet2.write('E14', data_lines['totales']['importacion']['iva'], amount_format)
        sheet2.write('F14', data_lines['totales']['importacion']['total'], amount_format)

        #TOTALES
        total_exento = data_lines['totales']['compra']['exento'] + data_lines['totales']['servicio']['exento'] + data_lines['totales']['importacion']['exento']
        total_neto = data_lines['totales']['compra']['neto'] + data_lines['totales']['servicio']['neto'] + data_lines['totales']['importacion']['neto']
        total_iva = data_lines['totales']['compra']['iva'] + data_lines['totales']['servicio']['iva'] + data_lines['totales']['importacion']['iva']
        total = data_lines['totales']['compra']['total'] + data_lines['totales']['servicio']['total'] + data_lines['totales']['importacion']['total']
        sheet2.write('B15', 'Totales', subtitle_left)
        sheet2.write('C15', total_exento, amount_format)
        sheet2.write('D15', total_neto, amount_format)
        sheet2.write('E15', total_iva, amount_format)
        sheet2.write('F15', total, amount_format)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
