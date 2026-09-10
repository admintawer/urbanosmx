# -*- coding: utf-8 -*-


from odoo import api, models, fields, _, tools
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
import logging

_logger = logging.getLogger(__name__)


class MultiApprovalTypeLine(models.Model):
    _name = 'multi.approval.type.line'
    _description = 'Multi Aproval Type Lines'
    _order = 'sequence'

    name = fields.Char(string='Title', required=True)
    user_ids = fields.Many2many(string='User', comodel_name="res.users",
                              required=True)
    sequence = fields.Integer(string='Sequence')
    require_opt = fields.Selection(
        [('Required', 'Required'),
         ('Optional', 'Optional'),
         ], string="Type of Approval", default='Required')
    type_id = fields.Many2one(
        string="Type", comodel_name="multi.approval.type")
    
    mail_notification = fields.Boolean("Notificacion por email")
    activity_notification = fields.Boolean("Notificacion actividad")

    # ============================================
    # CONFIGURACIÓN DE APROBADOR DINÁMICO
    # ============================================
    user_selection_type = fields.Selection([
        ('fixed', 'Usuario(s) Fijo(s)'),
        ('field_path', 'Ruta de Campo'),
        ('python', 'Código Python'),
    ], string='Tipo de Selección',
        default='fixed',
        help='Cómo se determina el/los usuario(s) aprobador(es):\n'
             '• Usuario(s) Fijo(s): Siempre los mismos usuarios\n'
             '• Ruta de Campo: Obtiene el usuario desde un campo del documento\n'
             '• Código Python: Lógica personalizada')

    user_field_path = fields.Char(
        string='Ruta de Campo al Usuario',
        help='Ruta al campo que contiene el usuario aprobador.\n\n'
             'Ejemplos:\n'
             '• user_id → Usuario del documento\n'
             '• employee_id.parent_id.user_id → Jefe del empleado\n'
             '• project_id.user_id → Responsable del proyecto\n'
             '• department_id.manager_id.user_id → Gerente del departamento'
    )

    user_python_code = fields.Text(
        string='Código Python',
        help='Código Python que retorna un res.users, su ID, o una lista de IDs.\n\n'
             'Variables disponibles:\n'
             '• record: Documento origen (ej: orden de compra)\n'
             '• env: Entorno de Odoo\n'
             '• user: Usuario actual\n\n'
             'Ejemplo:\n'
             'if record.employee_id:\n'
             '    result = record.employee_id.parent_id.user_id\n'
             'else:\n'
             '    result = env.ref("base.user_admin")'
    )

    fallback_user_id = fields.Many2one(
        'res.users',
        string='Usuario de Respaldo',
        help='Usuario a usar si no se puede determinar el aprobador dinámicamente'
    )

    user_selection_description = fields.Char(
        string='Descripción de Selección',
        compute='_compute_user_selection_description',
        store=False
    )

    require_all_approvers = fields.Boolean(
        string='Requiere Todos',
        default=False,
        help='Si está marcado y hay múltiples aprobadores, todos deben '
             'aprobar para que esta línea sea considerada aprobada.\n\n'
             'Si no está marcado, con que un aprobador apruebe es suficiente.'
    )

    @api.depends('user_selection_type', 'user_ids', 'user_field_path',
                 'fallback_user_id')
    def _compute_user_selection_description(self):
        """
        Genera descripción legible de cómo se selecciona el usuario
        """
        for line in self:
            if line.user_selection_type == 'fixed':
                if line.user_ids:
                    names = ', '.join(line.user_ids.mapped('name'))
                    line.user_selection_description = f'Fijo: {names}'
                else:
                    line.user_selection_description = 'Fijo: (No configurado)'
            elif line.user_selection_type == 'field_path':
                desc = f'Campo: {line.user_field_path or "(No configurado)"}'
                if line.fallback_user_id:
                    desc += f' | Respaldo: {line.fallback_user_id.name}'
                line.user_selection_description = desc
            elif line.user_selection_type == 'python':
                desc = 'Código Python'
                if line.fallback_user_id:
                    desc += f' | Respaldo: {line.fallback_user_id.name}'
                line.user_selection_description = desc
            else:
                line.user_selection_description = ''

    @api.onchange('user_selection_type')
    def _onchange_user_selection_type(self):
        """
        Limpia campos no relevantes al cambiar el tipo de selección
        """
        if self.user_selection_type == 'fixed':
            self.user_field_path = False
            self.user_python_code = False
            self.fallback_user_id = False
        elif self.user_selection_type == 'field_path':
            self.user_python_code = False
            self.user_ids = False
        elif self.user_selection_type == 'python':
            self.user_field_path = False
            self.user_ids = False

    def get_user(self, record=None):
        """
        Determina el/los usuario(s) aprobador(es) según la configuración.
        Args:
            record: Registro del documento origen (opcional, requerido para tipos dinámicos)
        Returns:
            list[int]: Lista de IDs de usuarios aprobadores
        """
        self.ensure_one()

        # Tipo: Usuario(s) Fijo(s)
        if self.user_selection_type == 'fixed':
            return self.user_ids.ids

        # Para tipos dinámicos, necesitamos el documento origen
        if not record:
            _logger.warning(
                f'Línea "{self.name}": Se requiere documento origen para '
                f'tipo "{self.user_selection_type}". Usando usuario de respaldo.'
            )
            return self._get_fallback_user_ids()

        # Obtener usuario(s) según tipo
        try:
            if self.user_selection_type == 'field_path':
                user_ids = self._get_user_from_field_path(record)
            elif self.user_selection_type == 'python':
                user_ids = self._get_user_from_python(record)
            else:
                user_ids = []

            # Si no se obtuvo usuario, usar respaldo
            if not user_ids:
                _logger.warning(
                    f'Línea "{self.name}": No se pudo determinar usuario. '
                    f'Usando respaldo.'
                )
                return self._get_fallback_user_ids()

            # Asegurar que sea lista
            if isinstance(user_ids, int):
                return [user_ids]
            return list(user_ids)

        except Exception as e:
            _logger.error(
                f'Línea "{self.name}": Error al obtener usuario dinámico: {e}. '
                f'Usando respaldo.'
            )
            return self._get_fallback_user_ids()

    # ============================================
    # RUTA DE CAMPO
    # ============================================
    def _get_user_from_field_path(self, record):
        """
        Obtiene usuario(s) navegando por una ruta de campos.

        Ejemplos de rutas:
        - 'user_id' → record.user_id
        - 'employee_id.parent_id.user_id' → record.employee_id.parent_id.user_id
        - 'partner_id.user_id' → record.partner_id.user_id
        - 'department_id.member_ids.user_id' → Múltiples usuarios
        Returns:
            list[int]: Lista de IDs de usuarios
        """
        if not self.user_field_path:
            _logger.warning(f'Línea "{self.name}": user_field_path no configurado')
            return []

        # Navegar por la ruta
        path_parts = self.user_field_path.split('.')
        current_value = record

        for i, field_name in enumerate(path_parts):
            if not current_value:
                _logger.warning(
                    f'Línea "{self.name}": Valor vacío en paso {i} de la ruta '
                    f'"{self.user_field_path}" (campo: {field_name})'
                )
                return []

            # Manejar recordsets múltiples
            if hasattr(current_value, '__iter__') and hasattr(current_value, '_name'):
                # Es un recordset de Odoo
                try:
                    current_value = current_value.mapped(field_name)
                except AttributeError:
                    _logger.error(
                        f'Línea "{self.name}": Campo "{field_name}" no existe. '
                        f'Ruta: "{self.user_field_path}"'
                    )
                    return []
            else:
                # Obtener siguiente valor
                try:
                    current_value = getattr(current_value, field_name, None)
                except AttributeError:
                    _logger.error(
                        f'Línea "{self.name}": Campo "{field_name}" no existe en '
                        f'{current_value._name}. Ruta: "{self.user_field_path}"'
                    )
                    return []

        # Validar que el resultado final sea usuario(s)
        if not current_value:
            _logger.info(
                f'Línea "{self.name}": La ruta "{self.user_field_path}" '
                f'retornó valor vacío'
            )
            return []

        # Si es un recordset de usuarios
        if hasattr(current_value, '_name') and current_value._name == 'res.users':
            if len(current_value) == 0:
                return []
            return current_value.ids

        # Si es un ID directo
        if isinstance(current_value, int):
            return [current_value]

        # Si es una lista de IDs
        if isinstance(current_value, (list, tuple)):
            return [x for x in current_value if isinstance(x, int)]

        _logger.error(
            f'Línea "{self.name}": La ruta "{self.user_field_path}" no retorna '
            f'usuario(s) válido(s). Tipo: {type(current_value)}'
        )
        return []

    # ============================================
    # CÓDIGO PYTHON
    # ============================================
    def _get_user_from_python(self, record):
        """
        Ejecuta código Python para determinar el/los usuario(s).
        El código debe definir 'result' con:
        - Un recordset de res.users
        - Un ID de usuario (int)
        - Una lista de IDs

        Returns:
            list[int]: Lista de IDs de usuarios
        """
        if not self.user_python_code:
            _logger.warning(f'Línea "{self.name}": user_python_code no configurado')
            return []

        try:
            # Contexto de evaluación
            eval_context = {
                'record': record,
                'env': self.env,
                'user': self.env.user,
                'time': tools.safe_eval.time,
                'datetime': tools.safe_eval.datetime,
            }

            # Ejecutar código
            safe_eval(
                self.user_python_code,
                eval_context,
                mode='exec',
                nocopy=True
            )

            # Obtener resultado
            result = eval_context.get('result', None)

            if not result:
                _logger.warning(
                    f'Línea "{self.name}": El código Python no definió "result"'
                )
                return []

            # Convertir resultado a lista de IDs
            if hasattr(result, '_name') and result._name == 'res.users':
                return result.ids
            elif isinstance(result, int):
                return [result]
            elif isinstance(result, (list, tuple)):
                return [x.id if hasattr(x, 'id') else x for x in result
                        if isinstance(x, int) or hasattr(x, 'id')]
            else:
                _logger.error(
                    f'Línea "{self.name}": El código Python retornó tipo inválido: '
                    f'{type(result)}'
                )
                return []
        except Exception as e:
            _logger.error(
                f'Línea "{self.name}": Error ejecutando código Python: {e}\n'
                f'Código: {self.user_python_code}'
            )
            return []

    def _get_fallback_user_ids(self):
        """
        Retorna los IDs de usuario de respaldo.
        Returns:
            list[int]: Lista de IDs de usuarios de respaldo
        """
        if self.fallback_user_id:
            return [self.fallback_user_id.id]
        else:
            _logger.error(
                f'Línea "{self.name}": No hay usuario de respaldo configurado'
            )
            return []

    @api.constrains('user_selection_type', 'user_field_path', 'user_python_code', 'user_ids')
    def _check_user_selection_config(self):
        """
        Valida que la configuración sea coherente
        """
        for line in self:
            if line.user_selection_type == 'fixed' and not line.user_ids:
                raise ValidationError(_(
                    'La línea "{}" tiene tipo "Usuario(s) Fijo(s)" pero no se han '
                    'seleccionado usuarios.'
                ).format(line.name))

            if line.user_selection_type == 'field_path' and not line.user_field_path:
                raise ValidationError(_(
                    'La línea "{}" tiene tipo "Ruta de Campo" pero no se ha '
                    'especificado la ruta.'
                ).format(line.name))

            if line.user_selection_type == 'python' and not line.user_python_code:
                raise ValidationError(_(
                    'La línea "{}" tiene tipo "Código Python" pero no se ha '
                    'definido el código.'
                ).format(line.name))
