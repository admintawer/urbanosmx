# -*- coding: utf-8 -*-
# from odoo import http


# class RailPatches(http.Controller):
#     @http.route('/rail_patches/rail_patches', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/rail_patches/rail_patches/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('rail_patches.listing', {
#             'root': '/rail_patches/rail_patches',
#             'objects': http.request.env['rail_patches.rail_patches'].search([]),
#         })

#     @http.route('/rail_patches/rail_patches/objects/<model("rail_patches.rail_patches"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('rail_patches.object', {
#             'object': obj
#         })
