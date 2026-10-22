# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Snapshot and copy legacy data before obsolete v16 models are cleaned."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['rail.payroll.legacy.migration'].run_nomina_cfdi()
