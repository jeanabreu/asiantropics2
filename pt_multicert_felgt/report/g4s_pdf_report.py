
import json
import base64
import io
import requests
from requests.auth import AuthBase
import re
from odoo import models
import zeep


class PtMulticertFelgtFelPdfAbstract(models.AbstractModel):
    _name = 'report.fel_pdf.abstract' 
    _description = "Abstract Byte serverd PDF Report"
    
    def _get_objs_for_report(self, docids, data):
        """
        Returns objects for xlx report.  From WebUI these
        are either as docids taken from context.active_ids or
        in the case of wizard are in data.  Manual calls may rely
        on regular context, setting docids, or setting data.

        :param docids: list of integers, typically provided by
            qwebactionmanager for regular Models.
        :param data: dictionary of data, if present typically provided
            by qwebactionmanager for TransientModels.
        :param ids: list of integers, provided by overrides.
        :return: recordset of active model for ids.
        """
        if docids:
            ids = docids
        elif data and "context" in data:
            ids = data["context"].get("active_ids", [])
        else:
            ids = self.env.context.get("active_ids", [])
        return self.env[self.env.context.get("active_model")].browse(ids)
    

class PtMulticertFelgtG4sPdfAbstract(models.AbstractModel):
    _name = 'report.g4s_pdf.abstract' 
    _inherit = 'report.fel_pdf.abstract'
    
    def generate_g4s_pdf(self, docids):
        
        invoice_data = self.env['account.move'].search([
            ('id', 'in', docids)
        ], limit=1)
        
        
        if invoice_data and invoice_data.company_id:
            company_id = invoice_data.company_id
            uuid = invoice_data.uuid
            company_vat = company_id.vat
            requestor_id = company_id.requestor_id
            username = company_id.g4s_username
            active_env = company_id.g4s_environment
            env_url = company_id.g4s_dev_url
            if active_env == 'production':
                env_url = company_id.g4s_prod_url

            second_wsdl = env_url+'?wsdl'
            client = zeep.Client(wsdl=second_wsdl)
            
            request_data = {
                'Requestor': requestor_id,
                'Transaction': 'GET_DOCUMENT',
                'Country': 'GT',
                'Entity': company_vat,
                'User': requestor_id,
                'UserName': username,
                'Data1': uuid,
                'Data2': '',
                'Data3': 'PDF'
            }
            
            service_response = client.service.RequestTransaction(**request_data)
            
            
            if 'ResponseData' in service_response:
                if 'ResponseData3' in service_response['ResponseData']:
                    pdf_b64_data = service_response['ResponseData']['ResponseData3']
                    bytes = base64.b64decode(pdf_b64_data, validate=True)
            
                    if bytes[0:4] != b'%PDF':
                        raise ValueError('Missing the PDF file signature')

                    output = io.BytesIO()
                    
                    output.seek(0)
                    return bytes
                    