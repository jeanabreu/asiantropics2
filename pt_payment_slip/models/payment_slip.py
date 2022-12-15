# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import get_lang
from odoo.addons.mail.wizard.mail_compose_message import _reopen

import base64


class PtPaymentSlip(models.Model):
    _name = 'pt_payment_slip.slip_config'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _description = 'Contraseña de pago'

    # name = fields.Char(string='Número de pago', required=True)
    name = fields.Char(string="Nombre", required=True, copy=False, readonly=True, index=True, default=lambda self: self._get_next_sequence())
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company.id)
    date = fields.Date(string='Fecha de recepción', default=fields.Date.today())
    partner_id = fields.Many2one('res.partner', string="Proveedor", required=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Término de pago', oldname='payment_term')
    order_number = fields.Char(string="Orden de compra", required=True)
    order_date = fields.Date(string='Fecha de recepción', default=fields.Date.today())

    invoice_id = fields.Many2one("account.move", string="Factura de proveedor", domain=['type', '=', 'in_invoice'])
    invoice_serial = fields.Char(string="Factura serie", compute="_get_invoice_ref")
    invoice_number = fields.Char(string="Factura numero", compute="_get_invoice_ref")
    amount = fields.Monetary(string='Monto')
    currency_id = fields.Many2one('res.currency', string="Moneda")

    payment_date = fields.Date(string='Fecha de Pago', required=True)
    note = fields.Text(string='Nota')

    invoice_ref = fields.Char(string="Referencia", compute="_get_invoice_ref")

    def action_edit_payment_slip(self):
        vendor_id = self.env.context.get('vendor_id')
        invoice_id = self.env.context.get('active_id')
        return {
            'name': _('Crear Contraseña de pago'),
            'res_model': 'pt_payment_slip.slip_config',
            'view_mode': 'form',
            'view_id': self.env.ref('pt_payment_slip.pt_payment_slip_slip_config_form_view').id,
            'view_mode': 'form',
            'context': {'default_partner_id': vendor_id, 'default_invoice_id': invoice_id},
            'target': 'edit',
            'type': 'ir.actions.act_window',
        }

    def action_create_payment_slip(self):
        
        vendor_id = self.env.context.get('vendor_id')
        invoice_id = self.env.context.get('active_id')
        
        return {
            'name': _('Crear Contraseña de pago'),
            'res_model': 'pt_payment_slip.slip_config',
            'view_mode': 'form',
            'view_id': self.env.ref('pt_payment_slip.pt_payment_slip_invoice_form_view').id,
            'view_mode': 'form',
            'context': {'default_partner_id': vendor_id, 'default_invoice_id': invoice_id},
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def _get_invoice_ref(self):
        for rec in self:
            print('---CALLL')
            if rec.invoice_id:
                rec.invoice_ref = rec.invoice_id.ref
                rec.invoice_serial = rec.invoice_id.provider_invoice_serial
                rec.invoice_number = rec.invoice_id.provider_invoice_number
            else:
                rec.invoice_ref = ""
                rec.invoice_serial = ""
                rec.invoice_number = ""

    signed_by_employee_id = fields.Many2one("hr.employee", string="Aprobado por", required=True)

    state = fields.Selection(selection=[
            ('draft', 'Borrador'),
            ('posted', 'Generada'),
            ('cancel', 'Cancelada')
        ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft')

    def action_sent_payment_slip(self):
        self.ensure_one()
        template = self.env.ref('pt_payment_slip.pt_payment_slip_email_template', raise_if_not_found=False)
        compose_form = self.env.ref('pt_payment_slip.payment_slip_send_wizard_form', raise_if_not_found=False)
        lang = get_lang(self.env)
        ctx = dict(
            default_model='pt_payment_slip.slip_config',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            force_email=True
        )
        return {
            'name': _('Enviar contraseña de pago'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'res_model': 'pt_payment_slip.payment_send',
            'target': 'new',
            'context': ctx,
        }

    @api.model
    def create(self, vals):
        operation_sequence = self.env['ir.sequence'].next_by_code('pt_payment_slip.payment_slip')
        vals['name'] = operation_sequence
        vals['state'] = "posted"
        if 'order_number' in vals:
            if vals['order_number'] == "":
                raise ValidationError('Debe ingresar la orden.')
        
        res = super(PtPaymentSlip, self).create(vals)
        
        return res

    def create_payment_slip(self):
        action_vals = {
            'name': _('Contraseña'),
            'res_id': self.id,
            'res_model': 'pt_payment_slip.slip_config',
            'view_id': False,
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
        }
        return action_vals

    def _get_next_sequence(self):
        
        sequence_data_query = self.env['ir.sequence'].search([
            ('code', '=', 'pt_payment_slip.payment_slip')
        ])
        operation_sequence = ""
        padding = 0
        padding_string = ""
        prefix = ""
        for sequence_data in sequence_data_query:
            operation_sequence = sequence_data['number_next_actual']
            prefix = sequence_data['prefix']
            padding = sequence_data['padding']

        for i in range(0, padding-len(str(operation_sequence))):
            padding_string += "0"

        operation_sequence = prefix+padding_string+str(operation_sequence)
        
        return operation_sequence

    '''@api.onchange('order_number')
    def _onchange_order_number(self):
        
        
        validate_invoice_id_query = self.env['pt_payment_slip.slip_config'].search([
            ('order_number', '=', self.order_number)
        ])

        if len(validate_invoice_id_query) > 0:
            payment_slip_name = ""
            for payment_slip in validate_invoice_id_query:
                payment_slip_name = payment_slip.name

            raise ValidationError('Ya existe una contraseña de pago para el número de orden ingresada ('+payment_slip_name+')')'''
        
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        
        if not self.partner_id:
            return {}
        self.payment_term_id = self.partner_id.property_supplier_payment_term_id
        return {}

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        
        validate_invoice_id_query = self.env['pt_payment_slip.slip_config'].search([
            ('invoice_id', '=', self.invoice_id.id)
        ])

        if len(validate_invoice_id_query) > 0:
            payment_slip_name = ""
            for payment_slip in validate_invoice_id_query:
                payment_slip_name = payment_slip.name

            raise ValidationError('Ya existe una contraseña de pago para la factura seleccionada ('+payment_slip_name+')')

        purchase_order_query = self.env['purchase.order'].search([
            ('invoice_ids', 'in', (self.invoice_id.id))
        ])

        order_number = ""
        for purchase_order in purchase_order_query:
            order_number = purchase_order.name

        self.order_number = order_number

        if not self.invoice_id:
            return {}
        self.currency_id = self.invoice_id.currency_id
        self.amount = self.invoice_id.amount_total
        return {}

    @api.onchange('payment_term_id', 'date')
    def _onchange_payment_term_date_invoice(self):
        
        date = self.date
        if not date:
            date = fields.Date.context_today(self)
        if self.payment_term_id:
            pterm = self.payment_term_id
            pterm_list = pterm.with_context(currency_id=self.company_id.currency_id.id).compute(value=1, date_ref=date)[0]
            payment_date = pterm_list[0]
            if payment_date:
                self.payment_date = payment_date
            d = self.payment_date
            # TODO: Buscar manera de que se pueda indicar que dias se puede realizar el pago
            while d.weekday() != 4:
                d += timedelta(days=1)
            self.payment_date = d
        elif self.payment_date and (date > self.payment_date):
            self.payment_date = date
        


class PtPaymentSlipPaymentSend(models.TransientModel):
    _name = 'pt_payment_slip.payment_send'
    _inherits = {'mail.compose.message': 'composer_id'}
    _description = 'Account Invoice Send'

    is_email = fields.Boolean('Email', default=True)
    is_print = fields.Boolean('Print', default=False)
    printed = fields.Boolean('Is Printed', default=False)
    composer_id = fields.Many2one('mail.compose.message', string='Composer', required=True, ondelete='cascade')
    template_id = fields.Many2one('mail.template', 'Use template', index=True, domain="[('model', '=', 'pt_payment_slip.slip_config')]")

    @api.model
    def default_get(self, fields):
        res = super(PtPaymentSlipPaymentSend, self).default_get(fields)
        res_ids = self._context.get('active_ids')

        composer = self.env['mail.compose.message'].create({
            'composition_mode': 'comment' if len(res_ids) == 1 else 'mass_mail',
        })
        res.update({
            'composer_id': composer.id,
        })
        return res

    @api.onchange('template_id')
    def onchange_template_id(self):
        for wizard in self:
            if wizard.composer_id:
                wizard.composer_id.template_id = wizard.template_id.id
                wizard.composer_id._onchange_template_id_wrapper()

    @api.onchange('is_email')
    def onchange_is_email(self):
        if self.is_email:
            if not self.composer_id:
                res_ids = self._context.get('active_ids')
                self.composer_id = self.env['mail.compose.message'].create({
                    'composition_mode': 'comment' if len(res_ids) == 1 else 'mass_mail',
                    'template_id': self.template_id.id
                })
            self.composer_id._onchange_template_id_wrapper()

    def _send_email(self):
        if self.is_email:
            self.composer_id._action_send_mail()
            if self.env.context.get('mark_invoice_as_sent'):
                self.write({'invoice_sent': True})

    def send_and_print_action(self):
        self.ensure_one()
        # Send the mails in the correct language by splitting the ids per lang.
        # This should ideally be fixed in mail_compose_message, so when a fix is made there this whole commit should be reverted.
        # basically self.body (which could be manually edited) extracts self.template_id,
        # which is then not translated for each customer.

        self._send_email()
        return {'type': 'ir.actions.act_window_close'}
