# -*- coding: utf-8 -*-


from odoo import api, models, fields, _
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MultiApprovalLine(models.Model):
    _name = 'multi.approval.line'
    _description = 'Multi Aproval Line'
    _order = 'sequence'

    name = fields.Char(string='Title', required=True)
    user_ids = fields.Many2many(string='Users', comodel_name="res.users",
                                required=True)
    sequence = fields.Integer(string='Sequence')
    require_opt = fields.Selection(
        [('Required', 'Required'),
         ('Optional', 'Optional'),
         ], string="Type of Approval", default='Required')
    approval_id = fields.Many2one(
        string="Approval", comodel_name="multi.approval")
    state = fields.Selection(
        [('Draft', 'Draft'),
         ('Waiting for Approval', 'Waiting for Approval'),
         ('Approved', 'Approved'),
         ('Refused', 'Refused'),
         ('Cancel', 'Cancel'),
         ], default="Draft")
    refused_reason = fields.Text('Refused Reason')
    deadline = fields.Date(string='Deadline')
    require_all_approvers = fields.Boolean(
        string='Requiere Todos',
        default=False,
        help='Indica si todos los usuarios deben aprobar esta línea.'
    )
    # Usuarios que ya han aprobado
    approved_user_ids = fields.Many2many(
        'res.users',
        'multi_approval_line_approved_users_rel',
        'line_id',
        'user_id',
        string='Usuarios que Aprobaron',
        help='Lista de usuarios que ya han dado su aprobación para esta línea.'
    )
    # Usuarios pendientes de aprobar
    pending_user_ids = fields.Many2many(
        'res.users',
        string='Usuarios Pendientes',
        compute='_compute_pending_users',
        store=False,
        help='Lista de usuarios que aún no han aprobado esta línea.'
    )
    # Progreso de aprobación
    approval_progress = fields.Char(
        string='Progreso',
        compute='_compute_approval_progress',
        store=False,
        help='Muestra el progreso de aprobación (ej: 1/3 aprobados)'
    )
    # Indica si el usuario actual puede aprobar
    can_current_user_approve = fields.Boolean(
        string='Puede Aprobar',
        compute='_compute_can_current_user_approve',
        store=False
    )
    # Indica si el usuario actual ya aprobó
    current_user_approved = fields.Boolean(
        string='Ya Aprobó',
        compute='_compute_current_user_approved',
        store=False
    )

    # 13.0.1.1
    def set_approved(self):
        self.ensure_one()
        # Si requiere todos los aprobadores, verificar
        if self.require_all_approvers and len(self.user_ids) >= 1:
            if not self._check_all_approved():
                raise UserError(_(
                    f'Línea "{self.name}" aún pendiente. '
                    f'Faltan {len(self.pending_user_ids)} aprobadores.'
                ))
        self.state = 'Approved'

    def set_refused(self, reason=''):
        self.ensure_one()
        self.write({
            'state': 'Refused',
            'refused_reason': reason
        })

    @api.depends('user_ids', 'approved_user_ids')
    def _compute_pending_users(self):
        """
        Calcula los usuarios que aún no han aprobado.
        """
        for line in self:
            line.pending_user_ids = line.user_ids - line.approved_user_ids

    @api.depends('user_ids', 'approved_user_ids', 'require_all_approvers')
    def _compute_approval_progress(self):
        """
        Calcula el progreso de aprobación.
        """
        for line in self:
            if line.require_all_approvers and len(line.user_ids) > 1:
                approved = len(line.approved_user_ids)
                total = len(line.user_ids)
                line.approval_progress = f'{approved}/{total} aprobados'
            else:
                line.approval_progress = ''

    @api.depends('user_ids', 'approved_user_ids')
    def _compute_can_current_user_approve(self):
        """
        Verifica si el usuario actual puede aprobar esta línea.
        """
        current_user = self.env.user
        for line in self:
            # El usuario debe estar en la lista de aprobadores
            # y no haber aprobado ya
            line.can_current_user_approve = (
                    current_user in line.user_ids and
                    current_user not in line.approved_user_ids
            )

    @api.depends('approved_user_ids')
    def _compute_current_user_approved(self):
        """
        Verifica si el usuario actual ya aprobó.
        """
        current_user = self.env.user
        for line in self:
            line.current_user_approved = current_user in line.approved_user_ids

    def register_user_approval(self, user=None):
        """
        Registra la aprobación de un usuario específico.
        Args:
            user: Usuario que aprueba (por defecto el usuario actual)

        Returns:
            bool: True si todos han aprobado, False si aún faltan
        """
        self.ensure_one()
        if not user:
            user = self.env.user

        # Verificar que el usuario esté en la lista de aprobadores
        if user not in self.user_ids:
            raise UserError(_(
                '{} no está autorizado para aprobar esta línea.'
            ).format(user.name))

        # Verificar que no haya aprobado ya
        if user in self.approved_user_ids:
            _logger.info(
                f'Usuario {user.name} ya había aprobado la línea "{self.name}"'
            )
            return self._check_all_approved()

        # Registrar la aprobación
        self.write({
            'approved_user_ids': [(4, user.id)]
        })

        _logger.info(
            f'Usuario {user.name} aprobó la línea "{self.name}". '
            f'Progreso: {len(self.approved_user_ids)}/{len(self.user_ids)}'
        )

        return self._check_all_approved()

    def _check_all_approved(self):
        """
        Verifica si todos los usuarios requeridos han aprobado.
        Returns:
            bool: True si la línea está completamente aprobada
        """
        self.ensure_one()

        # Si no requiere todos, con uno es suficiente
        if not self.require_all_approvers:
            return len(self.approved_user_ids) >= 1

        return len(self.approved_user_ids) >= len(self.user_ids)
