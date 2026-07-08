# -*- coding: utf-8 -*-
import base64
import json

from odoo import _, fields, models, release
from odoo.exceptions import UserError


class AccessManagementJsonIO(models.Model):
    _inherit = 'access.management'

    def _sam_json_check_manager(self):
        """Keep the transient models ACL simple, but enforce the real permission here.

        The vendor module uses different group XMLIDs between versions:
        - v16: simplify_access_management.group_access_management_spt
        - v18: simplify_access_management.group_access_management_bits
        """
        group_xmlids = [
            'simplify_access_management.group_access_management_bits',
            'simplify_access_management.group_access_management_spt',
            'base.group_system',
        ]
        for xmlid in group_xmlids:
            try:
                if self.env.user.has_group(xmlid):
                    return True
            except Exception:
                continue
        raise UserError(_('No tiene permisos para importar/exportar reglas de Access Management.'))

    def action_export_sam_json(self):
        self._sam_json_check_manager()
        records = self.sudo()
        if not records:
            raise UserError(_('Seleccione al menos una regla para exportar.'))
        payload = records._sam_json_export_payload()
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        filename = 'access_management_rules_%s.json' % fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        wizard = self.env['sam.json.export.wizard'].sudo().create({
            'filename': filename,
            'file': base64.b64encode(content.encode('utf-8')),
            'info': _('Archivo generado con %s regla(s).') % len(records),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exportar reglas JSON'),
            'res_model': 'sam.json.export.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_open_sam_json_import(self):
        self._sam_json_check_manager()
        wizard = self.env['sam.json.import.wizard'].sudo().create({})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar reglas JSON'),
            'res_model': 'sam.json.import.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    # -------------------------------------------------------------------------
    # Export helpers
    # -------------------------------------------------------------------------
    def _sam_json_export_payload(self):
        return {
            'schema': 'simplify_access_management_json_io/1.0',
            'source_odoo_version': release.version,
            'generated_at': fields.Datetime.now().isoformat(),
            'records': [rec._sam_json_export_record() for rec in self],
        }

    def _sam_json_xmlid(self, record):
        record = record.exists()
        if not record:
            return False
        xmlids = record.get_external_id()
        return xmlids.get(record.id) or False

    def _sam_json_export_record(self):
        self.ensure_one()
        data = {
            'name': self.name,
            'active': self.active,
            'readonly': self.readonly,
            'users': [self._sam_json_export_user(user) for user in self.user_ids],
            'companies': [self._sam_json_export_company(company) for company in self.company_ids],
            'hide_menus': [self._sam_json_export_menu(menu) for menu in self.hide_menu_ids],
            'hide_fields': [line._sam_json_export_hide_field() for line in self.hide_field_ids],
            'remove_actions': [line._sam_json_export_remove_action() for line in self.remove_action_ids],
            'access_domains': [line._sam_json_export_access_domain() for line in self.access_domain_ah_ids],
            'hide_view_nodes': [line._sam_json_export_hide_view_nodes() for line in self.hide_view_nodes_ids],
            'hide_filters_groups': [line._sam_json_export_hide_filters_groups() for line in self.hide_filters_groups_ids],
        }
        optional_fields = [
            'hide_chatter', 'hide_send_mail', 'hide_log_notes', 'hide_schedule_activity',
            'hide_export', 'hide_import', 'hide_spreadsheet', 'hide_add_property',
            'disable_login', 'disable_debug_mode', 'is_apply_on_without_company',
        ]
        for fname in optional_fields:
            if fname in self._fields:
                data[fname] = bool(self[fname])
        if 'hide_chatter_ids' in self._fields:
            data['hide_chatter_rules'] = [self._sam_json_export_hide_chatter_line(line) for line in self.hide_chatter_ids]
        return data


    def _sam_json_export_hide_chatter_line(self, line):
        data = {
            'model': line.model_id.model if line.model_id else False,
        }
        for fname in ['hide_chatter', 'hide_send_mail', 'hide_log_notes', 'hide_schedule_activity']:
            if fname in line._fields:
                data[fname] = bool(line[fname])
        return data

    def _sam_json_export_user(self, user):
        return {
            'login': user.login,
            'email': user.email or False,
            'name': user.name,
        }

    def _sam_json_export_company(self, company):
        return {
            'xmlid': self._sam_json_xmlid(company),
            'name': company.name,
        }

    def _sam_json_export_menu(self, item):
        """Normalize both vendor implementations.

        v16 stores access.management.hide_menu_ids as ir.ui.menu.
        v18 stores it as menu.item with an integer menu_id pointing to ir.ui.menu.
        """
        menu = self.env['ir.ui.menu']
        exported_name = item.display_name
        if item._name == 'ir.ui.menu':
            menu = item
        elif item._name == 'menu.item':
            exported_name = item.name
            menu = self.env['ir.ui.menu'].sudo().browse(item.menu_id).exists()
        complete_name = False
        if menu:
            complete_name = getattr(menu, 'complete_name', False) or menu.display_name
        return {
            'xmlid': self._sam_json_xmlid(menu) if menu else False,
            'name': exported_name,
            'complete_name': complete_name,
        }


class SamJsonExportMixin(models.AbstractModel):
    _name = 'sam.json.export.mixin'
    _description = 'SAM JSON Export Mixin'

    def _sam_json_model_name(self, model_id):
        return model_id.model if model_id else False

    def _sam_json_xmlid(self, record):
        record = record.exists()
        if not record:
            return False
        xmlids = record.get_external_id()
        return xmlids.get(record.id) or False

    def _sam_json_export_action_data(self, action_data):
        action = action_data.action_id.exists()
        return {
            'xmlid': self._sam_json_xmlid(action) if action else False,
            'name': action.name if action else action_data.name,
            'type': action.type if action else False,
            'binding_model': action.binding_model_id.model if action and action.binding_model_id else False,
        }

    def _sam_json_export_store_node(self, node):
        return {
            'model': node.model_id.model if node.model_id else False,
            'node_option': node.node_option,
            'attribute_name': node.attribute_name or False,
            'attribute_string': node.attribute_string or False,
            'button_type': getattr(node, 'button_type', False) or False,
            'is_smart_button': bool(getattr(node, 'is_smart_button', False)),
            'lang_code': getattr(node, 'lang_code', False) or False,
        }

    def _sam_json_export_filter_node(self, node):
        return {
            'model': node.model_id.model if node.model_id else False,
            'node_option': node.node_option,
            'attribute_name': node.attribute_name or False,
            'attribute_string': node.attribute_string or False,
        }


class HideFieldJsonExport(models.Model):
    _name = 'hide.field'
    _inherit = ['hide.field', 'sam.json.export.mixin']

    def _sam_json_export_hide_field(self):
        self.ensure_one()
        return {
            'model': self._sam_json_model_name(self.model_id),
            'fields': [field.name for field in self.field_id],
            'invisible': bool(self.invisible),
            'readonly': bool(self.readonly),
            'required': bool(self.required),
            'external_link': bool(self.external_link),
        }


class RemoveActionJsonExport(models.Model):
    _name = 'remove.action'
    _inherit = ['remove.action', 'sam.json.export.mixin']

    def _sam_json_export_remove_action(self):
        self.ensure_one()
        bool_fields = [
            'restrict_export', 'restrict_import', 'readonly', 'restrict_create',
            'restrict_edit', 'restrict_delete', 'restrict_archive_unarchive',
            'restrict_duplicate', 'restrict_chatter', 'restrict_spreadsheet',
        ]
        data = {
            'model': self._sam_json_model_name(self.model_id),
            'views': [view.techname for view in self.view_data_ids],
            'server_actions': [self._sam_json_export_action_data(action) for action in self.server_action_ids],
            'report_actions': [self._sam_json_export_action_data(action) for action in self.report_action_ids],
        }
        for fname in bool_fields:
            if fname in self._fields:
                data[fname] = bool(self[fname])
        return data


class AccessDomainJsonExport(models.Model):
    _name = 'access.domain.ah'
    _inherit = ['access.domain.ah', 'sam.json.export.mixin']

    def _sam_json_export_access_domain(self):
        self.ensure_one()
        return {
            'model': self._sam_json_model_name(self.model_id),
            'apply_domain': bool(self.apply_domain),
            'domain': self.domain or '[]',
            'read_right': bool(self.read_right),
            'create_right': bool(self.create_right),
            'write_right': bool(self.write_right),
            'delete_right': bool(self.delete_right),
        }


class HideViewNodesJsonExport(models.Model):
    _name = 'hide.view.nodes'
    _inherit = ['hide.view.nodes', 'sam.json.export.mixin']

    def _sam_json_export_hide_view_nodes(self):
        self.ensure_one()
        return {
            'model': self._sam_json_model_name(self.model_id),
            'buttons': [self._sam_json_export_store_node(node) for node in self.btn_store_model_nodes_ids],
            'pages': [self._sam_json_export_store_node(node) for node in self.page_store_model_nodes_ids],
            'links': [self._sam_json_export_store_node(node) for node in self.link_store_model_nodes_ids],
        }


class HideFiltersGroupsJsonExport(models.Model):
    _name = 'hide.filters.groups'
    _inherit = ['hide.filters.groups', 'sam.json.export.mixin']

    def _sam_json_export_hide_filters_groups(self):
        self.ensure_one()
        return {
            'model': self._sam_json_model_name(self.model_id),
            'filters': [self._sam_json_export_filter_node(node) for node in self.filters_store_model_nodes_ids],
            'groups': [self._sam_json_export_filter_node(node) for node in self.groups_store_model_nodes_ids],
        }
