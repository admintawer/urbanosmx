import { Chatter } from "@mail/chatter/web_portal/chatter";
import { user } from "@web/core/user";
import { patch } from "@web/core/utils/patch";
import { useService, } from "@web/core/utils/hooks";
import { onMounted, useState } from "@odoo/owl";

patch(Chatter.prototype, {
  setup() {
    super.setup();
    this.orm = useService("orm");
    this.access = useState({ hide_log_notes: false, hide_send_mail: false, hide_schedule_activity: false });
    onMounted(async () => {
      var self = this;
      let model = this.props.threadModel;
      let cid = user.activeCompany?.id;
      let userId = user.userId;
      if (cid && model) {
        await this.orm.call("access.management", "get_chatter_hide_details", [userId, cid, model])
          .then(function (result) {
            Object.assign(self.access, result)
          });
      }
    });
  },
});
