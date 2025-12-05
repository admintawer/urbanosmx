# -*- coding: utf-8 -*-


from odoo import api, fields, models


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    def write(self, vals):
        self.env['multi.approval.type'].check_rule(self, vals)
        res = super(BaseModel, self).write(vals)
        return res
