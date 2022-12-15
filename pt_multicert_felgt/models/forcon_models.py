# -*- encoding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID


class PtMuticertFelgtForconXmlSent(models.Model):
    _name = "pt_multicert_felgt.forcon_xml_sent"
    _description = "Records the XML sent to forcon"

    name = fields.Char(string="Nombre",  required=True)
    data_content = fields.Char(string="content")
    api_sent = fields.Char(string="api sent")