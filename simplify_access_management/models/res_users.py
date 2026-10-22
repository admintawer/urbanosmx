from odoo import fields, models, api, SUPERUSER_ID,_
from odoo.exceptions import UserError, AccessDenied
from .query_prepare import search_data
import logging
_logger = logging.getLogger(__name__)

class res_users(models.Model):
    _inherit = 'res.users'

    access_management_ids = fields.Many2many('access.management', 'access_management_users_rel_ah', 'user_id', 'access_management_id', 'Access Pack')
    
    def write(self, vals):
        res = super(res_users, self).write(vals)
        for access in self.sudo().access_management_ids:
            if self.env.company in access.company_ids and access.readonly:
                if self.has_group('base.group_system') or self.has_group('base.group_erp_manager'):
                    raise UserError(_('Admin user can not be set as a read-only..!'))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super(res_users, self).create(vals_list)
        for record in self:
            for access in record.sudo().access_management_ids:    
                if self.env.company in access.company_ids and access.readonly:
                    if record.has_group('base.group_system') or record.has_group('base.group_erp_manager'):
                        raise UserError(_('Admin user can not be set as a read-only..!'))
        return res

    
    def _login(self, credential, user_agent_env):
        res = super()._login(credential, user_agent_env=user_agent_env)
        try:            
            with self.pool.cursor() as cr:  
                uid = res.get('uid') 
                self = api.Environment(cr, uid, {})[self._name]
            # access_management_obj = self.env['access.management']
                result = search_data(self, 'access.management',condition=('disable_login','=',True), operator='AND', limit=1)
                if result:
                    raise AccessDenied("Login is disabled for this user due to access management settings.")
        except AccessDenied:
            _logger.info("Login failed login:%s from ", credential.get('login'))
            raise
        return res
        
