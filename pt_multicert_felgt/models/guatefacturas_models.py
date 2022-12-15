# -*- encoding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID


class PtMuticertFelgtGuatefacturasXmlSent(models.Model):
    _name = "pt_multicert_felgt.guatefacturas_xml_sent"
    _description = "Registra los envios "

    name = fields.Char(string="Nombre",  required=True)
    data_content = fields.Char(string="content")
    api_sent = fields.Char(string="api sent")
