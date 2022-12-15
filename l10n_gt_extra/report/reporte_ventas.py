# -*- encoding: utf-8 -*-

from typing import ValuesView
from odoo import api, models
import logging
from odoo.exceptions import ValidationError
import math

class ReporteVentas(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_ventas'
    _description = 'Report Diario'
    
    def lineas(self, datos):
        totales = {}

        totales['num_facturas'] = 0
        totales['compra'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['servicio'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['importacion'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['combustible'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['venta_neta'] = 0
        totales['extentos'] = 0

        journal_ids = [x for x in datos['diarios_id']]
        facturas = self.env['account.move'].search([
            ('state', 'in', ['draft', 'posted', 'cancel']),
            ('journal_id', 'in', journal_ids),
            ('invoice_date', '<=', datos['fecha_hasta']),
            ('invoice_date', '>=', datos['fecha_desde']),
        ], order='invoice_date, name')

        lineas = []

        for f in facturas:
            cliente = f.partner_id.name
            nit = f.partner_id.vat

            totales['num_facturas'] += 1

            tipo_cambio = 1
            if f.currency_id.id != f.company_id.currency_id.id:
                tipo_cambio = 7.65
                currency_rate_query = self.env['res.currency.rate'].search([
                    ('name', '<=', f.date)
                ], order='name desc', limit=1)
                for rate in currency_rate_query:
                    tipo_cambio = rate.rate
                    tipo_cambio = 1/tipo_cambio

            tipo = 'FACT'
            signo = 1
            if f.move_type == 'out_refund':
                if f.amount_untaxed >= 0:
                    tipo = 'NC'
                    signo = -1
                else:
                    tipo = 'ND'

            # numero = f.number or f.numero_viejo or '-',
            numero = f.name
            # Por si es un diario de rango de facturas
            if f.journal_id.facturas_por_rangos:
                numero = f.name

            # Por si usa factura electrónica
            if 'firma_gface' in f.fields_get() and f.firma_gface:
                numero = f.name

            # Por si usa tickets
            if 'requiere_resolucion' in f.journal_id.fields_get() and f.journal_id.requiere_resolucion:
                numero = f.name

            if f.state == 'cancel':
                numero = f.name
                cliente = 'ANULADA'
                nit = ''

            linea = {
                'estado': f.state,
                'tipo': tipo,
                'serie': f.journal_id.code,
                'fecha': f.invoice_date,
                'numero': numero,
                'cliente': cliente,
                'nit': nit,
                'compra': 0,
                'compra_exento': 0,
                'servicio': 0,
                'servicio_exento': 0,
                'combustible': 0,
                'combustible_exento': 0,
                'importacion': 0,
                'importacion_exento': 0,
                'total_extento': 0,
                'base': 0,
                'iva': 0,
                'total': 0
            }

            if f.state == 'cancel':
                lineas.append(linea)
                continue
            
            for l in f.invoice_line_ids:
                precio = (l.price_unit * (1-(l.discount or 0.0)/100.0)) 
                if tipo == 'NC':
                    precio = precio * -1

                tipo_linea = f.tipo_gasto
                if f.tipo_gasto == 'mixto':
                    if l.product_id.product_tmpl_id.type == 'product':
                        tipo_linea = 'compra'
                    else:
                        tipo_linea = 'servicio'

                r = l.tax_ids._origin.compute_all(precio, currency=f.currency_id, quantity=l.quantity, product=l.product_id, partner=f.partner_id)
                base_price = (l.price_subtotal  * signo)  * tipo_cambio
                linea['base'] += base_price
                totales[tipo_linea]['total'] += base_price 
                totales['venta_neta'] += base_price 
                if len(l.tax_ids) > 0:
                    linea[tipo_linea] += base_price
                    totales[tipo_linea]['neto'] += base_price
                    for i in r['taxes']:
                        if i['id'] == datos['impuesto_id'][0]:
                            #Cambios agregados para Analytecs 26/11/2021, al hacer la conversión de dolares a quetzales
                            #muchos centavos se estaban perdiendo así que se coloca la validación si es en dolares
                            #que realice otro flujo para poder recuperar esos decimales que se pierden
                            if f.currency_id.id == f.company_id.currency_id.id:
                                linea['iva'] += i['amount'] * signo
                                totales[tipo_linea]['iva'] += i['amount']  * signo
                                totales[tipo_linea]['total'] += i['amount']  * signo
                            else:
                                amount = (precio * l.quantity * tipo_cambio) - base_price
                                linea['iva'] += amount
                                totales[tipo_linea]['iva'] += amount
                                totales[tipo_linea]['total'] += amount
                        elif i['amount'] > 0:
                            linea[tipo_linea+'_exento'] += i['amount']  * signo
                            totales[tipo_linea]['exento'] += i['amount']  * signo
                            totales['extentos'] += i['amount']  * signo
                else:
                    linea[tipo_linea+'_exento'] += base_price  
                    linea['total_extento'] += base_price
                    print("\n\nENTRA A SUMAR EL EXENTO")  
                    print(base_price)
                    print(tipo_linea)
                    totales[tipo_linea]['exento'] += base_price  
                    totales['extentos'] += base_price
                    print(totales[tipo_linea]['exento'])  
                if f.currency_id.id != f.company_id.currency_id.id:
                    invoice_currency_total = round(precio * l.quantity * tipo_cambio, 2)
                    diff_totals = abs(round(invoice_currency_total - f.amount_total_signed, 5))
                    linea['total'] += round(precio * l.quantity * tipo_cambio, 2) + diff_totals
                else:
                    linea['total'] += round(precio * l.quantity * tipo_cambio, 2) 
                    
                
            lineas.append(linea)

        if datos['resumido']:
            lineas_resumidas = {}
            for l in lineas:
                llave = l['tipo']+l['fecha']
                if llave not in lineas_resumidas:
                    lineas_resumidas[llave] = dict(l)
                    lineas_resumidas[llave]['estado'] = 'open'
                    lineas_resumidas[llave]['cliente'] = 'Varios'
                    lineas_resumidas[llave]['nit'] = 'Varios'
                    lineas_resumidas[llave]['facturas'] = [l['numero']]
                else:
                    lineas_resumidas[llave]['compra'] += l['compra']
                    lineas_resumidas[llave]['compra_exento'] += l['compra_exento']
                    lineas_resumidas[llave]['servicio'] += l['servicio']
                    lineas_resumidas[llave]['servicio_exento'] += l['servicio_exento']
                    lineas_resumidas[llave]['combustible'] += l['combustible']
                    lineas_resumidas[llave]['combustible_exento'] += l['combustible_exento']
                    lineas_resumidas[llave]['importacion'] += l['importacion']
                    lineas_resumidas[llave]['importacion_exento'] += l['importacion_exento']
                    lineas_resumidas[llave]['base'] += l['base']
                    lineas_resumidas[llave]['iva'] += l['iva']
                    lineas_resumidas[llave]['total'] += l['total']
                    lineas_resumidas[llave]['facturas'].append(l['numero'])

            for l in lineas_resumidas.values():
                facturas = sorted(l['facturas'])
                l['numero'] = l['facturas'][0] + ' al ' + l['facturas'][-1]

            lineas = sorted(lineas_resumidas.values(), key=lambda l: l['tipo']+l['fecha'])
        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        return self.get_report_values(docids, data)

    @api.model
    def get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))

        diario = self.env['account.journal'].browse(data['form']['diarios_id'][0])

        for data_company in diario:
            company_name = data_company.company_id.name
            company_registry = data_company.company_id.company_registry
            company_street = data_company.company_id.street
            company_vat = data_company.company_id.vat
            company_logo = data_company.company_id.logo
            
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'direccion_diario': diario.direccion and diario.direccion.street,
            'company_id': self.env.company
        }

def truncate(number, digits) -> float:
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
