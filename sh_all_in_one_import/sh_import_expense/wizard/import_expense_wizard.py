# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
import logging

_logger = logging.getLogger(__name__)

class ImportPartnerWizard(models.TransientModel):
    _name = "import.expense.wizard"
    _description = "Import customer or supplier wizard"

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)
    expense_type = fields.Selection([('expense','Expense'),('expense_sheet','Expense Sheet')],string="Import",default="expense")
    employee_type = fields.Selection([('name','Name'),('work_phone','Work Phone'),('work_email','Work Email'),('badge_id','Badge ID')],string="Employee By",default="name")
    product_type = fields.Selection([('name','Name'),('internal_ref','Internal Refrence'),('barcode','Barcode')],string="Product By",default="name")

    def show_success_msg(self, counter, skipped_line_no):
        # open the new success message box
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
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def import_expense_apply(self):
        if self.file and self.expense_type == 'expense':
            if self.import_type == 'csv':
                counter = 1
                skipped_line_no = {}
                try:
                    file = str(base64.decodebytes(self.file).decode('utf-8'))
                    myreader = csv.reader(file.splitlines())
                    skip_header = True

                    for row in myreader:
                        try:
                            if skip_header:
                                skip_header = False
                                counter = counter + 1
                                continue
                            if row[0] != '':
                                vals = {
                                    'name' : row[0],
                                    'unit_amount' : row[2],
                                    'quantity' : row[3],
                                    'reference' : row[4],
                                    'date' : row[5] if row[5] else False,
                                    'description' : row[10]
                                }
                                if row[1] != '':
                                    domain = []
                                    if self.product_type == 'name':
                                        domain.append(('name', '=', row[1]))
                                    elif self.product_type == 'internal_ref':
                                        domain.append(('default_code', '=', row[1]))
                                    elif self.product_type == 'barcode':
                                        domain.append(('barcode', '=', row[1]))
                                    search_product = self.env['product.product'].search(domain, limit=1)
                                    if search_product:
                                        vals.update(
                                            {'product_id': search_product.id})
                                        if search_product.uom_id:
                                            vals.update({
                                                'product_uom_id' : search_product.uom_id.id
                                            })
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        continue

                                if row[6] != '':
                                    search_account = self.env["account.account"].search(
                                        [('code', '=', row[6])], limit=1)
                                    if search_account:
                                        vals.update({'account_id': search_account.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Account not found. "
                                        counter = counter + 1
                                        continue

                                if row[7] != '':
                                    domain = []
                                    if self.employee_type == 'name':
                                        domain.append(('name', '=', row[7]))
                                    elif self.employee_type == 'work_phone':
                                        domain.append(('work_phone', '=', row[7]))
                                    elif self.employee_type == 'work_email':
                                        domain.append(('work_email', '=', row[7]))
                                    elif self.employee_type == 'badge_id':
                                        domain.append(('barcode', '=', row[7]))
                                    search_employee = self.env["hr.employee"].search(domain, limit=1)
                                    if search_employee:
                                        vals.update(
                                            {'employee_id': search_employee.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Employee not found. "
                                        counter = counter + 1
                                        continue

                                if row[8] != '':
                                    search_cuurency = self.env["res.currency"].search(
                                        [('name', '=', row[8])], limit=1)
                                    if search_cuurency:
                                        vals.update({'currency_id': search_cuurency.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Currency not found. "
                                        counter = counter + 1
                                        continue

                                if row[9] != '':
                                    if row[9] == 'Employee' or row[9] == 'employee':
                                        vals['payment_mode'] = 'own_account'
                                    elif row[9] == 'company' or row[9] == 'Company':
                                        vals['payment_mode'] = 'company_account'
                                create_exp = self.env['hr.expense'].create(vals)
                                if create_exp:
                                    counter += 1
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Description is empty. "
                                counter = counter + 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue

                except Exception:
                    raise UserError(
                        _("Sorry, Your csv file does not match with our format"))

                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res

            if self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
                try:
                    wb = xlrd.open_workbook(
                        file_contents=base64.decodebytes(self.file))
                    sheet = wb.sheet_by_index(0)
                    skip_header = True
                    for row in range(sheet.nrows):
                        try:
                            if skip_header:
                                skip_header = False
                                counter = counter + 1
                                continue
                            if sheet.cell(row, 0).value != '':
                                vals = {
                                    'name' : sheet.cell(row, 0).value,
                                    'unit_amount' : sheet.cell(row, 2).value if sheet.cell(row, 2).value else 0.00,
                                    'quantity' : sheet.cell(row, 3).value if sheet.cell(row, 3).value else 1,
                                    'reference' : sheet.cell(row, 4).value if sheet.cell(row, 4).value else False,
                                    'date' : sheet.cell(row, 5).value if sheet.cell(row, 5).value else False,
                                    'description' : sheet.cell(row, 10).value if sheet.cell(row, 10).value else False
                                }
                                if sheet.cell(row, 9).value != '':
                                    if sheet.cell(row, 9).value == 'Employee' or sheet.cell(row, 9).value == 'employee':
                                        vals['payment_mode'] = 'own_account'
                                    elif sheet.cell(row, 9).value == 'company' or sheet.cell(row, 9).value == 'Company':
                                        vals['payment_mode'] = 'company_account'

                                if sheet.cell(row, 1).value != '':
                                    domain = []
                                    if self.product_type == 'name':
                                        domain.append(('name', '=', sheet.cell(row, 1).value))
                                    elif self.product_type == 'internal_ref':
                                        domain.append(('default_code', '=', sheet.cell(row, 1).value))
                                    elif self.product_type == 'barcode':
                                        domain.append(('barcode', '=', sheet.cell(row, 1).value))
                                    search_product = self.env['product.product'].search(domain, limit=1)
                                    if search_product:
                                        vals.update(
                                            {'product_id': search_product.id})
                                        if search_product.uom_id:
                                            vals.update({
                                                'product_uom_id' : search_product.uom_id.id
                                            })
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        continue

                                if sheet.cell(row, 6).value != '':
                                    search_account = self.env["account.account"].search(
                                        [('code', '=', sheet.cell(row, 6).value)], limit=1)
                                    if search_account:
                                        vals.update({'account_id': search_account.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Account not found. "
                                        counter = counter + 1
                                        continue

                                if sheet.cell(row, 7).value != '':
                                    domain = []
                                    if self.employee_type == 'name':
                                        domain.append(('name', '=', sheet.cell(row, 7).value))
                                    elif self.employee_type == 'work_phone':
                                        domain.append(('work_phone', '=', sheet.cell(row, 7).value))
                                    elif self.employee_type == 'work_email':
                                        domain.append(('work_email', '=', sheet.cell(row, 7).value))
                                    search_employee = self.env["hr.employee"].search(domain, limit=1)
                                    if search_employee:
                                        vals.update(
                                            {'employee_id': search_employee.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Employee not found. "
                                        counter = counter + 1
                                        continue

                                if sheet.cell(row, 8).value != '':
                                    search_cuurency = self.env["res.currency"].search(
                                        [('name', '=', sheet.cell(row, 8).value)], limit=1)
                                    if search_cuurency:
                                        vals.update({'currency_id': search_cuurency.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Currency not found. "
                                        counter = counter + 1
                                        continue
                                create_exp = self.env['hr.expense'].create(vals)
                                if create_exp:
                                    counter += 1
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Description is empty. "
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
                    completed_records = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res
        if self.file and self.expense_type == 'expense_sheet':
            if self.import_type == 'csv':
                counter = 1
                skipped_line_no = {}
                running_exp = None
                created_exp = False
                try:
                    file = str(base64.decodebytes(self.file).decode('utf-8'))
                    myreader = csv.reader(file.splitlines())
                    skip_header = True

                    for row in myreader:
                        try:
                            if skip_header:
                                skip_header = False
                                counter = counter + 1
                                continue
                            if row[0] != running_exp:
                                running_exp = row[0]
                                vals = {
                                    'name' : row[1]
                                }
                                if row[2] != '':
                                    domain = []
                                    if self.employee_type == 'name':
                                        domain.append(('name', '=', row[2]))
                                    elif self.employee_type == 'work_phone':
                                        domain.append(('work_phone', '=', row[2]))
                                    elif self.employee_type == 'work_email':
                                        domain.append(('work_email', '=', row[2]))
                                    search_employee = self.env["hr.employee"].search(domain, limit=1)
                                    if search_employee:
                                        vals.update(
                                            {'employee_id': search_employee.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Employee not found. "
                                        counter = counter + 1
                                        continue
                                if row[3] != '':
                                    search_manager = self.env["res.users"].search([('name', '=', row[3])], limit=1)
                                    if search_manager:
                                        vals.update(
                                            {'user_id': search_manager.id})
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Manager not found. "
                                        counter = counter + 1
                                        continue
                                created_exp = self.env['hr.expense.sheet'].create(vals)
                            if created_exp:
                                if row[4] != '':
                                    exp_vals = {
                                        'name' : row[4],
                                        'unit_amount' : row[6],
                                        'quantity' : row[7],
                                        'reference' : row[8],
                                        'date' : row[9] if row[9] else False,
                                        'description' : row[13],
                                        'employee_id' : created_exp.employee_id.id,
                                        'sheet_id' : created_exp.id
                                    }
                                    if row[5] != '':
                                        domain = []
                                        if self.product_type == 'name':
                                            domain.append(('name', '=', row[5]))
                                        elif self.product_type == 'internal_ref':
                                            domain.append(('default_code', '=', row[5]))
                                        elif self.product_type == 'barcode':
                                            domain.append(('barcode', '=', row[5]))
                                        search_product = self.env['product.product'].search(domain, limit=1)
                                        if search_product:
                                            exp_vals.update(
                                                {'product_id': search_product.id})
                                            if search_product.uom_id:
                                                exp_vals.update({
                                                    'product_uom_id' : search_product.uom_id.id
                                                })
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Product not found. "
                                            counter = counter + 1
                                            continue

                                    if row[10] != '':
                                        search_account = self.env["account.account"].search(
                                            [('code', '=', row[10])], limit=1)
                                        if search_account:
                                            exp_vals.update({'account_id': search_account.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Account not found. "
                                            counter = counter + 1
                                            continue
                                    if row[11] != '':
                                        search_cuurency = self.env["res.currency"].search(
                                            [('name', '=', row[11])], limit=1)
                                        if search_cuurency:
                                            exp_vals.update({'currency_id': search_cuurency.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Currency not found. "
                                            counter = counter + 1
                                            continue

                                    if row[12] != '':
                                        if row[12] == 'Employee' or row[12] == 'employee':
                                            exp_vals['payment_mode'] = 'own_account'
                                        elif row[12] == 'company' or row[12] == 'Company':
                                            exp_vals['payment_mode'] = 'company_account'

                                    create_exp = self.env['hr.expense'].create(exp_vals)
                                    if create_exp:
                                        counter += 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Description is empty. "
                                    counter = counter + 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue

                except Exception:
                    raise UserError(
                        _("Sorry, Your csv file does not match with our format"))

                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res

            if self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
                running_exp = None
                created_exp = False
                try:
                    wb = xlrd.open_workbook(
                        file_contents=base64.decodebytes(self.file))
                    sheet = wb.sheet_by_index(0)
                    skip_header = True
                    for row in range(sheet.nrows):
                        try:
                            if skip_header:
                                skip_header = False
                                counter = counter + 1
                                continue
                            if sheet.cell(row, 0).value != '':
                                if sheet.cell(row, 0).value != running_exp:
                                    running_exp = sheet.cell(row, 0).value
                                    vals = {
                                        'name' : sheet.cell(row, 1).value
                                    }
                                    if sheet.cell(row, 2).value != '':
                                        domain = []
                                        if self.employee_type == 'name':
                                            domain.append(('name', '=', sheet.cell(row, 2).value))
                                        elif self.employee_type == 'work_phone':
                                            domain.append(('work_phone', '=', sheet.cell(row, 2).value))
                                        elif self.employee_type == 'work_email':
                                            domain.append(('work_email', '=', sheet.cell(row, 2).value))
                                        search_employee = self.env["hr.employee"].search(domain, limit=1)
                                        if search_employee:
                                            vals.update(
                                                {'employee_id': search_employee.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Employee not found. "
                                            counter = counter + 1
                                            continue
                                    if sheet.cell(row, 3).value != '':
                                        search_manager = self.env["res.users"].search([('name', '=', sheet.cell(row, 3).value)], limit=1)
                                        if search_manager:
                                            vals.update(
                                                {'user_id': search_manager.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Manager not found. "
                                            counter = counter + 1
                                            continue
                                    created_exp = self.env['hr.expense.sheet'].create(vals)
                                if created_exp:
                                    if sheet.cell(row, 4).value != '':
                                        exp_vals = {
                                            'name' : sheet.cell(row, 4).value,
                                            'unit_amount' : sheet.cell(row, 6).value if sheet.cell(row, 6).value else 0.00,
                                            'quantity' : sheet.cell(row, 7).value if sheet.cell(row, 7).value else 1,
                                            'reference' : sheet.cell(row, 8).value if sheet.cell(row, 8).value else False,
                                            'date' : sheet.cell(row, 9).value if sheet.cell(row, 9).value else False,
                                            'description' : sheet.cell(row, 13).value if sheet.cell(row, 13).value else False,
                                            'employee_id' : created_exp.employee_id.id,
                                            'sheet_id' : created_exp.id
                                        }
                                        if sheet.cell(row, 12).value != '':
                                            if sheet.cell(row, 12).value == 'Employee' or sheet.cell(row, 12).value == 'employee':
                                                exp_vals['payment_mode'] = 'own_account'
                                            elif sheet.cell(row, 12).value == 'company' or sheet.cell(row, 12).value == 'Company':
                                                exp_vals['payment_mode'] = 'company_account'

                                        if sheet.cell(row, 5).value != '':
                                            domain = []
                                            if self.product_type == 'name':
                                                domain.append(('name', '=', sheet.cell(row, 5).value))
                                            elif self.product_type == 'internal_ref':
                                                domain.append(('default_code', '=', sheet.cell(row, 5).value))
                                            elif self.product_type == 'barcode':
                                                domain.append(('barcode', '=', sheet.cell(row, 5).value))
                                            search_product = self.env['product.product'].search(domain, limit=1)
                                            if search_product:
                                                exp_vals.update(
                                                    {'product_id': search_product.id})
                                                if search_product.uom_id:
                                                    exp_vals.update({
                                                        'product_uom_id' : search_product.uom_id.id
                                                    })
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product not found. "
                                                counter = counter + 1
                                                continue

                                        if sheet.cell(row, 10).value != '':
                                            search_account = self.env["account.account"].search(
                                                [('code', '=', sheet.cell(row, 10).value)], limit=1)
                                            if search_account:
                                                exp_vals.update({'account_id': search_account.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Account not found. "
                                                counter = counter + 1
                                                continue

                                        if sheet.cell(row, 11).value != '':
                                            search_cuurency = self.env["res.currency"].search(
                                                [('name', '=', sheet.cell(row, 11).value)], limit=1)
                                            if search_cuurency:
                                                exp_vals.update({'currency_id': search_cuurency.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Currency not found. "
                                                counter = counter + 1
                                                continue
                                        all_created = self.env['hr.expense'].create(exp_vals)
                                        if all_created:
                                            counter += 1
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Description is empty. "
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
                    completed_records = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res
