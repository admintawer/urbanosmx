import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { TagsList } from "@web/core/tags_list/tags_list";
import { isId } from "@web/core/tree_editor/utils";
import { useService } from "@web/core/utils/hooks";
import { RecordAutocompleteBits } from "./record_autocomplete";
import { _t } from "@web/core/l10n/translation";
import { imageUrl } from "@web/core/utils/urls";
import { useTagNavigation } from "./tag_navigation_hook";

export class MultiRecordSelectorBits extends Component {
    static props = {
        resIds: { type: Array, element: Number },
        resModel: String,
        update: Function,
        domain: { type: Array, optional: true },
        context: { type: Object, optional: true },
        fieldString: { type: String, optional: true },
        placeholder: { type: String, optional: true },
    };
    static components = { RecordAutocompleteBits, TagsList };
    static template = "awdw.MultiRecordSelectorBits";

    setup() {
        this.nameService = useService("namebits");
        useTagNavigation("multiRecordSelector", {
            delete: (index) => this.deleteTag(index),
        });
        onWillStart(() => this.computeDerivedParams());
        onWillUpdateProps((nextProps) => this.computeDerivedParams(nextProps));
    }

    get isAvatarModel() {
        // bof
        return ["res.partner", "res.users", "hr.employee", "hr.employee.public"].includes(
            this.props.resModel
        );
    }

      async computeDerivedParams(props = this.props) {
        const displayNames = await this.getDisplayNames(props);
        if (this.props.resModel === 'res.users') {
            const userIndex = props.resIds.indexOf(0);
            if (userIndex !== -1) {
                displayNames[0] = _t('Environment User');
            }
        }
        if (this.props.resModel === 'res.company') {
            const companyIndex = props.resIds.indexOf(0);
            if (companyIndex !== -1) {
                displayNames[0] = _t('Environment Companies');
            }
        }
        this.tags = this.getTags(props, displayNames);
    }

    async getDisplayNames(props) {
        const ids = this.getIds(props);
        return this.nameService.loadDisplayNames(props.resModel, ids);
    }
    /**
     * Placeholder should be empty if there is at least one tag. We cannot use
     * the default behavior of the input placeholder because even if there is
     * a tag, the input is still empty.
     */
    get placeholder() {
        return this.getTags(this.props, {}).length ? "" : this.props.placeholder;
    }

    getIds(props = this.props) {
        return props.resIds;
    }

    getTags(props, displayNames) {
        return props.resIds.map((id, index) => {
            let text;
            let img;

            // Handle environment records first
            if (id === 0) {
                if (props.resModel === 'res.users') {
                    text = 'Environment User';
                } else if (props.resModel === 'res.company') {
                    text = 'Environment Companies';
                } else {
                    text = 'Environment Record';
                }
                // Add environment user image
                img = this.isAvatarModel ? "/advanced_web_domain_widget/static/description/img/env_user.png" : false;
            } else {
                // Handle regular records
                text = typeof displayNames[id] === "string"
                    ? displayNames[id]
                    : _t("Inaccessible/missing record ID: %s", id);
                img = this.isAvatarModel &&
                    isId(id) &&
                    imageUrl(this.props.resModel, id, "avatar_128");
            }

            return {
                text,
                onDelete: () => {
                    this.deleteTag(index);
                },
                img,
            };
        });
    }


    deleteTag(index) {
        this.props.update([
            ...this.props.resIds.slice(0, index),
            ...this.props.resIds.slice(index + 1),
        ]);
    }

    update(resIds) {
        this.props.update([...this.props.resIds, ...resIds]);
    }
}
