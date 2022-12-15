# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
import time

_logger = logging.getLogger(__name__)
        
class L10nGtExtraCheckReport(models.TransientModel):
    _name = "l10n_gt_extra.check_report"
    _description = "Check Report"
    
    journal_id = fields.Many2many('account.journal', string='Diario')
    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    
    