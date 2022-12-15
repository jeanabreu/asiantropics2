
from odoo import api, fields, models, SUPERUSER_ID
# Import logger
import logging
import time
import zeep
import datetime
import pytz
# Get the logger
_logger = logging.getLogger(__name__)


class BanguatRate(models.Model):
    _name = 'banguat.rate'
    _description = "Retreives Banguat daily Dollar rate and adds it to the currency rate"

    name = fields.Char()
    @api.model
    def get_daily_rate(self):
        currency_usd_id = self.env.ref("base.USD").id

        today_date = datetime.datetime.now(pytz.timezone('America/Guatemala')).__format__('%Y-%m-%d')

        odoo_companies = self.env['res.company'].search([])
        company_ids = []
        all_completed = True
        for company in odoo_companies:
        
            rateCount = self.env['res.currency.rate'].search_count([
                ('name', '=', today_date), 
                ('currency_id', '=', currency_usd_id),
                ('company_id', '=', company.id),
            ])
            if rateCount == 0:
                company_ids.append(company.id)

        if len(company_ids) == 0:
            _logger.info('line: The rate for today is  already registered')

        if len(company_ids) > 0:
            second_wsdl = 'http://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?WSDL'
            client = zeep.Client(wsdl=second_wsdl)
            service_response = client.service.TipoCambioDia()
            rate_date = service_response['CambioDolar']['VarDolar'][0]['fecha'] + ' 05:00:00'
            rate_value = service_response['CambioDolar']['VarDolar'][0]['referencia']

            # CONVERSION FOR ODOD CALCULATION
            rate_value = 1 / rate_value

            rate_iso_date = datetime.datetime.strptime(rate_date, '%d/%m/%Y %H:%M:%S').__format__('%Y-%m-%d %H:%M:%S')

            strRate = repr(rate_value)
            strGTQ = str(currency_usd_id)
            _logger.info('line: WSLD Response ' + rate_date + '-----' + strRate + ' GTQid: ' + strGTQ)
            
            odoo_companies = self.env['res.company'].search([])
            
            for company_id in company_ids:    

                self.env['res.currency.rate'].create({
                    'name': rate_iso_date,
                    'rate': rate_value,
                    'currency_id': currency_usd_id,
                    'company_id': company_id
                })
