# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
class NoteStage(models.Model):
    """Compatibility model for the Notes application removed after v16.

    Keeping the original technical model and table lets upgraded databases retain
    their note stages without a destructive rename.
    """

    _name = 'note.stage'
    _description = 'Note Stage (legacy compatibility)'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)


class NoteTag(models.Model):
    _name = 'note.tag'
    _description = 'Note Tag (legacy compatibility)'

    name = fields.Char(required=True, translate=True)
    color = fields.Integer()


class Note(models.Model):
    _name = 'note.note'
    _description = 'Note (legacy compatibility)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id desc'

    name = fields.Char(required=True, default=lambda self: _('New note'), tracking=True)
    memo = fields.Html()
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, tracking=True)
    stage_id = fields.Many2one('note.stage', ondelete='set null', tracking=True)
    tag_ids = fields.Many2many('note.tag', string='Tags')
    open = fields.Boolean(default=True, tracking=True)
    date_done = fields.Date()
    sequence = fields.Integer(default=10)
    color = fields.Integer()

    def action_close(self):
        self.write({'open': False, 'date_done': fields.Date.context_today(self)})

    def action_open(self):
        self.write({'open': True, 'date_done': False})

    @api.onchange('task_id')
    def onchange_task(self):
        for rec in self:
            rec.project_id = rec.task_id.project_id.id
    
    project_id = fields.Many2one(
        'project.project',
        string='Construction Project',
    )
    task_id = fields.Many2one(
        'project.task',
        string='Task / Job Order',
    )
    is_task = fields.Boolean(
        string='Is Job Order?',
    )
    is_project = fields.Boolean(
        string='Is Project?',
    )
