# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import xlwt
import base64
import io


class AsistenteReporteCompras(models.TransientModel):
    _name = 'l10n_gt_extra.asistente_reporte_compras'
    _description = 'Asistente de información para reporte de compras'

    diarios_id = fields.Many2many("account.journal", string="Diarios", required=True)
    impuesto_id = fields.Many2many("account.tax", string="Impuesto", required=True, domain="[('type_tax_use', '=', 'purchase')]")
    folio_inicial = fields.Integer(string="Folio Inicial", required=True, default=1)
    fecha_desde = fields.Date(string="Fecha Inicial", required=True, default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True, default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo', size=32)

    def print_report(self):
        data = {
             'ids': [],
             'model': 'l10n_gt_extra.asistente_reporte_compras',
             'form': self.read()[0]
        }
        return self.env.ref('l10n_gt_extra.action_reporte_compras').report_action(self, data=data)

    def print_report_excel(self):
        for w in self:
            dict = {}
            dict['fecha_hasta'] = w['fecha_hasta']
            dict['fecha_desde'] = w['fecha_desde']
            #dict['impuesto_id'] = [w.impuesto_id.id, w.impuesto_id.name]
            dict['impuesto_id'] = [x.id for x in w.impuesto_id]
            dict['diarios_id'] = [x.id for x in w.diarios_id]

            res = self.env['report.l10n_gt_extra.reporte_compras'].lineas(dict)
            lineas = res['lineas']
            totales = res['totales']
            libro = xlwt.Workbook()
            hoja = libro.add_sheet('reporte')
            xlwt.add_palette_colour("custom_colour", 0x21)
            libro.set_colour_RGB(0x21, 200, 200, 200)
            estilo = xlwt.easyxf('pattern: pattern solid, fore_colour custom_colour')
            hoja.write(0, 0, 'LIBRO DE COMPRAS Y SERVICIOS')
            hoja.write(2, 0, 'NUMERO DE IDENTIFICACION TRIBUTARIA')
            if w.diarios_id:
                hoja.write(2, 1, w.diarios_id[0].company_id.partner_id.vat)
                hoja.write(3, 0, 'NOMBRE COMERCIAL')
                hoja.write(3, 1, w.diarios_id[0].company_id.partner_id.name)
                hoja.write(2, 3, 'DOMICILIO FISCAL')
                hoja.write(2, 4, w.diarios_id[0].company_id.partner_id.street)
                hoja.write(3, 3, 'REGISTRO DEL')
                hoja.write(3, 4, str(w.fecha_desde) +
                           ' al ' + str(w.fecha_hasta))

            y = 5
            hoja.write(y, 0, '')
            hoja.write_merge(y, y, 1, 4, 'Documento')
            hoja.write_merge(y, y, 5, 6, 'Proveedor')
            hoja.write_merge(y, y, 7, 10, 'Compras')
            hoja.write_merge(y, y, 11, 14, 'Iva Crédito Fiscal')

            y = 6
            hoja.write(y, 0, 'No')
            hoja.write(y, 1, 'Fecha')
            hoja.write(y, 2, 'Tipo')
            hoja.write(y, 3, 'Serie')
            hoja.write(y, 4, 'Doc')
            hoja.write(y, 5, 'NIT')
            hoja.write(y, 6, 'Nombre')
            hoja.write(y, 7, 'Importaciones')
            hoja.write(y, 8, 'Bienes')
            hoja.write(y, 9, 'Servicios')
            hoja.write(y, 10, 'Combustibles')
            hoja.write(y, 11, 'Importaciones')
            hoja.write(y, 12, 'Bienes')
            hoja.write(y, 13, 'Servicios')
            hoja.write(y, 14, 'Combustibles')
            hoja.write(y, 15, 'Total IVA Crédito Fiscal')
            hoja.write(y, 16, 'Compras Extentas')
            hoja.write(y, 17, 'Total')

            for linea in lineas:
                y += 1
                hoja.write(y, 0, y)
                hoja.write(y, 1, linea['fecha'])
                hoja.write(y, 2, linea['tipo'])
                hoja.write(y, 3, linea['serie'])
                hoja.write(y, 4, linea['numero'])
                hoja.write(y, 5, linea['proveedor']['vat'])
                hoja.write(y, 6, linea['proveedor']['name'])
                hoja.write(y, 7, linea['importacion'])
                hoja.write(y, 8, linea['compra'])
                hoja.write(y, 9, linea['servicio'])
                hoja.write(y, 10, linea['combustible'])
                hoja.write(y, 11, linea['importacion_iva'])
                hoja.write(y, 12, linea['compra_iva'])
                hoja.write(y, 13, linea['servicio_iva'])
                hoja.write(y, 14, linea['combustible_iva'])
                hoja.write(y, 15, linea['iva'])
                hoja.write(y, 16, linea['compra_exento'])
                hoja.write(y, 17, linea['total'])

            y += 1
            hoja.write(y, 6, 'Totales')
            hoja.write(y, 7, totales['importacion']['neto'])
            hoja.write(y, 8, totales['compra']['neto'])
            hoja.write(y, 9, totales['servicio']['neto'])
            hoja.write(y, 10, totales['combustible']['neto'])
            hoja.write(y, 11, totales['importacion']['iva'])
            hoja.write(y, 12, totales['compra']['iva'])
            hoja.write(y, 13, totales['servicio']['iva'])
            hoja.write(y, 14, totales['combustible']['iva'])
            hoja.write(y, 15, totales['compra']['iva'] + totales['servicio']
                       ['iva']+totales['combustible']['iva']+totales['importacion']['iva'])
            hoja.write(y, 16, totales['compra']['exento']+totales['servicio']['exento']+totales['combustible']['exento']+totales['importacion']['exento'])
            hoja.write(y, 17, totales['total'])

            y += 2
            hoja.write(y, 0, 'Total de facturas de pequenos contribuyentes')
            hoja.write(y, 1, totales['pequenio_contribuyente'])
            y += 1
            hoja.write(y, 0, 'Cantidad de facturas')
            hoja.write(y, 1, totales['num_facturas'])
            y += 1
            hoja.write(y, 0, 'Total credito fiscal')
            hoja.write(y, 1, totales['compra']['iva'] + totales['servicio']['iva'] +
                       totales['combustible']['iva'] + totales['importacion']['iva'])

            y += 2
            hoja.write(y, 3, 'EXENTO')
            hoja.write(y, 4, 'NETO')
            hoja.write(y, 5, 'IVA')
            hoja.write(y, 6, 'TOTAL')
            y += 1
            hoja.write(y, 1, 'COMPRAS')
            hoja.write(y, 3, totales['compra']['exento'])
            hoja.write(y, 4, totales['compra']['neto'])
            hoja.write(y, 5, totales['compra']['iva'])
            hoja.write(y, 6, totales['compra']['total'])
            y += 1
            hoja.write(y, 1, 'SERVICIOS')
            hoja.write(y, 3, totales['servicio']['exento'])
            hoja.write(y, 4, totales['servicio']['neto'])
            hoja.write(y, 5, totales['servicio']['iva'])
            hoja.write(y, 6, totales['servicio']['total'])
            y += 1
            hoja.write(y, 1, 'COMBUSTIBLES')
            hoja.write(y, 3, totales['combustible']['exento'])
            hoja.write(y, 4, totales['combustible']['neto'])
            hoja.write(y, 5, totales['combustible']['iva'])
            hoja.write(y, 6, totales['combustible']['total'])
            y += 1
            hoja.write(y, 1, 'IMPORTACIONES')
            hoja.write(y, 3, totales['importacion']['exento'])
            hoja.write(y, 4, totales['importacion']['neto'])
            hoja.write(y, 5, totales['importacion']['iva'])
            hoja.write(y, 6, totales['importacion']['total'])
            y += 1
            hoja.write(y, 1, 'TOTALES')
            hoja.write(y, 3, totales['compra']['exento']+totales['servicio']['exento'] +
                       totales['combustible']['exento']+totales['importacion']['total'])
            hoja.write(y, 4, totales['compra']['neto']+totales['servicio']['neto'] +
                       totales['combustible']['neto']+totales['importacion']['neto'])
            hoja.write(y, 5, totales['compra']['iva']+totales['servicio']['iva'] +
                       totales['combustible']['iva']+totales['importacion']['iva'])
            hoja.write(y, 6, totales['compra']['total']+totales['servicio']['total'] +
                       totales['combustible']['total']+totales['importacion']['total'])

            f = io.BytesIO()
            libro.save(f)
            datos = base64.b64encode(f.getvalue())

            self.write({'archivo': datos, 'name': 'libro_de_compras.xls'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'l10n_gt_extra.asistente_reporte_compras',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
