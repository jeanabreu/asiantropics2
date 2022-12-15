# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging


class SettlementExpensesSettlement(models.Model):
    _name = 'settlement_expenses'
    _description = 'Liquidación'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'settlement_date desc, name desc'

    settlement_date = fields.Date(string="Fecha", required=True)
    name = fields.Char(string="Descripcion", required=True)
    invoice_id = fields.One2many("account.move", "settlement_expenses_id", string="Facturas", domain=[('move_type', 'in', ('out_invoice', 'in_invoice'))])
    payment_id = fields.One2many("account.payment", "settlement_expenses_id", string="Pagos")
    company_id = fields.Many2one("res.company", string="Empresa", required=True, default=lambda self: self.env.company.id)
    journal_id = fields.Many2one("account.journal", string="Diario", required=True)
    account_move_id = fields.Many2one("account.move", string="Asiento")
    employee_id = fields.Many2one("hr.employee", string="Empleado")
    adjustment_journal_id = fields.Many2one("account.journal", string="Diario de desajuste")
    conversion_rate_ref = fields.Float(string="Tasa de conversión")

    # =========== TOTAL FIELDS ===========
    currency_id = fields.Many2one('res.currency', string="Moneda")
    invoice_total = fields.Monetary(string="Total de facturas", compute="get_invoice_totals")
    payment_total = fields.Monetary(string="Total de pagos", compute="get_payment_totals")
    final_balance = fields.Monetary(string="Balance final", compute="get_final_balance")

    def get_final_balance(self):
        for rec in self:
            # rec.invoice_total = rec.invoice_total * -1
            rec.final_balance = rec.payment_total - rec.invoice_total

    def get_invoice_totals(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        for rec in self:
            total = 0
            for invoice in rec.invoice_id:
                if invoice.move_type == 'in_invoice':
                    if invoice.currency_id.id != company_currency_id:
                        invoice_conversion_rate = 0
                        if not 'conversion_rate_ref' in self.env['account.move']._fields:
                            invoice_currency = self.env['res.currency.rate'].search([
                                ('currency_id', '=', invoice.currency_id.id),
                                ('name', '=', invoice.invoice_date),
                                ('company_id', '=', self.env.company.id)
                            ], limit=1)
                            invoice_conversion_rate = invoice_currency.rate
                            # invoice_conversion_rate = invoice.currency_id.with_context(date='2020-04-26').rate
                            invoice_amount = invoice.amount_total
                            if invoice_conversion_rate > 0:
                                invoice_amount = invoice.amount_total / invoice_conversion_rate
                        else:
                            invoice_conversion_rate = invoice.conversion_rate_ref
                            invoice_amount = invoice.amount_total * invoice_conversion_rate
                        
                        total += invoice_amount
                    else:
                        total += invoice.amount_total

            rec.invoice_total = total

    def get_payment_totals(self):
        company_currency_id = self.env.user.company_id.currency_id.id
        for rec in self:
            total = 0
            for payment in rec.payment_id:
                if payment.payment_type == 'outbound':
                    if payment.currency_id.id != company_currency_id:
                        outbound_currency = self.env['res.currency.rate'].search([
                            ('currency_id', '=', payment.currency_id.id),
                            ('name', '=', payment.date),
                            ('company_id', '=', self.env.company.id)
                        ], limit=1)
                        conversion_rate = outbound_currency.rate
                        payment_amount = payment.amount
                        if conversion_rate > 0:
                            payment_amount = payment.amount / conversion_rate
                        total += payment_amount
                    else:
                        total += payment.amount
                if payment.payment_type == 'inbound':
                    if payment.currency_id.id != company_currency_id:
                        inbound_currency = self.env['res.currency.rate'].search([
                            ('currency_id', '=', payment.currency_id.id),
                            ('name', '=', payment.date),
                            ('company_id', '=', self.env.company.id)
                        ], limit=1)
                        conversion_rate = inbound_currency.rate
                        payment_amount = payment.amount
                        if conversion_rate > 0:
                            payment_amount = payment.amount / conversion_rate
                        total -= payment_amount
                    else:
                        total -= payment.amount

            rec.payment_total = total

    def conciliar(self):
        for rec in self:
            lines = []

            company_currency_id = self.env.user.company_id.currency_id.id

            if len(rec.invoice_id) == 0:
                raise UserError('Debe asociar al menos una factura a la liquidación')
            if len(rec.payment_id) == 0:
                raise UserError('Debe asociar al menos un pago a la liquidación')

            total = 0
            vendor_account_id = 0
            last_vendor = []
            last_invoice = []
            message_list = ""
            for invoice in rec.invoice_id:
                if invoice.state == "draft":
                    message_list += 'La factura '+str(invoice.name)+' por un monto de '+str(round(invoice.amount_total, 2))+' no esta validada \n'

            if message_list != "":
                raise UserError(message_list)

            for invoice in rec.invoice_id:

                for invoice_lines in invoice.line_ids:

                    if invoice_lines.account_id.id is False:
                        raise UserError('El diario seleccionado en la factura no tiene un plan contable asignado')

                    if invoice_lines.account_id.reconcile:
                        if not invoice_lines.reconciled:
                            if invoice_lines.credit > 0:
                                total += round(invoice_lines.credit, 3) - round(invoice_lines.debit, 3)
                                total = round(total, 3)                                
                                lines.append(invoice_lines)
                        else:
                            raise UserError('La factura %s ya esta conciliada' % (invoice.name))


            for payment in rec.payment_id:
                payment_type = payment.payment_type

                for payment_line in payment.line_ids:

                    if payment_line.account_id.reconcile:
                        if not payment_line.reconciled:
                            if payment_type == 'outbound' and payment_line.debit > 0:
                                # total -= payment_line.debit - payment_line.credit
                                total = total - payment_line.debit
                                lines.append(payment_line)
                            if payment_type == 'inbound' and payment_line.credit > 0:
                                # total -= payment_line.debit - payment_line.credit
                                total = total + payment_line.credit
                                lines.append(payment_line)

                        else:
                            raise UserError('El cheque %s ya esta conciliado' % (payment.name))

            if round(total) != 0 and not rec.adjustment_journal_id:
                raise UserError('Debe seleccionar la cuenta de desajuste')

            pairs = []
            new_lines = []
            write_off_account_id = self.adjustment_journal_id.settlement_credit_account_id.id
            if total > 0:
                write_off_account_id = self.adjustment_journal_id.settlement_credit_account_id.id
            if total < 0:
                write_off_account_id = self.adjustment_journal_id.settlement_debit_account_id.id

            
            for line in lines:

                new_lines.append((0, 0, {
                    'name': line.name,
                    'debit': line.credit,
                    'credit': line.debit,
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    # 'journal_id': rec.journal_id.id,
                    'date_maturity': rec.settlement_date,
                }))

            if total != 0:
                new_lines.append((0, 0, {
                    'name': 'Diferencial en ' + rec.name,
                    'debit': -1 * total if total < 0 else 0,
                    'credit': total if total > 0 else 0,
                    # 'account_id': invoice.line_ids[0].account_id.id,
                    'account_id': write_off_account_id,
                    'date_maturity': rec.settlement_date
                }))
                
            move = self.env['account.move'].create({
                'line_ids': new_lines,
                'ref': rec.name,
                'date': rec.settlement_date,
                'journal_id': rec.journal_id.id,
                'move_type': 'entry',
                'auto_post': False
            })

            index = 0
            
            move._post(False)
            
            if total != 0 and move.state == 'posted':
                move_lines = move.line_ids
                for line in lines:
                    par = line | move_lines[index]
                    par.reconcile()
                    index += 1
            else:
                move_lines = move.line_ids
                for line in lines:
                    par = line | move_lines[index]
                    par.reconcile()
                    index += 1
                
            move.message_subscribe([p.id for p in [move.partner_id] if p not in move.sudo().message_partner_ids])

            self.write({'account_move_id': move.id})

        return True

    def cancelar(self):
        for rec in self:
            for l in rec.account_move_id.line_ids:
                if l.reconciled:
                    l.remove_move_reconcile()
            rec.account_move_id.button_cancel()
            rec.account_move_id.unlink()

        return True
