# -*- coding: utf-8 -*-
from odoo import http

# class Addons/settlementExpenses(http.Controller):
#     @http.route('/addons/settlement_expenses/addons/settlement_expenses/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/addons/settlement_expenses/addons/settlement_expenses/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('addons/settlement_expenses.listing', {
#             'root': '/addons/settlement_expenses/addons/settlement_expenses',
#             'objects': http.request.env['addons/settlement_expenses.addons/settlement_expenses'].search([]),
#         })

#     @http.route('/addons/settlement_expenses/addons/settlement_expenses/objects/<model("addons/settlement_expenses.addons/settlement_expenses"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('addons/settlement_expenses.object', {
#             'object': obj
#         })