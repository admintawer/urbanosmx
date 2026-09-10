# controllers/domain.py
from odoo.addons.web.controllers.domain import Domain as WebDomain
from odoo import http

class Domain(WebDomain):

    @http.route('/web/domain/validate', type='jsonrpc', auth="user")
    def validate(self, model, domain):
        # Trust client-evaluated domains (including datetime in-range).
        return super(Domain, self).validate(model, domain)