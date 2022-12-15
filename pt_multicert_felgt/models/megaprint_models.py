# -*- encoding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID


class PtMuticertFelgtMepagrintFelgtJsonSent(models.Model):
    _name = "pt_multicert_felgt.megaprint_json_sent"
    _description = "Records the JSONs generated on the api calls"

    name = fields.Char(string="Nombre",  required=True)
    data_content = fields.Char(string="content")
    api_sent = fields.Char(string="api sent")
