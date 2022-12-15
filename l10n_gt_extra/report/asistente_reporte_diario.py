# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import xlwt
import base64
import io
import logging


class AsistenteReporteDiario(models.TransientModel):
    _name = 'l10n_gt_extra.asistente_reporte_diario'
    _description = 'Asistente Report Diario'

    cuentas_id = fields.Many2many("account.account", string="Diario",
                    required=True)
    folio_inicial = fields.Integer(string="Folio Inicial",
                    required=True, default=1)
    agrupado_por_dia = fields.Boolean(string="Agrupado por dia")
    fecha_desde = fields.Date(string="Fecha Inicial", required=True,
                    default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True, 
                    default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo', size=32)
    archivo = fields.Binary('Archivo', filters='.xls')

    currency_id = fields.Many2one('res.currency',string="Moneda", default=lambda self: self.env.company.currency_id.id)
    

    all_accounts = fields.Boolean(string="Todas las cuentas")
    grouping_type = fields.Selection([
        ('monthly', 'Mensual'),
        ('daily','Día'),
        ('transaction', 'Transacción')

    ],string="Tipo de Agrupación", default="monthly")

    @api.onchange('all_accounts')
    def onchange_all_accounts(self):
        if self.all_accounts == True:
            for rec in self:
                account_data = self.env['account.account'].search([])
                for account in account_data:
                    rec.cuentas_id = [(4, account.id)] 
        if self.all_accounts == False:
            for rec in self:
                rec.cuentas_id = False
            
    
    #@api.multi
    def print_report(self):
        form_data = []
        if self.read():
            form_data = self.read()[0]
        data = {
             'ids': [],
             'model': 'l10n_gt_extra.asistente_reporte_diario',
             'form': form_data
        }
        return self.env.ref('l10n_gt_extra.action_reporte_diario').report_action(self, data=data)

    def print_report_excel(self):
        for w in self:
            dict = {}
            dict['fecha_hasta'] = w['fecha_hasta']
            dict['fecha_desde'] = w['fecha_desde']
            dict['agrupado_por_dia'] = w['agrupado_por_dia']
            dict['cuentas_id'] =[x.id for x in w.cuentas_id]
            res = self.env['report.l10n_gt_extra.reporte_diario'].lineas(dict)
            
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
            estilo = xlwt.easyxf('pattern: pattern solid, fore_colour custom_colour,')
            hoja.write(0, 0, 'LIBRO DIARIO')
            hoja.write(2, 0, 'NUMERO DE IDENTIFICACION TRIBUTARIA')
            hoja.write(2, 1, w.cuentas_id[0].company_id.partner_id.vat)
            hoja.write(3, 0, 'NOMBRE COMERCIAL')
            hoja.write(3, 1, w.cuentas_id[0].company_id.partner_id.name)
            hoja.write(2, 3, 'DOMICILIO FISCAL')
            hoja.write(2, 4, w.cuentas_id[0].company_id.partner_id.street)
            hoja.write(3, 3, 'REGISTRO DEL')
            hoja.write(3, 4, w.fecha_desde + ' al ' + w.fecha_hasta)

            y = 5
            if w['agrupado_por_dia']:
                lineas = res['lineas']

                hoja.write(y, 0, 'Fecha')
                hoja.write(y, 1, 'Codigo')
                hoja.write(y, 2, 'Cuenta')
                hoja.write(y, 3, 'Debe')
                hoja.write(y, 4, 'Haber')

                for fechas in lineas:
                    y += 1
                    hoja.write(y, 0, fechas['fecha'])
                    for cuentas in fechas['cuentas']:
                        y += 1
                        hoja.write(y, 1, cuentas['codigo'])
                        hoja.write(y, 2, cuentas['cuenta'])
                        hoja.write(y, 3, cuentas['debe'])
                        hoja.write(y, 4, cuentas['haber'])
                    y += 1
                    hoja.write(y, 3, fechas['total_debe'])
                    hoja.write(y, 4, fechas['total_haber'])

            else:
                lineas = res['lineas']
                totales = res['totales']
                
                hoja.write(y, 0, 'No. de transacción',style=titulos_principales_style )
                hoja.write(y, 1, 'Fecha',style=titulos_principales_style)
                hoja.write(y, 2, 'Número De Doc',style=titulos_principales_style)
                hoja.write(y, 3, 'Codigo',style=titulos_principales_style)
                hoja.write(y, 4, 'Cuenta',style=titulos_principales_style)
                hoja.write(y, 5, 'Debe',style=titulos_principales_style)
                hoja.write(y, 6, 'Haber',style=titulos_principales_style)
                hoja.write(y, 7, 'Comentario',style=titulos_principales_style)

                for linea in lineas:
                    y += 1
                    hoja.write(y, 0, linea['numero_movimiento'], style=titulos_texto_style)
                    hoja.write(y, 1, linea['fecha_movimiento'], style=titulos_texto_style)
                    hoja.write(y, 2, linea['numero_documento'], style=titulos_texto_style)
                    hoja.write(y, 3, linea['codigo'],style=titulos_texto_style)
                    hoja.write(y, 4, linea['cuenta'],style=titulos_texto_style)
                    hoja.write(y, 5, linea['debe'],style=titulos_numero_style)
                    hoja.write(y, 6, linea['haber'],style=titulos_numero_style)
                    hoja.write(y, 7, linea['comentario_documento'],style=titulos_texto_style)

                y += 1
                hoja.write(y, 4, 'Totales',style=titulos_texto_style)
                hoja.write(y, 5, totales['debe'],style=titulos_texto_style)
                hoja.write(y, 6, totales['haber'],style=titulos_texto_style)

            xlwt.add_palette_colour("custom_colour", 0x21)
            libro.set_colour_RGB(0x21, 200, 200, 200)
            estilo = xlwt.easyxf('pattern: pattern solid,')

            f = io.BytesIO()
            libro.save(f)
            datos = base64.b64encode(f.getvalue())
            self.write({'archivo': datos, 'name': 'libro_diario.xls'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'l10n_gt_extra.asistente_reporte_diario',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
