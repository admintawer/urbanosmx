# -*- coding: utf-8 -*-


def post_init_hook(env):
    env['rail.payroll.legacy.migration'].run_nomina_cfdi_extras()
