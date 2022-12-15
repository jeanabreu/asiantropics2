# -*- encoding: utf-8 -*-
from typing import ValuesView
from odoo.exceptions import ValidationError
from odoo import api, models, fields
from datetime import date
import datetime
import calendar
import logging


class ReporteMayor(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_mayor'
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

    def get_balance(self, account_id, date):
        sql = """
            SELECT sum(balance) as account_balance, sum(amount_currency) as amount_currency
            FROM account_move_line aml
            INNER JOIN account_move am on (aml.move_id = am.id)
            WHERE aml.account_id = %s AND am.company_id = %s
            AND aml.date < '%s'
            AND aml.parent_state = 'posted'
        """ % (str(account_id), str(self.env.company.id), str(date))
        self.env.cr.execute(sql)
        balance = self.env.cr.dictfetchall()

        return balance[0]
    
    def lineas(self, datos):
        totales = {}
        lineas_resumidas = {}
        lineas = []
        total_debe = 0
        total_haber = 0
        totales['saldo_inicial'] = 0
        totales['saldo_final'] = 0

        '''if datos['all_accounts']:
            account_list = None
            if datos['currency_id']:
                if datos['currency_id'][1] == 'GTQ':
                    self.env.cr.execute('select id from account_account aa where aa.currency_id is null or aa.currency_id = ' + str(
                        datos['currency_id'][0]) + ' and aa.internal_group != "off_balance" order by id')
                    accounts_list = [item[0]
                                     for item in self.env.cr.fetchall()]

                elif datos['currency_id'][1] == 'USD':
                    self.env.cr.execute('select id from account_account aa where aa.currency_id =' + str(
                        datos['currency_id'][0]) + ' and aa.internal_group != "off_balance" order by id')
                    accounts_list = [item[0]
                                     for item in self.env.cr.fetchall()]
            else:
                self.env.cr.execute(
                    'select id from account_account aa where aa.internal_group != "off_balance" order by id')
                accounts_list = [item[0] for item in self.env.cr.fetchall()]

            accounts_str = ','.join([str(x) for x in accounts_list])
        else:
            account_ids = [x for x in datos['cuentas_id']]'''
        accounts_str = ','.join([str(x) for x in datos['cuentas_id']])
        credit_accounts = ('liability', 'equity', 'income')
        debit_accounts = ('asset', 'expense', 'off_balance')

        sql = """
                select
                    ml.date as fecha_movimiento,
                    aa.internal_group as tipo_cuenta,
                    aa.id as cuenta_id,
                    aa.name as cuenta,
                    aa.code as codigo_cuenta,
                    ml.debit as debe,
                    ml.credit as haber,
                    am.name as poliza,
                    am.ref as descripcion

                from
                    account_move_line ml
                inner join account_account aa on
                    (ml.account_id = aa.id)
                inner join account_move am on
                    (am.id = ml.move_id)
                where
                    ml.date >= '%s'
                    and ml.date <= '%s'
                    and aa.id in (%s)
                    and am.state = 'posted'
                    and am.company_id = %s
                    and aa.internal_group != 'off_balance'
                group by
                    aa.id,
                    aa.id,
                    aa.name,
                    aa.code,
                    ml.debit,
                    ml.credit,
                    am.name,
                    am.ref,
                    ml.date
                order by
                    aa.id,
                    ml.date
            """ % (datos['fecha_desde'], datos['fecha_hasta'], accounts_str, str(self.env.company.id))
        self.env.cr.execute(sql)
        opening_balances = {}
        account_names = {}
        data_lines = {}

        if datos['grouping_type'] == 'daily':

            move_line_ids = self.env.cr.dictfetchall()

            for line in move_line_ids:

                new_line = {
                    'descripcion': line['descripcion'] if line['descripcion'] else '-',
                    'fecha_movimiento': line['fecha_movimiento'],
                    'codigo_cuenta': line['codigo_cuenta'],
                    'cuenta_id': line['cuenta_id'],
                    'poliza': line['poliza'],
                    'cuenta': line['cuenta'],
                    'haber': line['haber'],
                    'debe': line['debe']
                }

                if not line['cuenta_id'] in account_names:
                    account_id = line['cuenta_id']
                    account_balance = self.get_balance(
                        account_id, datos['fecha_desde'])
                    opening_balance = 0 if account_balance[
                        'account_balance'] is None else account_balance['account_balance']
                    opening_balances[line['cuenta_id']
                                     ] = 0 if account_balance['account_balance'] is None else account_balance['account_balance']
                    account_names[account_id] = [
                        line['cuenta'], opening_balance]

                if line['tipo_cuenta'] in credit_accounts:
                    opening_balances[account_id] += line['haber']
                    opening_balances[account_id] -= line['debe']
                elif line['tipo_cuenta'] in debit_accounts:
                    opening_balances[account_id] -= line['haber']
                    opening_balances[account_id] += line['debe']

                new_line['balance'] = opening_balances[account_id]

                if line['cuenta_id'] in data_lines:
                    account_id = line['cuenta_id']
                    if line['fecha_movimiento'] in data_lines[account_id]:
                        data_lines[account_id][line['fecha_movimiento']].append(new_line)
                    else:
                        line_ids = []
                        line_ids.append(new_line)
                        data_lines[account_id][line['fecha_movimiento']] = line_ids
                else:
                    new_date = {}
                    line_ids = []
                    account_id = line['cuenta_id']
                    new_line['balance'] = opening_balances[account_id]
                    line_ids.append(new_line)

                    new_date[line['fecha_movimiento']] = line_ids
                    data_lines[line['cuenta_id']] = new_date

            total_debe = 0
            total_haber = 0
            subtotales = {}
            for account_id in data_lines:
                account_ids = data_lines[account_id]
                subtotales[account_id] = {}
                for date in account_ids:
                    subtotal_debe = 0
                    subtotal_haber = 0
                    for line in account_ids[date]:
                        subtotal_debe += line['debe']
                        subtotal_haber += line['haber']
                    subtotales[account_id][date] = {
                        'subtotal_debe': subtotal_debe,
                        'subtotal_haber': subtotal_haber
                    }
                    total_haber += subtotal_haber
                    total_debe += subtotal_haber
            totales = {
                'total_debe': total_debe,
                'total_haber': total_haber
            }
            
            
            return {'data_lines': data_lines, 'account_names': account_names, 'opening_balances': opening_balances, 'subtotales':subtotales, 'totales':totales}

        elif datos['grouping_type'] == 'monthly':
            
            
            move_line_ids = self.env.cr.dictfetchall()
            for line in move_line_ids:
                new_line = {
                        #'saldo_inicial':  self.get_balance(line['cuenta_id'], datos['fecha_desde']),
                        'descripcion': line['descripcion'] if line['descripcion'] else '-',
                        'fecha_movimiento': line['fecha_movimiento'],
                        'codigo_cuenta': line['codigo_cuenta'],
                        'cuenta_id': line['cuenta_id'],
                        'poliza': line['poliza'],
                        'cuenta': line['cuenta'],
                        'haber': line['haber'],
                        'debe': line['debe']
                    }
                month_number = int(line['fecha_movimiento'].strftime('%-m'))
                month = self.get_month_name(month_number)
                
                account_id = line['cuenta_id']
                if not line['cuenta_id'] in account_names:
                    account_balance = self.get_balance(account_id, datos['fecha_desde'])
                    opening_balance = 0 if account_balance['account_balance'] is None else account_balance['account_balance']
                    opening_balances[account_id] = 0 if account_balance['account_balance'] is None else account_balance['account_balance']
                    account_names[account_id] = [line['cuenta'], opening_balance]

                if line['tipo_cuenta'] in credit_accounts:
                    opening_balances[account_id] += line['haber']
                    opening_balances[account_id] -= line['debe']
                elif line['tipo_cuenta'] in debit_accounts:
                    opening_balances[account_id] -= line['haber']
                    opening_balances[account_id] += line['debe']

                new_line['balance'] = opening_balances[account_id]
                if account_id in data_lines:
                    if month in data_lines[account_id]:
                        data_lines[account_id][month].append(new_line)
                    else:
                        month_data = []
                        month_data.append(new_line)
                        data_lines[account_id][month] = month_data
                else:
                    new_month = {}
                    line_ids = []
                    line_ids.append(new_line)
                    new_month[month] = line_ids
                    data_lines[account_id] = new_month
            
            return {'data_lines': data_lines, 'account_names': account_names, 'opening_balances': opening_balances}
            
    def get_month_name(self, month):
        switcher = {
            1: "Enero",
            2: "Febrero",
            3: "Marzo",
            4: "Abril",
            5: "Mayo",
            6: "Junio",
            7: "Julio",
            8: "Agosto",
            9: "Septiembre",
            10: "Octubre",
            11: "Noviembre",
            12: "Diciembre"
        }
        return switcher.get(month, " - ")
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

        fecha_inicio = str(tmp_inicio[2])+"/" + \
            str(tmp_inicio[1]+"/"+str(tmp_inicio[0]))
        fecha_final = str(tmp_final[2])+"/" + \
            str(tmp_final[1]+"/"+str(tmp_final[0]))
        data['fecha_inicio'] = fecha_inicio
        data['fecha_final'] = fecha_final
        

        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data,
            'docs': docs,
            'lineas': self.lineas,
            'company_id': self.env.company
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
