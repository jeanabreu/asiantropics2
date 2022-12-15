# -*- encoding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID


class PtMuticertFelgtDigifactFelgtAuthTokens(models.Model):
    _name = "pt_multicert_felgt.digifact_auth_tokens"
    _description = "Records the generated payments for each employee and payroll"

    name = fields.Char(string="Nombre",  required=True)
    auth_token = fields.Char(string="Token", required=True)
    expiration_date = fields.Datetime(string="Fecha de vencimiento", required=True)


class PtMuticertFelgtDigifactFelgtXmlSent(models.Model):
    _name = "pt_multicert_felgt.digifact_xml_sent"
    _description = "Records the XMLs generated on the api calls"

    name = fields.Char(string="Nombre",  required=True)
    xml_content = fields.Char(string="content")
    api_sent = fields.Char(string="api sent")
