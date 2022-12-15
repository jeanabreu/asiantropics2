# Copyright 2015 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReportAction(models.Model):
    _inherit = "ir.actions.report"

    report_type = fields.Selection(
        selection_add=[("g4s_pdf", "G4S PDF")], ondelete={"g4s_pdf": "set default"}
    )
    
    @api.model
    def _render_g4s_pdf(self, docids):
        report_model_name = "report.g4s_pdf.abstract"
        
        report_model = self.env.get(report_model_name)
        if report_model is None:
            raise UserError(_("%s model was not found") % report_model_name)
        return (
            report_model.with_context(active_model=self.model)
            .sudo(False)
            .generate_g4s_pdf(docids)  # noqa
        )
    
    @api.model
    def _get_report_from_converter(self, report_name):
        
        context = self.env["res.users"].context_get()
        
        report_obj = self.env["ir.actions.report"].with_context(**context).search([
            ("report_type", "=", "g4s_pdf"),
        ], limit=1)
        
        
        
        return report_obj