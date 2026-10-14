# -*- coding: utf-8 -*-
import base64
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SamJsonExportWizard(models.TransientModel):
    _name = 'sam.json.export.wizard'
    _description = 'Exportar reglas Access Management JSON'

    filename = fields.Char(default='access_management_rules.json', readonly=True)
    file = fields.Binary(string='Archivo JSON', readonly=True)
    info = fields.Text(string='Resultado', readonly=True)


class SamJsonImportWizard(models.TransientModel):
    _name = 'sam.json.import.wizard'
    _description = 'Importar reglas Access Management JSON'

    json_file = fields.Binary(string='Archivo JSON', required=True)
    json_filename = fields.Char(string='Nombre del archivo')
    update_existing = fields.Boolean(string='Actualizar si existe regla con el mismo nombre', default=True)
    import_users = fields.Boolean(string='Mapear usuarios por login/email', default=True)
    import_companies = fields.Boolean(string='Mapear compañías por XMLID/nombre', default=True)
    dry_run = fields.Boolean(string='Solo validar, no crear/actualizar')
    result_text = fields.Text(string='Resultado', readonly=True)

    def _sam_json_check_manager(self):
        return self.env['access.management']._sam_json_check_manager()

    def action_import(self):
        self.ensure_one()
        self._sam_json_check_manager()
        payload = self._decode_payload()
        records = payload.get('records') or []
        if not isinstance(records, list):
            raise UserError(_('El JSON no contiene una lista válida en la llave "records".'))

        Importer = self.env['sam.json.import.service'].sudo()
        result = Importer.import_payload(
            payload,
            update_existing=self.update_existing,
            import_users=self.import_users,
            import_companies=self.import_companies,
            dry_run=self.dry_run,
        )
        self.result_text = result
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar reglas JSON'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _decode_payload(self):
        self.ensure_one()
        try:
            raw = base64.b64decode(self.json_file or b'')
            if raw.startswith(b'\xef\xbb\xbf'):
                raw = raw[3:]
            return json.loads(raw.decode('utf-8'))
        except Exception as exc:
            raise UserError(_('No se pudo leer el JSON: %s') % exc)


class SamJsonImportService(models.AbstractModel):
    _name = 'sam.json.import.service'
    _description = 'SAM JSON Import Service'

    # ------------------------------------------------------------------
    # Main import
    # ------------------------------------------------------------------
    @api.model
    def import_payload(self, payload, update_existing=True, import_users=True, import_companies=True, dry_run=False):
        records = payload.get('records') or []
        logs = []
        created = updated = skipped = 0

        for data in records:
            if not isinstance(data, dict):
                skipped += 1
                logs.append(_('OMITIDO: elemento inválido en records.'))
                continue
            name = data.get('name')
            if not name:
                skipped += 1
                logs.append(_('OMITIDO: regla sin nombre.'))
                continue

            existing = self.env['access.management'].sudo().search([('name', '=', name)], limit=1)
            if existing and not update_existing:
                skipped += 1
                logs.append(_('OMITIDO: ya existe regla "%s".') % name)
                continue

            vals, warnings = self._prepare_access_vals(data, import_users, import_companies)
            logs.extend(warnings)
            if dry_run:
                logs.append(_('VALIDADO: %s') % name)
                continue

            if existing:
                self._clear_existing_rule(existing)
                existing.write(vals)
                updated += 1
                logs.append(_('ACTUALIZADO: %s') % name)
            else:
                self.env['access.management'].sudo().create(vals)
                created += 1
                logs.append(_('CREADO: %s') % name)

        if dry_run:
            summary = _('Validación finalizada. Reglas válidas: %s | Omitidas: %s') % (len(records) - skipped, skipped)
        else:
            summary = _('Importación finalizada. Creadas: %s | Actualizadas: %s | Omitidas: %s') % (created, updated, skipped)
        return summary + '\n\n' + '\n'.join(logs)

    def _clear_existing_rule(self, record):
        # One2many commands in write would replace children, but unlink first keeps the logic predictable.
        for fname in [
            'hide_field_ids', 'remove_action_ids', 'access_domain_ah_ids',
            'hide_view_nodes_ids', 'hide_filters_groups_ids', 'hide_chatter_ids',
        ]:
            if fname in record._fields:
                record[fname].sudo().unlink()

    def _prepare_access_vals(self, data, import_users, import_companies):
        warnings = []
        Access = self.env['access.management']
        vals = {
            'name': data.get('name'),
            'active': bool(data.get('active', True)),
            'readonly': bool(data.get('readonly', False)),
        }

        optional_fields = [
            'hide_chatter', 'hide_send_mail', 'hide_log_notes', 'hide_schedule_activity',
            'hide_export', 'hide_import', 'hide_spreadsheet', 'hide_add_property',
            'disable_login', 'disable_debug_mode', 'is_apply_on_without_company',
        ]
        for fname in optional_fields:
            if fname in Access._fields and fname in data:
                vals[fname] = bool(data.get(fname))

        if import_users:
            user_ids, user_warnings = self._resolve_users(data.get('users') or [])
            warnings.extend(user_warnings)
            vals['user_ids'] = [(6, 0, user_ids)]

        if import_companies:
            company_ids, company_warnings = self._resolve_companies(data.get('companies') or [])
            warnings.extend(company_warnings)
            if not company_ids and 'company_ids' in Access._fields and Access._fields['company_ids'].required:
                company_ids = [self.env.company.id]
                warnings.append(_('INFO: sin compañías mapeadas para "%s"; se usó la compañía actual.') % data.get('name'))
            vals['company_ids'] = [(6, 0, company_ids)]

        menu_ids, menu_warnings = self._resolve_menus(data.get('hide_menus') or [])
        warnings.extend(menu_warnings)
        vals['hide_menu_ids'] = [(6, 0, menu_ids)]

        vals['hide_field_ids'] = [(0, 0, item) for item in self._prepare_hide_fields(data.get('hide_fields') or [], warnings)]
        vals['remove_action_ids'] = [(0, 0, item) for item in self._prepare_remove_actions(data.get('remove_actions') or [], warnings)]
        vals['access_domain_ah_ids'] = [(0, 0, item) for item in self._prepare_access_domains(data.get('access_domains') or [], warnings)]
        vals['hide_view_nodes_ids'] = [(0, 0, item) for item in self._prepare_hide_view_nodes(data.get('hide_view_nodes') or [], warnings)]
        vals['hide_filters_groups_ids'] = [(0, 0, item) for item in self._prepare_hide_filters_groups(data.get('hide_filters_groups') or [], warnings)]

        if 'hide_chatter_ids' in Access._fields:
            vals['hide_chatter_ids'] = [(0, 0, item) for item in self._prepare_hide_chatter(data.get('hide_chatter_rules') or [], warnings)]
        return vals, warnings

    # ------------------------------------------------------------------
    # Resolvers
    # ------------------------------------------------------------------
    def _resolve_xmlid(self, xmlid):
        if not xmlid:
            return self.env['ir.model.data']
        try:
            return self.env.ref(xmlid, raise_if_not_found=False)
        except Exception:
            return self.env['ir.model.data']

    def _resolve_model(self, model_name, warnings=None):
        if not model_name:
            return self.env['ir.model']
        model = self.env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
        if not model and warnings is not None:
            warnings.append(_('OMITIDO: modelo no encontrado: %s') % model_name)
        return model

    def _resolve_users(self, users):
        ids = []
        warnings = []
        User = self.env['res.users'].sudo()
        for item in users:
            login = item.get('login')
            email = item.get('email')
            domain = []
            if login and email:
                domain = ['|', ('login', '=', login), ('email', '=', email)]
            elif login:
                domain = [('login', '=', login)]
            elif email:
                domain = [('email', '=', email)]
            if not domain:
                continue
            user = User.search(domain, limit=1)
            if user:
                ids.append(user.id)
            else:
                warnings.append(_('ADVERTENCIA: usuario no encontrado: %s') % (login or email))
        return ids, warnings

    def _resolve_companies(self, companies):
        ids = []
        warnings = []
        Company = self.env['res.company'].sudo()
        for item in companies:
            company = self._resolve_xmlid(item.get('xmlid'))
            if not company or company._name != 'res.company':
                name = item.get('name')
                company = Company.search([('name', '=', name)], limit=1) if name else Company
            if company:
                ids.append(company.id)
            else:
                warnings.append(_('ADVERTENCIA: compañía no encontrada: %s') % (item.get('name') or item.get('xmlid')))
        return ids, warnings

    def _resolve_menus(self, menus):
        Access = self.env['access.management']
        comodel = Access._fields['hide_menu_ids'].comodel_name
        ids = []
        warnings = []
        for item in menus:
            menu = self._resolve_menu(item)
            if not menu:
                warnings.append(_('ADVERTENCIA: menú no encontrado: %s') % (item.get('complete_name') or item.get('name') or item.get('xmlid')))
                continue
            if comodel == 'ir.ui.menu':
                ids.append(menu.id)
            elif comodel == 'menu.item':
                menu_item = self._get_or_create_menu_item(menu, item)
                ids.append(menu_item.id)
        return ids, warnings

    def _resolve_menu(self, item):
        menu = self._resolve_xmlid(item.get('xmlid'))
        if menu and menu._name == 'ir.ui.menu':
            return menu.sudo()
        Menu = self.env['ir.ui.menu'].sudo()
        complete_name = item.get('complete_name')
        name = item.get('name')
        if complete_name and 'complete_name' in Menu._fields:
            menu = Menu.search([('complete_name', '=', complete_name)], limit=1)
            if menu:
                return menu
        if name:
            return Menu.search([('name', '=', name)], limit=1)
        return Menu

    def _get_or_create_menu_item(self, menu, item):
        MenuItem = self.env['menu.item'].sudo()
        rec = MenuItem.search([('menu_id', '=', menu.id)], limit=1)
        if not rec:
            rec = MenuItem.create({
                'name': item.get('name') or getattr(menu, 'complete_name', False) or menu.name,
                'menu_id': menu.id,
            })
        return rec

    def _resolve_field_ids(self, model, field_names, warnings):
        if not model:
            return []
        Field = self.env['ir.model.fields'].sudo()
        fields_found = Field.search([('model_id', '=', model.id), ('name', 'in', field_names)])
        found_names = set(fields_found.mapped('name'))
        for field_name in field_names:
            if field_name not in found_names:
                warnings.append(_('ADVERTENCIA: campo no encontrado %s.%s') % (model.model, field_name))
        return fields_found.ids

    def _resolve_view_data_ids(self, tech_names):
        ViewData = self.env['view.data'].sudo()
        return ViewData.search([('techname', 'in', tech_names)]).ids

    def _resolve_action_data_ids(self, actions, fallback_model=False, fallback_type=False, warnings=None):
        ids = []
        Action = self.env['ir.actions.actions'].sudo()
        ActionData = self.env['action.data'].sudo()
        for item in actions:
            action = self._resolve_xmlid(item.get('xmlid'))
            if not action or action._name != 'ir.actions.actions':
                domain = []
                action_type = item.get('type') or fallback_type
                if action_type:
                    domain.append(('type', '=', action_type))
                if item.get('name'):
                    domain.append(('name', '=', item.get('name')))
                model_name = item.get('binding_model') or fallback_model
                if model_name:
                    model = self._resolve_model(model_name)
                    if model:
                        domain.append(('binding_model_id', '=', model.id))
                action = Action.search(domain, limit=1) if domain else Action
            if action:
                action_data = ActionData.search([('action_id', '=', action.id)], limit=1)
                if not action_data:
                    action_data = ActionData.create({'name': action.name, 'action_id': action.id})
                ids.append(action_data.id)
            elif warnings is not None:
                warnings.append(_('ADVERTENCIA: acción no encontrada: %s') % (item.get('xmlid') or item.get('name')))
        return ids

    def _get_or_create_store_node(self, item, forced_option, warnings):
        model = self._resolve_model(item.get('model'), warnings)
        if not model:
            return False
        Store = self.env['store.model.nodes'].sudo()
        domain = [
            ('model_id', '=', model.id),
            ('node_option', '=', item.get('node_option') or forced_option),
            ('attribute_name', '=', item.get('attribute_name') or False),
            ('attribute_string', '=', item.get('attribute_string') or False),
        ]
        if item.get('button_type'):
            domain.append(('button_type', '=', item.get('button_type')))
        rec = Store.search(domain, limit=1)
        if rec:
            return rec
        vals = {
            'model_id': model.id,
            'node_option': item.get('node_option') or forced_option,
            'attribute_name': item.get('attribute_name') or False,
            'attribute_string': item.get('attribute_string') or item.get('attribute_name') or '-',
        }
        for fname in ['button_type', 'is_smart_button', 'lang_code']:
            if fname in Store._fields and fname in item:
                vals[fname] = item.get(fname)
        return Store.create(vals)

    def _get_or_create_filter_node(self, item, forced_option, warnings):
        model = self._resolve_model(item.get('model'), warnings)
        if not model:
            return False
        Store = self.env['store.filters.groups'].sudo()
        domain = [
            ('model_id', '=', model.id),
            ('node_option', '=', item.get('node_option') or forced_option),
            ('attribute_name', '=', item.get('attribute_name') or False),
        ]
        rec = Store.search(domain, limit=1)
        if rec:
            return rec
        return Store.create({
            'model_id': model.id,
            'node_option': item.get('node_option') or forced_option,
            'attribute_name': item.get('attribute_name') or False,
            'attribute_string': item.get('attribute_string') or item.get('attribute_name') or '-',
        })

    # ------------------------------------------------------------------
    # Line preparers
    # ------------------------------------------------------------------
    def _prepare_hide_fields(self, lines, warnings):
        vals_list = []
        for item in lines:
            model = self._resolve_model(item.get('model'), warnings)
            if not model:
                continue
            field_ids = self._resolve_field_ids(model, item.get('fields') or [], warnings)
            vals_list.append({
                'model_id': model.id,
                'field_id': [(6, 0, field_ids)],
                'invisible': bool(item.get('invisible')),
                'readonly': bool(item.get('readonly')),
                'required': bool(item.get('required')),
                'external_link': bool(item.get('external_link')),
            })
        return vals_list

    def _prepare_remove_actions(self, lines, warnings):
        vals_list = []
        Remove = self.env['remove.action']
        bool_fields = [
            'restrict_export', 'restrict_import', 'readonly', 'restrict_create',
            'restrict_edit', 'restrict_delete', 'restrict_archive_unarchive',
            'restrict_duplicate', 'restrict_chatter', 'restrict_spreadsheet',
        ]
        for item in lines:
            model = self._resolve_model(item.get('model'), warnings)
            if not model:
                continue
            vals = {
                'model_id': model.id,
                'view_data_ids': [(6, 0, self._resolve_view_data_ids(item.get('views') or []))],
                'server_action_ids': [(6, 0, self._resolve_action_data_ids(
                    item.get('server_actions') or [], fallback_model=model.model,
                    fallback_type=False, warnings=warnings))],
                'report_action_ids': [(6, 0, self._resolve_action_data_ids(
                    item.get('report_actions') or [], fallback_model=model.model,
                    fallback_type='ir.actions.report', warnings=warnings))],
            }
            for fname in bool_fields:
                if fname in Remove._fields and fname in item:
                    vals[fname] = bool(item.get(fname))
            vals_list.append(vals)
        return vals_list

    def _prepare_access_domains(self, lines, warnings):
        vals_list = []
        for item in lines:
            model = self._resolve_model(item.get('model'), warnings)
            if not model:
                continue
            vals_list.append({
                'model_id': model.id,
                'apply_domain': bool(item.get('apply_domain')),
                'domain': item.get('domain') or '[]',
                'read_right': bool(item.get('read_right')),
                'create_right': bool(item.get('create_right')),
                'write_right': bool(item.get('write_right')),
                'delete_right': bool(item.get('delete_right')),
            })
        return vals_list

    def _prepare_hide_view_nodes(self, lines, warnings):
        vals_list = []
        for item in lines:
            model = self._resolve_model(item.get('model'), warnings)
            if not model:
                continue
            btn_ids = [rec.id for rec in [self._get_or_create_store_node(n, 'button', warnings) for n in item.get('buttons') or []] if rec]
            page_ids = [rec.id for rec in [self._get_or_create_store_node(n, 'page', warnings) for n in item.get('pages') or []] if rec]
            link_ids = [rec.id for rec in [self._get_or_create_store_node(n, 'link', warnings) for n in item.get('links') or []] if rec]
            vals_list.append({
                'model_id': model.id,
                'btn_store_model_nodes_ids': [(6, 0, btn_ids)],
                'page_store_model_nodes_ids': [(6, 0, page_ids)],
                'link_store_model_nodes_ids': [(6, 0, link_ids)],
            })
        return vals_list

    def _prepare_hide_filters_groups(self, lines, warnings):
        vals_list = []
        for item in lines:
            model = self._resolve_model(item.get('model'), warnings)
            if not model:
                continue
            filter_ids = [rec.id for rec in [self._get_or_create_filter_node(n, 'filter', warnings) for n in item.get('filters') or []] if rec]
            group_ids = [rec.id for rec in [self._get_or_create_filter_node(n, 'group', warnings) for n in item.get('groups') or []] if rec]
            vals_list.append({
                'model_id': model.id,
                'filters_store_model_nodes_ids': [(6, 0, filter_ids)],
                'groups_store_model_nodes_ids': [(6, 0, group_ids)],
            })
        return vals_list

    def _prepare_hide_chatter(self, lines, warnings):
        HideChatter = self.env['hide.chatter']
        vals_list = []
        for item in lines:
            model = self._resolve_model(item.get('model'), warnings)
            if not model:
                continue
            vals = {'model_id': model.id}
            for fname in ['hide_chatter', 'hide_send_mail', 'hide_log_notes', 'hide_schedule_activity']:
                if fname in HideChatter._fields and fname in item:
                    vals[fname] = bool(item.get(fname))
            vals_list.append(vals)
        return vals_list
