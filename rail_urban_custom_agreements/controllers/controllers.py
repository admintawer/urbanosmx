# -*- coding: utf-8 -*-
# from odoo import http


# class RailUrbanCustomAgreements(http.Controller):
#     @http.route('/rail_urban_custom_agreements/rail_urban_custom_agreements', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/rail_urban_custom_agreements/rail_urban_custom_agreements/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('rail_urban_custom_agreements.listing', {
#             'root': '/rail_urban_custom_agreements/rail_urban_custom_agreements',
#             'objects': http.request.env['rail_urban_custom_agreements.rail_urban_custom_agreements'].search([]),
#         })

#     @http.route('/rail_urban_custom_agreements/rail_urban_custom_agreements/objects/<model("rail_urban_custom_agreements.rail_urban_custom_agreements"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('rail_urban_custom_agreements.object', {
#             'object': obj
#         })
