# -*- coding: utf-8 -*-

from . import models


def post_init_hook(env):
    """Map the legacy local-tax flag to Odoo 19's native CFDI setting."""
    taxes = env['account.tax'].with_context(active_test=False).search([('local_tax', '=', True)])
    taxes.write({'l10n_mx_tax_type': 'local'})
