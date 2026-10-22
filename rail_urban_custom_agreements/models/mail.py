# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools import email_split


class MailMail(models.Model):
    _inherit = 'mail.mail'

    email_bcc = fields.Char(string='Bcc')

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        """Pass Bcc through Odoo 19's normal mail pipeline."""
        values_list = super()._prepare_outgoing_list(
            mail_server=mail_server,
            doc_to_followers=doc_to_followers,
        )
        bcc = email_split(self.email_bcc or '')
        if bcc:
            for values in values_list:
                values['headers'] = dict(values.get('headers') or {}, Bcc=', '.join(bcc))
        return values_list


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    email_bcc = fields.Char(string='Bcc')

    def _generate_template(self, res_ids, render_fields,
                           recipients_allow_suggested=False,
                           find_or_create_partners=False):
        result = super()._generate_template(
            res_ids,
            render_fields,
            recipients_allow_suggested=recipients_allow_suggested,
            find_or_create_partners=find_or_create_partners,
        )
        if 'email_bcc' in render_fields:
            for res_id in res_ids:
                result[res_id]['email_bcc'] = self.email_bcc
        return result


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_bcc = fields.Char(string='Bcc')

    def _prepare_mail_values(self, res_ids):
        values = super()._prepare_mail_values(res_ids)
        for res_id in res_ids:
            values[res_id]['email_bcc'] = self.email_bcc
        return values
