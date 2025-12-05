# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ProjectUserSubtask(models.TransientModel):
    _name = 'project.user.subtask'
    _description = 'Project User Subtask'

    subtask_user_ids = fields.One2many(
        'user.subtask', 
        'subtask_id',
        string="Project Subtask User",
        required=True,
    )
    
    def create_subtask(self):
        task_id = self._context.get('active_id', False)
        task = self.env['project.task'].browse(task_id)
        subtask_ids = []
        for subtask in self.subtask_user_ids:
            vals = {
                'planned_hours' : subtask.planned_hours,
                'description'   : subtask.description,
                'user_ids'       : subtask.user_id.ids,
                'name'          : subtask.name,
                'parent_task_id' : task.id,
                'parent_id'      : task.id,
                'project_id'     : task.project_id.id,
                'company_id'     : task.company_id.id,
            }
            copy_task_vals = self.env['project.task'].create(vals)

            subtask_ids.append(copy_task_vals.id)
        if subtask_ids:
            result = self.env["ir.actions.actions"]._for_xml_id("project.action_view_task")
            result['domain'] = "[('id','in',[" + ','.join(map(str, subtask_ids)) + "])]"
            return result
        return True
    
class UserSubtask(models.TransientModel):
    _name = 'user.subtask'
    _description = 'User Subtask'
    
    user_id = fields.Many2one(
        'res.users',
        string="User",
        required=True,
    )
    name = fields.Char(
        string='Task Name',
        required=True,
    )
    description = fields.Text(
        string='Task Description',
        required=True,
    )
    planned_hours = fields.Float(
        'Planned Hours',
        required=True,
    )
    subtask_id = fields.Many2one(
        'project.user.subtask',
        string='Project User Subtask'
    )
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
