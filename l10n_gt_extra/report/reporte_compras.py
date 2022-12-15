from logging.config import valid_ident
from odoo import api, models
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ReporteCompras(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_compras'

    def lineas(self, datos):
        totales = {}

        totales['num_facturas'] = 0
        totales['compra'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['servicio'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['importacion'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['combustible'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['small_taxpayer'] = {'compra': 0, 'servicio': 0, 'combustible': 0, 'importacion':0,'total': 0}
        totales['compras'] = {'bienes': 0}
        totales['total'] = 0
        totales['resumen'] = {'exento': 0, 'neto': 0, 'iva': 0, 'total': 0}
        totales['pequenio_contribuyente'] = 0

        journal_ids = [x for x in datos['diarios_id']]
        tax_ids = [x for x in datos['impuesto_id']]
        facturas = self.env['account.move'].search([
            ('state', 'in', ['draft', 'posted']),
            ('journal_id', 'in', journal_ids),
            ('invoice_date', '<=', datos['fecha_hasta']),
            ('invoice_date', '>=', datos['fecha_desde']),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
        ], order='invoice_date, payment_reference')

        lineas = []
        for f in facturas:

            if f.journal_id.is_receipt_journal:
                continue
            #Verifica si la factura no tiene impuestos
            has_taxes = False
            for line in f.invoice_line_ids:
                if len(line.tax_ids) > 0:
                    has_taxes = True
            if has_taxes is False:
                if not f.partner_id.pequenio_contribuyente:
                    continue
            
            proveedor = f.partner_id.name
            nit = f.partner_id.vat
            numero = f.provider_invoice_number

            totales['num_facturas'] += 1

            tipo_cambio = 1
            if f.currency_id.id != f.company_id.currency_id.id:
                if 'conversion_rate_ref' in self.env['account.move']._fields:
                    if f.conversion_rate_ref > 0:
                        tipo_cambio = f.conversion_rate_ref
                else:
                    tipo_cambio = 7.65
                    currency_rate_query = self.env['res.currency.rate'].search([
                        ('name', '=', f.date)
                    ], order='name desc', limit=1)
                    for rate in currency_rate_query:
                        if rate.rate > 0:
                            tipo_cambio = 1 / rate.rate

            tipo = 'FACT'
            if f.move_type != 'in_invoice':
                tipo = 'NC'
            if f.partner_id.pequenio_contribuyente:
                tipo += ' PEQ'
            if f.type_invoice == 'special_invoice':
                tipo = 'FES'
            if f.tipo_gasto == 'importacion':
                tipo = 'DA'
            if f.journal_id.is_receipt_journal == True:
                tipo = 'REC'

            linea = {
                'estado': f.state,
                'tipo': tipo,
                'fecha': f.invoice_date,
                'serie': f.provider_invoice_serial or '',
                # 'numero': f.reference or '',
                'numero': f.provider_invoice_number or '',
                'proveedor': proveedor,
                'nit': nit,
                'compra': 0,
                'compra_exento': 0,
                'servicio': 0,
                'servicio_exento': 0,
                'combustible': 0,
                'combustible_exento': 0,
                'importacion': 0,
                'importacion_exento': 0,
                'importacion_iva': 0,
                'compra_iva': 0,
                'servicio_iva': 0,
                'combustible_iva': 0,
                'small_taxpayer_amount': 0,
                'base': 0,
                'iva': 0,
                'subtotal_exento': 0, 
                'total': 0
            }
            is_compra = False
            is_service = False
            is_mix = False
            is_import = False
            is_gas = False
            flag_gas = False
            signo = 1
            for linea_factura in f.invoice_line_ids:
                if len(linea_factura.product_id) > 0:
                        
                    precio = (linea_factura.price_unit *
                            (1-(linea_factura.discount or 0.0)/100.0)) * tipo_cambio
                    if tipo == 'NC':
                        precio = precio * -1
                        signo = -1
                    tipo_linea = f.tipo_gasto

                    if linea_factura.tax_ids:
                        for tax in linea_factura.tax_ids:
                            if tax.sat_tax_type == 'gas':
                                if is_compra or is_service:
                                    is_mix = True
                                    flag_gas = True
                                else:
                                    is_gas = True
                                    flag_gas = True
                        if flag_gas:
                            flag_gas = False

                    if f.tipo_gasto == 'mixto':

                        if linea_factura.product_id.type == 'product' or linea_factura.product_id.type == 'consu':
                            tipo_linea = 'compra'
                        if linea_factura.product_id.product_tmpl_id.type == 'service':
                            tipo_linea = 'servicio'
                        if is_gas:
                            tipo_linea = 'combustible'

                    if f.tipo_gasto == 'combustible':
                        tipo_linea = 'combustible'

                    r = linea_factura.tax_ids._origin.compute_all(precio, currency=f.currency_id, quantity=linea_factura.quantity, product=linea_factura.product_id, partner=f.partner_id)

                    base_price = linea_factura.price_subtotal * signo
                    if f.currency_id.id != f.company_id.currency_id.id:
                        base_price = linea_factura.price_subtotal * tipo_cambio
                    linea['base'] += base_price
                    totales[tipo_linea]['total'] += base_price

                    # totales[tipo_linea]['total'] += precio * linea_factura.quantity

                    if len(linea_factura.tax_ids) > 0:
                        linea[tipo_linea] += base_price
                        if tipo_linea == 'compra':
                            totales['compras']['bienes'] += base_price
                        totales[tipo_linea]['neto'] += base_price
                        totales['resumen']['neto'] += base_price
                        for i in r['taxes']:
                            if i['id'] in tax_ids:
                                linea['iva'] += i['amount']
                                linea[tipo_linea+'_iva'] += i['amount']
                                totales[tipo_linea]['iva'] += i['amount']
                                totales['resumen']['iva'] += i['amount']
                                totales[tipo_linea]['total'] += i['amount']
                            elif i['amount'] > 0:
                                if tipo_linea == 'combustible':
                                    #linea['compra_exento'] += i['amount']
                                    linea[tipo_linea+'_exento'] += i['amount']
                                    linea['subtotal_exento'] += i['amount']
                                    totales[tipo_linea]['exento'] += i['amount']
                                    totales[tipo_linea]['total'] += i['amount']
                                else:
                                    linea[tipo_linea+'_exento'] += i['amount']
                                    totales[tipo_linea]['exento'] += i['amount']
                                    totales[tipo_linea]['total'] += i['amount']
                                    linea['subtotal_exento'] += i['amount']
                                totales['resumen']['exento'] += i['amount']
                    else:
                        #linea['subtotal_exento'] += base_price
                        #linea[tipo_linea+'_exento'] += base_price
                        #totales[tipo_linea]['exento'] += base_price
                        #totales['resumen']['exento'] += base_price
                        #totales[tipo_linea]['total'] += base_price
                        #linea['compra_exento'] += base_price

                        if f.partner_id.pequenio_contribuyente:
                            linea['small_taxpayer_amount'] += base_price
                            totales['small_taxpayer'][tipo_linea] += base_price
                            totales['small_taxpayer']["total"] += base_price
                            totales['pequenio_contribuyente'] += base_price
                        else:
                            linea['subtotal_exento'] += base_price
                            linea[tipo_linea+'_exento'] += base_price
                            totales[tipo_linea]['exento'] += base_price
                            totales['resumen']['exento'] += base_price
                            totales[tipo_linea]['total'] += base_price

                    linea['total'] += precio * linea_factura.quantity
                    totales['total'] += precio * linea_factura.quantity
            
            #if f.partner_id.pequenio_contribuyente:
            #    totales['pequenio_contribuyente'] += linea['base']
            
            lineas.append(linea)
        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        return self.get_report_values(docids, data)

    @api.model
    def get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))

        diario = self.env['account.journal'].browse(data['form']['diarios_id'][0])
        
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'direccion': diario.direccion and diario.direccion.street,
            'company_id': self.env.company
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
