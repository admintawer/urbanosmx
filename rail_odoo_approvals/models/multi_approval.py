# -*- coding: utf-8 -*-


from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MultiApproval(models.Model):
    _name = 'multi.approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Multi Aproval'

    code = fields.Char(default=_('New'))
    name = fields.Char(string='Title', required=True)
    user_id = fields.Many2one(
        string='Request by', comodel_name="res.users",
        required=True, default=lambda self: self.env.uid)
    priority = fields.Selection(
        [('0', 'Normal'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Very High')], string='Priority', default='0')
    request_date = fields.Datetime(
        string='Request Date', default=fields.Datetime.now)
    complete_date = fields.Datetime()
    type_id = fields.Many2one(
        string="Type", comodel_name="multi.approval.type", required=True)
    image = fields.Binary(related="type_id.image")
    description = fields.Html('Description')
    state = fields.Selection(
        [('Draft', 'Draft'),
         ('Submitted', 'Submitted'),
         ('Approved', 'Approved'),
         ('Refused', 'Refused'),
         ('Cancel', 'Cancel')], default='Draft', tracking=True)

    document_opt = fields.Selection(
        string="Document opt",
        readonly=True, related='type_id.document_opt')
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')

    contact_opt = fields.Selection(
        string="Contact opt",
        readonly=True, related='type_id.contact_opt')
    contact_id = fields.Many2one('res.partner', string='Contact')

    date_opt = fields.Selection(
        string="Date opt",
        readonly=True, related='type_id.date_opt')
    date = fields.Date('Date')

    period_opt = fields.Selection(
        string="Period opt",
        readonly=True, related='type_id.period_opt')
    date_start = fields.Date('Start Date')
    date_end = fields.Date('End Date')

    item_opt = fields.Selection(
        string="Item opt",
        related='type_id.item_opt')
    item_id = fields.Many2one('product.product', string='Item')

    multi_items_opt = fields.Selection(
        string="Multi Items opt",
        readonly=True, related='type_id.multi_items_opt')
    item_ids = fields.Many2many('product.product', string='Items')


    quantity_opt = fields.Selection(
        string="Quantity opt",
        readonly=True, related='type_id.quantity_opt')
    quantity = fields.Float('Quantity')

    amount_opt = fields.Selection(
        string="Amount opt",
        readonly=True, related='type_id.amount_opt')
    amount = fields.Float('Amount')

    payment_opt = fields.Selection(
        string="Payment opt",
        readonly=True, related='type_id.payment_opt')
    payment = fields.Float('Payment')

    reference_opt = fields.Selection(
        string="Reference opt",
        readonly=True, related='type_id.reference_opt')
    reference = fields.Char('Reference')

    location_opt = fields.Selection(
        string="Location opt",
        readonly=True, related='type_id.location_opt')
    location = fields.Char('Location')
    line_ids = fields.One2many('multi.approval.line', 'approval_id',
                               string="Lines")
    line_id = fields.Many2one('multi.approval.line', string="Line", copy=False)
    deadline = fields.Date(string='Deadline', related='line_id.deadline')
    pic_ids = fields.Many2many(
        'res.users', string='Approvers', related='line_id.user_ids')
    is_pic = fields.Boolean(compute='_check_pic')
    follower = fields.Text('Following Users', default='[]', copy=False)

    # copy the idea of hr_expense
    attachment_number = fields.Integer(
        'Number of Attachments', compute='_compute_attachment_number')
    current_line_progress = fields.Char(
        string='Progreso de Aprobación',
        compute='_compute_current_line_progress',
        store=False
    )

    @api.depends_context("uid")
    def _check_pic(self):
        for r in self:
            r.is_pic = self.env.uid in r.pic_ids.ids

    def _compute_attachment_number(self):
        attachment_data = self.env['ir.attachment'].read_group(
            [('res_model', '=', 'multi.approval'), ('res_id', 'in', self.ids)],
            ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count'])
                          for data in attachment_data)
        for r in self:
            r.attachment_number = attachment.get(r.id, 0)

    def action_cancel(self):
        recs = self.filtered(lambda x: x.state == 'Draft')
        recs.write({'state': 'Cancel'})

    def action_submit(self):
        recs = self.filtered(lambda x: x.state == 'Draft')
        for r in recs:
            # Check if document is required
            if r.document_opt == 'Required' and r.attachment_number < 1:
                raise UserError(_('Document is required !'))
            if not r.type_id.line_ids:
                raise UserError(_(
                    'There is no approver of the type "{}" !'.format(
                        r.type_id.name)))
            r.state = 'Submitted'
        recs._create_approval_lines()
        recs.send_request_mail()
        recs.send_activity_notification()

    @api.model
    def get_follow_key(self, user_id=None):
        if not user_id:
            user_id = self.env.uid
        k = '[res.users:{}]'.format(user_id)
        return k

    def update_follower(self, user_id):
        self.ensure_one()
        k = self.get_follow_key(user_id)
        follower = self.follower
        if k not in follower:
            self.follower = follower + k

    # 13.0.1.1
    def set_approved(self):
        self.ensure_one()
        self.state = 'Approved'
        self.complete_date = fields.Datetime.now()
        self.send_approved_mail()

    def set_refused(self, reason=''):
        self.ensure_one()
        self.state = 'Refused'
        self.complete_date = fields.Datetime.now()
        self.send_refused_mail()

    def action_approve(self):
        ret_act = None
        recs = self.filtered(lambda x: x.state == 'Submitted')
        for rec in recs:
            if not rec.is_pic:
                msg = _('{} do not have the authority to approve this request !'.format(rec.env.user.name))
                self.sudo().message_post(body=msg)
                return False
            line = rec.line_id
            if not line or line.state != 'Waiting for Approval':
                # Something goes wrong!
                self.message_post(body=_('Something goes wrong!'))
                return False

            # Update follower
            rec.update_follower(self.env.uid)

            # Registrar la aprobación del usuario actual
            line.register_user_approval(self.env.user)

            # Verificar si la línea está completamente aprobada
            if line.require_all_approvers and len(line.user_ids) >= 1:
                if not line._check_all_approved():
                    # Aún faltan aprobadores - no pasar a la siguiente línea
                    msg = _(
                        '{} aprobó. Esperando aprobación de: {}'
                    ).format(
                        self.env.user.name,
                        ', '.join(line.pending_user_ids.mapped('name'))
                    )
                    rec.message_post(body=msg)

                    # Enviar notificaciones a los pendientes
                    rec._notify_pending_approvers(line)
                    return False

            # check if this line is required
            other_lines = rec.line_ids.filtered(
                lambda x: x.sequence >= line.sequence and x.state == 'Draft')
            if not other_lines:
                ret_act = rec.set_approved()
            else:
                next_line = other_lines.sorted('sequence')[0]
                next_line.write({
                    'state': 'Waiting for Approval',
                })
                rec.line_id = next_line
                rec.send_request_mail()
                recs.send_activity_notification()
            line.set_approved()
            msg = _('I approved')
            rec.finalize_activity_or_message('approved', msg)
        if ret_act:
            return ret_act
        return True

    def action_refuse(self, reason=''):
        ret_act = None
        recs = self.filtered(lambda x: x.state == 'Submitted')
        for rec in recs:
            if not rec.is_pic:
                msg = _('{} do not have the authority to approve this request !'.format(rec.env.user.name))
                self.sudo().message_post(body=msg)
                return False
            line = rec.line_id
            if not line or line.state != 'Waiting for Approval':
                # Something goes wrong!
                self.message_post(body=_('Something goes wrong!'))
                return False

            # Update follower
            rec.update_follower(self.env.uid)

            # check if this line is required
            if line.require_opt == 'Required':
                ret_act = rec.set_refused(reason)
                draft_lines = rec.line_ids.filtered(lambda x: x.state == 'Draft')
                if draft_lines:
                    draft_lines.state = 'Cancel'
            else:  # optional
                other_lines = rec.line_ids.filtered(
                    lambda x: x.sequence >= line.sequence and x.state == 'Draft')
                if not other_lines:
                    ret_act = rec.set_refused(reason)
                else:
                    next_line = other_lines.sorted('sequence')[0]
                    next_line.state = 'Waiting for Approval'
                    rec.line_id = next_line
            line.set_refused(reason)
            msg = _('I refused due to this reason: {}'.format(reason))
            rec.finalize_activity_or_message('refused', msg)
        if ret_act:
            return ret_act

    def finalize_activity_or_message(self, action, msg):
        requests = self.filtered(
            lambda r: r.type_id.activity_notification
        )
        notify_type = self.env.ref("mail.mail_activity_data_todo", False)
        if requests and notify_type: 
            activities = requests.mapped("activity_ids").filtered(
                lambda a: a.activity_type_id == notify_type and a.user_id == self.env.user)
            activities._action_done(msg)

        requests2 = self - requests
        if requests2:
            requests2.message_post(body=msg)

    def _create_approval_lines(self):
        ApprovalLine = self.env['multi.approval.line']
        for r in self:
            # Obtener el registro origen si existe
            origin_record = None
            if hasattr(r, 'origin_ref') and r.origin_ref:
                origin_record = r.origin_ref
            lines = r.type_id.line_ids.sorted('sequence')
            last_seq = 0

            for l in lines:
                line_seq = l.sequence
                if not line_seq or line_seq <= last_seq:
                    line_seq = last_seq + 1
                last_seq = line_seq

                # Obtener usuarios - pasando el registro origen para tipos dinámicos
                user_ids = l.get_user(record=origin_record)

                # Validar que se obtuvieron usuarios
                if not user_ids:
                    _logger.warning(
                        f'Aprobación "{r.name}": La línea "{l.name}" no tiene '
                        f'usuarios configurados. Se omitirá esta línea.'
                    )
                    continue

                vals = {
                    'name': l.name,
                    'user_ids': [(6, 0, user_ids)],
                    'sequence': line_seq,
                    'require_opt': l.require_opt,
                    'require_all_approvers': l.require_all_approvers,
                    'approval_id': r.id,
                    'approved_user_ids': [(5, 0, 0)]
                }
                if l == lines[0]:
                    vals.update({'state': 'Waiting for Approval'})
                approval = ApprovalLine.create(vals)
                if l == lines[0]:
                    r.line_id = approval

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            seq_date = vals.get('request_date', fields.Datetime.now())
            vals['code'] = self.env['ir.sequence'].next_by_code(
                'multi.approval', sequence_date=seq_date) or _('New')
        result = super(MultiApproval, self).create(vals_list)
        return result

    # 12.0.1.3
    def send_request_mail(self):
        requests = self.filtered(lambda r: r.type_id.mail_notification and r.pic_ids and r.state == 'Submitted')
        for req in requests:
            approver_notifications = req.type_id.mail_notification
            mail_notification_line_ids = req.type_id.line_ids.filtered(lambda x: x.mail_notification)
            if not mail_notification_line_ids:
                continue
            approvers = mail_notification_line_ids.filtered(lambda x: x.user_ids.ids in req.pic_ids.ids).mapped(
                'user_ids')  # usuarios fijos
            # dinamicos
            try:
                origin_record = getattr(req, 'origin_ref', None)
                for line in mail_notification_line_ids:
                    if not origin_record:
                        break
                    user_ids = line.get_user(record=origin_record)
                    if user_ids:
                        users = self.env['res.users'].browse(user_ids)
                        approvers |= users.filtered(lambda u: u.id in req.pic_ids.ids)
            except Exception as e:
                _logger.error(f'Error obteniendo aprobadores dinámicos para solicitud {req.id}: {e}')
            if not approvers:
                approver_notifications = False
            if approver_notifications:
                if req.type_id.mail_template_id:
                    req.type_id.mail_template_id.send_mail(req.id)
                else:
                    message = self.env['mail.message'].create({
                        'subject': _('Request the approval for: {request_name}').format(
                            request_name=req.display_name
                        ),
                        'model': req._name,
                        'res_id': req.id,
                        'body': self.description,
                    })

                    self.env['mail.mail'].sudo().create({
                        'mail_message_id': message.id,
                        'body_html': self.description,
                        'email_to': ','.join(req.pic_ids.mapped('email') or []),
                        'email_from': req.user_id.email,
                        'auto_delete': True,
                        'state': 'outgoing',

                    })

    def send_approved_mail(self):
        requests = self.filtered(
            lambda r: r.type_id.approve_mail_template_id and
                r.state == 'Approved'
        )
        for req in requests:
            req.type_id.approve_mail_template_id.send_mail(req.id)

    def send_refused_mail(self):
        requests = self.filtered(
            lambda r: r.type_id.refuse_mail_template_id and
                r.state == 'Refused'
        )
        for req in requests:
            req.type_id.refuse_mail_template_id.send_mail(req.id)

    def send_activity_notification(self):
        requests = self.filtered(lambda r: r.type_id.activity_notification and r.pic_ids and r.state == 'Submitted')
        notify_type = self.env.ref("mail.mail_activity_data_todo", False)
        if not notify_type:
            return
        for req in requests:
            approver_notifications = req.type_id.activity_notification
            activity_notification_line_ids = req.type_id.line_ids.filtered(lambda x: x.activity_notification)
            if not activity_notification_line_ids:
                continue
            approvers = activity_notification_line_ids.filtered(lambda x: x.user_ids.ids in req.pic_ids.ids).mapped('user_ids')  # usuarios fijos
            # dinamicos
            try:
                origin_record = getattr(req, 'origin_ref', None)
                for line in activity_notification_line_ids:
                    if not origin_record:
                        break
                    user_ids = line.get_user(record=origin_record)
                    if user_ids:
                        users= self.env['res.users'].browse(user_ids)
                        approvers |= users.filtered(lambda u: u.id in req.pic_ids.ids)
            except Exception as e:
                _logger.error(f'Error obteniendo aprobadores dinámicos para solicitud {req.id}: {e}')
            if not approvers:
                approver_notifications = False
            if approver_notifications:
                summary = _("The request {code} need to be reviewed").format(
                    code=req.code
                )
                for pic in req.pic_ids:
                    self.env['mail.activity'].create({
                        'res_id': req.id,
                        'res_model_id': self.env['ir.model']._get(req._name).id,
                        'activity_type_id': notify_type.id,
                        'summary': summary,
                        'user_id': pic.id,
                    })

    @api.depends('line_id', 'line_id.approved_user_ids', 'line_id.user_ids')
    def _compute_current_line_progress(self):
        """
        Calcula el progreso de la línea actual.
        """
        for rec in self:
            if rec.line_id and rec.line_id.require_all_approvers:
                rec.current_line_progress = rec.line_id.approval_progress
            else:
                rec.current_line_progress = ''

    def _notify_pending_approvers(self, line):
        """
        Envía notificaciones a los aprobadores pendientes.
        Args:
            line: Línea de aprobación con aprobadores pendientes
        """
        if not line.pending_user_ids:
            return

        # Enviar email si está configurado
        if self.type_id.mail_notification:
            mail_notification_line_ids = self.type_id.line_ids.filtered(lambda x: x.mail_notification)
            if not mail_notification_line_ids:
                return
            approvers = mail_notification_line_ids.filtered(lambda x: x.user_ids.ids in self.pic_ids.ids).mapped(
                'user_ids')  # usuarios fijos
            # dinamicos
            try:
                origin_record = getattr(self, 'origin_ref', None)
                for approval_type_line in mail_notification_line_ids:
                    if not origin_record:
                        break
                    user_ids = approval_type_line.get_user(record=origin_record)
                    if user_ids:
                        users = self.env['res.users'].browse(user_ids)
                        approvers |= users.filtered(lambda u: u.id in self.pic_ids.ids)
            except Exception as e:
                _logger.error(f'Error obteniendo aprobadores dinámicos para solicitud {self.id}: {e}')
            for user in line.pending_user_ids:
                if approvers and user.id in approvers.ids:
                    self._send_pending_approval_mail(user, line)

        # Enviar actividad si está configurado
        if self.type_id.activity_notification:
            for user in line.pending_user_ids:
                self._send_pending_approval_activity(user, line)

    def _send_pending_approval_mail(self, user, line):
        """
        Envía email recordatorio a un aprobador pendiente.
        """
        try:
            approved_by = ', '.join(line.approved_user_ids.mapped('name'))
            pending = len(line.pending_user_ids)

            body = _(
                '<p>La solicitud <strong>{}</strong> está esperando tu aprobación.</p>'
                '<p>Ya aprobaron: {}</p>'
                '<p>Pendientes: {} usuario(s)</p>'
            ).format(self.display_name, approved_by or 'Nadie aún', pending)

            message = self.env['mail.message'].create({
                'subject': _('Aprobación pendiente: {}').format(self.display_name),
                'model': self._name,
                'res_id': self.id,
                'body': body,
            })

            self.env['mail.mail'].sudo().create({
                'mail_message_id': message.id,
                'body_html': body,
                'email_to': user.email,
                'email_from': self.env.user.email,
                'auto_delete': True,
                'state': 'outgoing',
            })
        except Exception as e:
            _logger.error(f'Error enviando email a aprobador pendiente: {e}')

    def _send_pending_approval_activity(self, user, line):
        """
        Crea actividad para un aprobador pendiente.
        """
        try:
            notify_type = self.env.ref("mail.mail_activity_data_todo", False)
            if not notify_type:
                return

            approved_count = len(line.approved_user_ids)
            total = len(line.user_ids)

            summary = _(
                'Aprobación pendiente ({}/{} aprobados)'
            ).format(approved_count, total)

            # Verificar si ya existe una actividad para este usuario
            existing = self.env['mail.activity'].search([
                ('res_id', '=', self.id),
                ('res_model', '=', self._name),
                ('user_id', '=', user.id),
                ('activity_type_id', '=', notify_type.id),
            ], limit=1)

            if not existing:
                self.env['mail.activity'].create({
                    'res_id': self.id,
                    'res_model_id': self.env['ir.model']._get(self._name).id,
                    'activity_type_id': notify_type.id,
                    'summary': summary,
                    'user_id': user.id,
                })
        except Exception as e:
            _logger.error(f'Error creando actividad para aprobador pendiente: {e}')
