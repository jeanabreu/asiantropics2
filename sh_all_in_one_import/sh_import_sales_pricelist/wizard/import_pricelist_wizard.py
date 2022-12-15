# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class Product(models.Model):
    _inherit = 'product.product'

    sh_display_name = fields.Char('Compleate Name',related='display_name',search='_search_sh_display_name')

    def _search_sh_display_name(self, operator, value):
        product_ids = []
        for rec in self.search([]):
            if rec.sh_display_name and rec.sh_display_name == value:
                product_ids.append(rec.id)
        if operator == '=':
            return [('id', 'in', product_ids)]
        return []


class ImportPricelistWizard(models.TransientModel):
    _name = "sh.import.sale.pricelist"
    _description = "Import Pricelist wizard"

    @api.model
    def get_deafult_company(self):
        company_id = self.env.company
        return company_id

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], string="Product By", default='name')
    sh_applied_on = fields.Selection([
        ('2_product_category', 'Product Category'),
        ('1_product', 'Product'),
        ('0_product_variant', 'Product Variant')
    ], default='1_product', string="Applied On")
    sh_compute_price = fields.Selection([
        ('fixed', 'Fixed Price'),
        ('percentage', 'Percentage (discount)'),
        ('formula', 'Formula')
    ], string="Compute Price", default='fixed')
    sh_country_group_ids = fields.Many2many(
        'res.country.group', string="Country Groups")
    sh_base = fields.Selection([
        ('list_price', 'Sales Price'),
        ('standard_price', 'Cost'),
        ('pricelist', 'Other Pricelist')
    ], string='Based On', default='list_price')
    file = fields.Binary(string="File", required=True)
    company_id = fields.Many2one(
        'res.company', 'Company', default=get_deafult_company, required=True)

    def show_success_msg(self, counter, skipped_line_no):
        #open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully"
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        context['message'] = dic_msg

        return {
            'name': 'Success',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sh.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def import_pricelist_apply(self):
        pricelist_obj = self.env['product.pricelist']
        pricelist_line_obj = self.env['product.pricelist.item']
        if self:
            for rec in self:
                # For CSV
                if rec.import_type == 'csv':
                    counter = 1
                    skipped_line_no = {}
                    try:
                        file = str(base64.decodebytes(
                            rec.file).decode('utf-8'))
                        myreader = csv.reader(file.splitlines())
                        skip_header = True
                        running_pricelist = None
                        created_pricelist = False
                        creted_price_list = []
                        for row in myreader:
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue

                                if row[0] not in (None, "") and row[2] not in (None, ""):
                                    vals = {}

                                    if row[0] != running_pricelist:

                                        running_pricelist = row[0]
                                        pricelist_vals = {}
                                        if row[1] not in [None, ""]:
                                            pricelist_vals.update({
                                                'name': row[1],
                                                'company_id': self.company_id.id,
                                            })
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Name is empty. "
                                            counter = counter + 1
                                            continue
                                        if self.sh_country_group_ids:
                                            pricelist_vals.update({
                                                'country_group_ids': [(6, 0, self.sh_country_group_ids.ids)]
                                            })
                                        if pricelist_vals:
                                            created_pricelist = pricelist_obj.sudo().create(pricelist_vals)
                                            creted_price_list.append(
                                                created_pricelist.id)
                                    if created_pricelist:
                                        vals = {}
                                        field_nm = 'name'
                                        if self.product_by == 'name':
                                            field_nm = 'name'
                                        elif self.product_by == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.product_by == 'barcode':
                                            field_nm = 'barcode'
                                        if self.sh_applied_on == '2_product_category':
                                            search_category = self.env['product.category'].sudo().search(
                                                [('name', '=', row[2])], limit=1)
                                            if search_category:
                                                vals.update(
                                                    {'categ_id': search_category.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Category not found. "
                                                counter = counter + 1
                                                continue
                                        elif self.sh_applied_on == '1_product':
                                            search_product = self.env['product.template'].sudo().search(
                                                [(field_nm, '=', row[2])], limit=1)
                                            if search_product:
                                                vals.update(
                                                    {'product_tmpl_id': search_product.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product not found. "
                                                counter = counter + 1
                                                continue
                                        elif self.sh_applied_on == '0_product_variant':
                                            if self.product_by == 'name':
                                                field_nm = 'sh_display_name'
                                            search_product = self.env['product.product'].sudo().search(
                                                [(field_nm, '=', row[2])], limit=1)
                                            if search_product:
                                                vals.update(
                                                    {'product_id': search_product.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product Variant not found. "
                                                counter = counter + 1
                                                continue
                                        if row[3] not in [None, ""]:
                                            vals.update({
                                                'min_quantity': row[3],
                                            })
                                        if row[4] not in [None, ""]:
                                            cd = row[4]
                                            vals.update({
                                                'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                            })
                                        if row[5] not in [None, ""]:
                                            cd = row[5]
                                            vals.update({
                                                'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                            })
                                        if self.sh_compute_price == 'fixed':
                                            if row[6] not in [None, ""]:
                                                vals.update({
                                                    'fixed_price': row[6]
                                                })
                                        elif self.sh_compute_price == 'percentage':
                                            if row[7] not in [None, ""]:
                                                vals.update({
                                                    'percent_price': row[7]
                                                })
                                        elif self.sh_compute_price == 'formula':
                                            vals.update({
                                                'base': self.sh_base,
                                            })
                                            if row[8] not in [None, ""]:
                                                vals.update({
                                                    'price_round': row[8]
                                                })
                                            if row[9] not in [None, ""]:
                                                vals.update({
                                                    'price_discount': row[9]
                                                })
                                            if row[10] not in [None, ""]:
                                                vals.update({
                                                    'price_min_margin': row[10]
                                                })
                                            if row[11] not in [None, ""]:
                                                vals.update({
                                                    'price_max_margin': row[11]
                                                })
                                            if row[12] not in [None, ""]:
                                                vals.update({
                                                    'price_surcharge': row[12]
                                                })
                                            if self.sh_base == 'pricelist':
                                                if row[13] not in [None, ""]:
                                                    other_pricelist_id = self.env['product.pricelist'].sudo().search(
                                                        [('name', '=', row[13])], limit=1)
                                                    if other_pricelist_id:
                                                        vals.update({
                                                            'base_pricelist_id': other_pricelist_id.id,
                                                        })
                                                    else:
                                                        skipped_line_no[str(
                                                            counter)] = " - Other Pricelist not found. "
                                                        counter = counter + 1
                                                        continue
                                                else:
                                                    skipped_line_no[str(
                                                        counter)] = " - Other Pricelist not found. "
                                                    counter = counter + 1
                                                    continue
                                        vals.update({
                                            'pricelist_id': created_pricelist.id,
                                            'applied_on': self.sh_applied_on,
                                            'compute_price': self.sh_compute_price,
                                            'company_id': self.company_id.id,
                                        })
                                        if vals:
                                            pricelist_line_obj.create(vals)
                                            counter = counter + 1
                            except Exception as e:
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid " + ustr(e)
                                counter = counter + 1
                                continue
                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your csv file does not match with our format " + ustr(e)))
                    if counter > 1:
                        completed_records = len(creted_price_list)
                        res = self.show_success_msg(
                            completed_records, skipped_line_no)
                        return res
                elif self.import_type == 'excel':
                    counter = 1
                    skipped_line_no = {}
                    try:
                        wb = xlrd.open_workbook(
                            file_contents=base64.decodebytes(self.file))
                        sheet = wb.sheet_by_index(0)
                        skip_header = True
                        running_pricelist = None
                        created_pricelist = False
                        creted_price_list = []
                        for row in range(sheet.nrows):
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue
                                if sheet.cell(row, 0).value not in (None, "") and sheet.cell(row, 2).value not in (None, ""):
                                    vals = {}

                                    if sheet.cell(row, 0).value != running_pricelist:

                                        running_pricelist = sheet.cell(
                                            row, 0).value
                                        pricelist_vals = {}
                                        if sheet.cell(row, 1).value not in [None, ""]:
                                            pricelist_vals.update({
                                                'name': sheet.cell(row, 1).value,
                                                'company_id': self.company_id.id,
                                            })
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Name is empty. "
                                            counter = counter + 1
                                            continue
                                        if self.sh_country_group_ids:
                                            pricelist_vals.update({
                                                'country_group_ids': [(6, 0, self.sh_country_group_ids.ids)]
                                            })
                                        if pricelist_vals:
                                            created_pricelist = pricelist_obj.sudo().create(pricelist_vals)
                                            creted_price_list.append(
                                                created_pricelist.id)
                                    if created_pricelist:
                                        vals = {}
                                        field_nm = 'name'
                                        if self.product_by == 'name':
                                            field_nm = 'name'
                                        elif self.product_by == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.product_by == 'barcode':
                                            field_nm = 'barcode'
                                        if self.sh_applied_on == '2_product_category':
                                            search_category = self.env['product.category'].sudo().search(
                                                [('name', '=', sheet.cell(row, 2).value)], limit=1)
                                            if search_category:
                                                vals.update(
                                                    {'categ_id': search_category.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Category not found. "
                                                counter = counter + 1
                                                continue
                                        elif self.sh_applied_on == '1_product':
                                            search_product = self.env['product.template'].sudo().search(
                                                [(field_nm, '=', sheet.cell(row, 2).value)], limit=1)
                                            if search_product:
                                                vals.update(
                                                    {'product_tmpl_id': search_product.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product not found. "
                                                counter = counter + 1
                                                continue
                                        elif self.sh_applied_on == '0_product_variant':
                                            if self.product_by == 'name':
                                                field_nm = 'sh_display_name'
                                            search_product = self.env['product.product'].sudo().search(
                                                [(field_nm, '=', sheet.cell(row, 2).value)], limit=1)
                                            if search_product:
                                                vals.update(
                                                    {'product_id': search_product.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product Variant not found. "
                                                counter = counter + 1
                                                continue
                                        if sheet.cell(row, 3).value not in [None, ""]:
                                            vals.update({
                                                'min_quantity': sheet.cell(row, 3).value,
                                            })
                                        if sheet.cell(row, 4).value not in [None, ""]:
                                            cd = sheet.cell(row, 4).value
                                            vals.update({
                                                'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                            })
                                        if sheet.cell(row, 5).value not in [None, ""]:
                                            cd = sheet.cell(row, 5).value
                                            vals.update({
                                                'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                            })
                                        if self.sh_compute_price == 'fixed':
                                            if sheet.cell(row, 6).value not in [None, ""]:
                                                vals.update({
                                                    'fixed_price': sheet.cell(row, 6).value
                                                })
                                        elif self.sh_compute_price == 'percentage':
                                            if sheet.cell(row, 7).value not in [None, ""]:
                                                vals.update({
                                                    'percent_price': sheet.cell(row, 7).value
                                                })
                                        elif self.sh_compute_price == 'formula':
                                            vals.update({
                                                'base': self.sh_base,
                                            })
                                            if sheet.cell(row, 8).value not in [None, ""]:
                                                vals.update({
                                                    'price_round': sheet.cell(row, 8).value
                                                })
                                            if sheet.cell(row, 9).value not in [None, ""]:
                                                vals.update({
                                                    'price_discount': sheet.cell(row, 9).value
                                                })
                                            if sheet.cell(row, 10).value not in [None, ""]:
                                                vals.update({
                                                    'price_min_margin': sheet.cell(row, 10).value
                                                })
                                            if sheet.cell(row, 11).value not in [None, ""]:
                                                vals.update({
                                                    'price_max_margin': sheet.cell(row, 11).value
                                                })
                                            if sheet.cell(row, 12).value not in [None, ""]:
                                                vals.update({
                                                    'price_surcharge': sheet.cell(row, 12).value
                                                })
                                            if self.sh_base == 'pricelist':
                                                if sheet.cell(row, 13).value not in [None, ""]:
                                                    other_pricelist_id = self.env['product.pricelist'].sudo().search(
                                                        [('name', '=', sheet.cell(row, 13).value)], limit=1)
                                                    if other_pricelist_id:
                                                        vals.update({
                                                            'base_pricelist_id': other_pricelist_id.id,
                                                        })
                                                    else:
                                                        skipped_line_no[str(
                                                            counter)] = " - Other Pricelist not found. "
                                                        counter = counter + 1
                                                        continue
                                                else:
                                                    skipped_line_no[str(
                                                        counter)] = " - Other Pricelist not found. "
                                                    counter = counter + 1
                                                    continue
                                        vals.update({
                                            'pricelist_id': created_pricelist.id,
                                            'applied_on': self.sh_applied_on,
                                            'compute_price': self.sh_compute_price,
                                            'company_id': self.company_id.id,
                                        })
                                        if vals:
                                            pricelist_line_obj.create(vals)
                                            counter = counter + 1

                            except Exception as e:
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid " + ustr(e)
                                counter = counter + 1
                                continue

                    except Exception:
                        raise UserError(
                            _("Sorry, Your excel file does not match with our format"))

                    if counter > 1:
                        completed_records = len(creted_price_list)
                        res = self.show_success_msg(
                            completed_records, skipped_line_no)
                        return res
