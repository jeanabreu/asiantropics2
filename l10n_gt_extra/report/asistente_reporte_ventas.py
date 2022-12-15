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


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
