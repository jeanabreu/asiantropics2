# -*- encoding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo import api, models, fields
import logging
import calendar
import datetime

class ReporteDiario(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_diario'
    _description = 'Report Diario'
    
    def retornar_saldo_inicial_todos_anios(self, cuenta, fecha_desde):
        saldo_inicial = 0
        self.env.cr.execute('select a.id, a.code as codigo, a.name as cuenta, sum(l.debit) as debe, sum(l.credit) as haber '\
        'from account_move_line l join account_account a on(l.account_id = a.id) join account_move am on(am.id = l.move_id)'\
        "where a.id = %s and l.date < %s and am.state = 'posted' group by a.id, a.code, a.name,l.debit,l.credit", (cuenta,fecha_desde))
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial

    def retornar_saldo_inicial_inicio_anio(self, cuenta, fecha_desde):
        saldo_inicial = 0
        fecha = fields.Date.from_string(fecha_desde)
        self.env.cr.execute('select a.id, a.code as codigo, a.name as cuenta, sum(l.debit) as debe, sum(l.credit) as haber '\
        'from account_move_line l join account_account a on(l.account_id = a.id) join account_move am on(am.id = l.move_id)'\
        "where a.id = %s and l.date < %s and l.date >= %s and am.state = 'posted' group by a.id, a.code, a.name,l.debit,l.credit", (cuenta,fecha_desde,fecha.strftime('%Y-1-1')))
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial
    
    def lineas(self, datos):
        
        totales = {}
        lineas = []
        totales['debe'] = 0
        totales['haber'] = 0
        totales['saldo_inicial'] = 0
        totales['saldo_final'] = 0
        meses = {}
        
        accounts_str = ','.join([str(x) for x in datos['cuentas_id']])
        """
        if datos['all_accounts']:
            account_list = None
           
            if datos['currency_id']:
                if datos['currency_id'][1] == 'GTQ':
                    self.env.cr.execute('select id from account_account aa where aa.currency_id is null or aa.currency_id = '+ str(datos['currency_id'][0])+ ' order by id')
                    accounts_list = [item[0] for item in self.env.cr.fetchall()]
                elif datos['currency_id'][1] == 'USD':
                    self.env.cr.execute('select id from account_account aa where aa.currency_id ='+ str(datos['currency_id'][0])+ ' order by id')
                    accounts_list = [item[0] for item in self.env.cr.fetchall()]

            else:
            
                self.env.cr.execute('select id from account_account order by id')
                accounts_list = [item[0] for item in self.env.cr.fetchall()]
            accounts_str = ','.join([str(x) for x in accounts_list])
        else:
            account_ids = [x for x in datos['cuentas_id']]
            accounts_str = ','.join([str(x) for x in datos['cuentas_id']])
        """
        if datos['grouping_type'] == 'daily':
            fechas = {}
            subtotales = {}
            sql = """
            select ml.date as fecha, aa.id as No_Cuenta, aa.name as cuenta, aa.code as codigo_cuenta, SUM(ml.debit) as debe, SUM(ml.credit) as haber, am.name as poliza, ml.move_id as move_id, am.ref as descripcion 
            from account_move_line ml 
            inner join account_account aa on(ml.account_id = aa.id) 
            inner join account_move am on(am.id = ml.move_id)  
            where ml.date >= '%s' and ml.date <= '%s' and aa.id in (%s) and am.state = 'posted' and am.company_id = %s
            group by  ml.account_id, ml.name, aa.id, aa.code, ml.move_id, am.name, am.ref, ml.date
            order by ml.date, aa.id
            """%(datos['fecha_desde'], datos['fecha_hasta'], accounts_str, str(self.env.company.id)) 
            self.env.cr.execute(sql)
            move_line_ids = self.env.cr.dictfetchall()
            for line in move_line_ids:
                date = line['fecha'].strftime('%d/%m/%Y')
                
                new_line = {
                        'descripcion': line['descripcion'] if line['descripcion'] else '-',
                        'codigo_cuenta': line['codigo_cuenta'],
                        'fecha_movimiento': date,
                        'cuenta': line['cuenta'],
                        'poliza': line['poliza'],
                        'haber': line['haber'],
                        'debe': line['debe']  
                    }
                
                if date in fechas:
                    fechas[date].append(new_line)
                else:
                    data_lines = []
                    data_lines.append(new_line)
                    fechas[date] = data_lines

            total_debe = 0
            total_haber = 0
            for date in fechas:
                subtotal_debe = 0
                subtotal_haber = 0
                for line in fechas[date]:
                    subtotal_debe += line['debe']
                    subtotal_haber += line['haber']
                subtotales[date] = {
                    'subtotal_debe': subtotal_debe,
                    'subtotal_haber': subtotal_haber
                }
                total_haber += subtotal_haber
                total_debe += subtotal_haber
            totales = {
                'total_debe': total_debe,
                'total_haber': total_haber
            }
            return {'fechas': fechas, 'subtotales': subtotales, 'totales': totales}
            
        elif datos['grouping_type'] == 'monthly':
            sql = """
                select ml.date as fecha, aa.id as cuenta_id, aa.code as codigo_cuenta,SUM(ml.debit) as debe, SUM(ml.credit) as haber, am.name as poliza, aa.name as cuenta, am.ref as descripcion  
                from account_move_line ml inner join account_account aa on(ml.account_id = aa.id)  
                inner join account_move am on(am.id = ml.move_id)  
                where ml.date >= '%s' and ml.date <= '%s' and aa.id in (%s) and am.state = 'posted' and am.company_id = %s 
                group by  ml.account_id,ml.name, aa.id, aa.code, am.name, am.ref,ml.date 
                order by ml.date, aa.id
            """%(datos['fecha_desde'], datos['fecha_hasta'], accounts_str, str(self.env.company.id))
            self.env.cr.execute(sql)
            move_line_ids = self.env.cr.dictfetchall()
            total_debe = 0
            total_haber = 0
            subtotales = {}
            for line in move_line_ids:
                new_line = {
                        'descripcion': line['descripcion'] if line['descripcion'] else '-',
                        'fecha_movimiento': line['fecha'].strftime('%d/%m/%Y'),
                        'codigo': line['codigo_cuenta'],
                        'cuenta': line['cuenta'],
                        'poliza': line['poliza'],
                        'id': line['cuenta_id'],
                        'haber': line['haber'],                        
                        'debe': line['debe'],
                        'saldo_inicial': 0 
                    }
                number_month = int(line['fecha'].strftime('%m'))
                month = self.get_month_name(number_month)
                if month in meses:
                    meses[month].append(new_line)
                else:
                    data_lines = []
                    data_lines.append(new_line)
                    meses[month] = data_lines

            total_debe = 0
            total_haber = 0
            for date in meses:
                subtotal_debe = 0
                subtotal_haber = 0
                for line in meses[date]:
                    subtotal_debe += line['debe']
                    subtotal_haber += line['haber']
                subtotales[date] = {
                    'subtotal_debe': subtotal_debe,
                    'subtotal_haber': subtotal_haber
                }
                total_haber += subtotal_haber
                total_debe += subtotal_haber
            totales = {
                'total_debe': total_debe,
                'total_haber': total_haber
            }
            return {'meses': meses,'totales': totales, 'subtotales':subtotales }

        elif datos['grouping_type'] == 'transaction':
            
            sql = """
                select 
                    aml.date as fecha_movimiento,
                    aml.move_id as id_movimiento,
                    aa.id as cuenta_id,
                    aa.code as codigo_cuenta,
                    aml.debit as debe,
                    aml.credit as haber,
                    am.name as poliza,
                    am.ref as referencia,
                    aa.name as cuenta
                from
                    account_move_line aml 
                inner join
                    account_move am on(am.id = aml.move_id)
                inner join account_account aa on
                    (aml.account_id = aa.id)	
                where
                    aml.date >= '%s'
                    and aml.date <= '%s'
                    and am.company_id = %s
                order by 
                    aml.id
            """%(str(datos['fecha_desde']),str(datos['fecha_hasta']),str(self.env.company.id))
            self.env.cr.execute(sql)
            move_line_ids = {} 
            
            for linea in self.env.cr.dictfetchall():
                nueva_linea ={
                        'referencia': linea['referencia'] if linea['referencia'] else '-',
                        'fecha_movimiento': linea['fecha_movimiento'].strftime('%d/%m/%Y'),
                        'id_movimiento': linea['id_movimiento'],
                        'codigo': linea['codigo_cuenta'],
                        'cuenta': linea['cuenta'],
                        'poliza': linea['poliza'],
                        'haber': linea['haber'],
                        'debe': linea['debe'],   
                    }

                if str(linea['poliza']) in move_line_ids:
                    move_line_ids[str(linea['poliza'])].append(nueva_linea)
                else:
                    lineas = []
                    lineas.append(nueva_linea)
                    move_line_ids[str(linea['poliza'])] = lineas
            
            subtotales = {}
            totales = {}
            total_debe = 0
            total_haber = 0
            for move in move_line_ids:
                subtotal_debe = 0
                subtotal_haber = 0
                
                for line in move_line_ids[str(move)]:
                    subtotal_haber += abs(line['haber'])
                    subtotal_debe += abs(line['debe'])
                
                total_haber += abs(subtotal_haber)
                total_debe += abs(subtotal_debe)
                subtotales[str(move)] = {
                    'subtotal_haber': subtotal_haber,
                    'subtotal_debe': subtotal_debe
                }

            totales['total_haber'] = round(total_haber,2)
            totales['total_debe'] = round(total_debe, 2)
            return {'move_line_ids':move_line_ids, 'subtotales': subtotales, 'totales':totales}
    def get_month_name(self, month):
        if month== 1:
            return "Enero"
        elif month == 2:
            return "Febrero"
        elif month == 3:
            return "Marzo"
        elif month == 4:
            return "Abril"
        elif month == 5:
            return "Mayo"
        elif month == 6:
            return "Junio"
        elif month == 7:
            return "Julio"
        elif month == 8:
            return "Agosto"
        elif month == 9:
            return "Septiembre"
        elif month == 10:
            return "Octubre"
        elif month == 11:
            return "Noviembre"
        elif month == 12:
            return "Diciembre"
            
    @api.model
    def _get_report_values(self, docids, data=None):
        return self.get_report_values(docids, data)

    @api.model
    def get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        data = data['form']
        tmp_inicio = data['fecha_desde'].split('-')
        tmp_final = data['fecha_hasta'].split('-')
        
        fecha_inicio = str(tmp_inicio[2])+"/"+str(tmp_inicio[1]+"/"+str(tmp_inicio[0]))
        fecha_final = str(tmp_final[2])+"/"+str(tmp_final[1]+"/"+str(tmp_final[0]))

        data['fecha_inicio'] = fecha_inicio
        data['fecha_final'] = fecha_final
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data,
            'docs': docs,
            'lineas': self.lineas,
            'company_id': self.env.company,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
