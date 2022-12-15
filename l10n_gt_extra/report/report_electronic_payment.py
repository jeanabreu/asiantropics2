# -*- encoding: utf-8 -*-

from odoo import api, models
import logging
from datetime import datetime
import locale

_logger = logging.getLogger(__name__)


class ReportElectronicPayment(models.AbstractModel):
    _name = 'report.l10n_gt_extra.report_electronic_payment'
    _description = 'Report Diario'

    def lines(self, data):
        lines = []

        '''invoices = self.env['account.move'].search([
            ('id ', 'in', data['invoice_ids']),
        ], order="invoice_date_due")'''
        invoices = self.env['account.move'].browse(data['invoice_ids'])
        for invoice in invoices:
            amount = invoice.amount_residual_signed * -1
            centros = ""
            for invoice_line in invoice.invoice_line_ids:
                if invoice_line.analytic_account_id:
                    centros += " " + invoice_line.analytic_account_id.name
            new_line = {
                "name": invoice.name,
                "invoice_date": invoice.invoice_date_due,
                "amount": amount,
                "isr": invoice.tax_withold_amount,
                "analytic_account": centros
            }
            lines.append(new_line)

        return lines

    @api.model
    def _get_report_values(self, docids, data=None):

        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        form_data = data['form']
        date_obj = datetime.strptime(form_data['payment_date'], '%Y-%m-%d')
        payment_date_text = self.current_date_format(date_obj, False)

        date_obj = datetime.strptime(form_data['request_date'], '%Y-%m-%d')
        request_date_text = self.current_date_format(date_obj)

        partner_vat = ""
        if form_data['partner_id'][0]:
            partner_data = self.env['res.partner'].search([
                ('id', '=', form_data['partner_id'][0])
            ], limit=1)
            partner_vat = partner_data.vat

            total_credit_notes = 0
            invoices = self.env['account.move'].browse(form_data['invoice_ids'])
            for invoice in invoices:
                credit_notes = self.env['account.move'].search([
                    ('reversed_entry_id', '=', invoice.id)
                ])
                if credit_notes:
                    total_credit_notes = credit_notes.amount_total_signed

        print('DATA', data['form'])
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'payment_date': payment_date_text,
            'request_date': request_date_text,
            'vat_partner': partner_vat,
            'docs': docs,
            'total_credit_notes': total_credit_notes,
            'lines': self.lines(data['form']),
            'company_id': self.env['res.company'].browse(
                self.env.user.company_id.id),
        }

    def current_date_format(self, date, weekday_label=True):
        months = ("Enero", "Febrero", "Marzo", "Abri", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
        weekdays = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
        weekday = date.weekday()
        day = date.day
        month = months[date.month - 1]
        year = date.year
        text_weekday = weekdays[weekday]
        if weekday_label:
            messsage = "{} {} de {} del {}".format(text_weekday, day, month, year)
        else:
            messsage = "{} de {} del {}".format(day, month, year)
        return messsage
