import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { Domain } from "@web/core/domain";
import { getDomainDisplayedOperators } from "./domain_selector_operator_editor";
import { _t } from "@web/core/l10n/translation";
import { ModelFieldSelectorBits } from "../model_field_selector/model_field_selector";
import {
    areEqualTrees,
    condition,
    connector,
    formatValue,
} from "../tree_editor/condition_tree";
import { domainFromTree } from "../tree_editor/domain_from_tree";
import { TreeEditorBits } from "../tree_editor/tree_editor";
import { getOperatorEditorInfo } from "../tree_editor/tree_editor_operator_editor";
import { useService } from "@web/core/utils/hooks";
import { getDefaultCondition } from "./utils";

const ARCHIVED_CONDITION = condition("active", "in", [true, false]);
const ARCHIVED_DOMAIN = `[("active", "in", [True, False])]`;

// Define the specific company domain patterns to extract for toggle
const COMPANY_CONDITION_FALSE = condition("company_id", "=", false);
const COMPANY_CONDITION_IN = condition("company_id", "in", [0]);

export class DomainSelectorBits extends Component {
    static template = "awdw.DomainSelectorBits";
    static components = { TreeEditorBits, CheckBox };
    static props = {
        domain: String,
        resModel: String,
        className: { type: String, optional: true },
        defaultConnector: { type: [{ value: "&" }, { value: "|" }], optional: true },
        isDebugMode: { type: Boolean, optional: true },
        allowExpressions: { type: Boolean, optional: true },
        readonly: { type: Boolean, optional: true },
        update: { type: Function, optional: true },
        debugUpdate: { type: Function, optional: true },
    };
    static defaultProps = {
        isDebugMode: false,
        allowExpressions: true,
        readonly: true,
        update: () => { },
    };

    setup() {
        this.fieldService = useService("field");
        this.treeProcessor = useService("tree_processor_bits");

        this.tree = null;
        this.showArchivedCheckbox = false;
        this.includeArchived = false;
    // showCompanyFilterCheckbox will be computed based on the current model
    this.showCompanyFilterCheckbox = true;
    this.includeCompany = false;

        onWillStart(() => this.onPropsUpdated(this.props));
        onWillUpdateProps((np) => this.onPropsUpdated(np));
    }

    async onPropsUpdated(p) {
        let domain;
        let isSupported = true;
        try {
            domain = new Domain(p.domain);
        } catch {
            isSupported = false;
        }
        if (!isSupported) {
            this.tree = null;
            this.showArchivedCheckbox = false;
            this.includeArchived = false;
            return;
        }

        const [tree, { fieldDef: activeFieldDef }] = await Promise.all([
            this.treeProcessor.treeFromDomain(p.resModel, domain, !p.isDebugMode),
            this.fieldService.loadFieldInfo(p.resModel, "active"),
        ]);

        this.tree = tree;
        this.showArchivedCheckbox = this.getShowArchivedCheckBox(Boolean(activeFieldDef), p);

        this.includeArchived = false;
        if (this.showArchivedCheckbox) {
            if (this.tree.value === "&") {
                this.tree.children = this.tree.children.filter((child) => {
                    if (areEqualTrees(child, ARCHIVED_CONDITION)) {
                        this.includeArchived = true;
                        return false;
                    }
                    return true;
                });
                if (this.tree.children.length === 1) {
                    this.tree = this.tree.children[0];
                }
            } else if (areEqualTrees(this.tree, ARCHIVED_CONDITION)) {
                this.includeArchived = true;
                this.tree = connector("&");
            }
        }

    // Decide whether to show the company filter checkbox based on resModel
    this.showCompanyFilterCheckbox = this.getShowCompanyFilterCheckbox(p);
    this.includeCompany = false;

        if (this.tree) {
            if (this.tree.value === "&") {
                this.tree.children = this.tree.children.filter((child) => {
                    // Only remove the SPECIFIC company filter pattern used by toggle
                    // ['|', ('company_id', '=', False), ('company_id', 'in', [0])]
                    if (child.value === "|" && child.children && child.children.length === 2) {
                        const [first, second] = child.children;
                        if (areEqualTrees(first, COMPANY_CONDITION_FALSE) &&
                            areEqualTrees(second, COMPANY_CONDITION_IN)) {
                            this.includeCompany = true;
                            return false; // Remove this specific pattern
                        }
                    }
                    // Keep all other company_id conditions in the tree for manual editing
                    return true;
                });
                if (this.tree.children.length === 1) {
                    this.tree = this.tree.children[0];
                }
            } else if (this.tree.value === "|" && this.tree.children && this.tree.children.length === 2) {
                // Handle case where the entire tree is the company OR condition
                const [first, second] = this.tree.children;
                if (areEqualTrees(first, COMPANY_CONDITION_FALSE) &&
                    areEqualTrees(second, COMPANY_CONDITION_IN)) {
                    this.includeCompany = true;
                    this.tree = await this.treeProcessor.treeFromDomain(p.resModel, `[]`, !p.isDebugMode);
                }
            }
            // Don't remove other company_id conditions - let them show in the tree editor
        }

    }

    getShowArchivedCheckBox(hasActiveField, props) {
        return hasActiveField;
    }

    /**
     * Hide the company filter toggle when editing the company model itself.
     * This prevents showing/applying the company-specific OR filter on res.company.
     */
    getShowCompanyFilterCheckbox(props) {
        // If the current model is res.company, do not show the company filter toggle
        return !(props && props.resModel === "res.company");
    }

    getDefaultCondition(fieldDefs) {
        return getDefaultCondition(fieldDefs);
    }

    getDefaultOperator(fieldDef) {
        return getDomainDisplayedOperators(fieldDef, {
            allowExpressions: this.props.allowExpressions,
        })[0];
    }

    getOperatorEditorInfo(fieldDef) {
        const operators = getDomainDisplayedOperators(fieldDef, {
            allowExpressions: this.props.allowExpressions,
        });
        return getOperatorEditorInfo(operators, fieldDef, { resModel: this.props.resModel });
    }

    getPathEditorInfo(resModel, defaultCondition) {
        const { isDebugMode } = this.props;
        return {
            component: ModelFieldSelectorBits,
            extractProps: ({ update, value: path }) => ({
                path,
                update,
                resModel,
                isDebugMode,
                readonly: false,
            }),
            isSupported: (path) => [0, 1].includes(path) || typeof path === "string",
            defaultValue: () => defaultCondition.path,
            stringify: (path) => formatValue(path),
            message: _t("Invalid field chain"),
        };
    }

    toggleIncludeArchived() {
        this.includeArchived = !this.includeArchived;
        this.update(this.tree);
    }

    toggleApplyCompanyFilter() {
        this.includeCompany = !this.includeCompany;
        this.update(this.tree);
    }

    resetDomain() {
        this.props.update("[]");
    }

    onDomainInput(domain) {
        if (this.props.debugUpdate) {
            this.props.debugUpdate(domain);
        }
    }

    onDomainChange(domain) {
        this.props.update(domain, true);
    }
    update(tree) {
        const archiveDomain = this.includeArchived ? ARCHIVED_DOMAIN : `[]`;
        const companyDomain = this.includeCompany 
            ? `["|", ("company_id", "=", False), ("company_id", "in", [0])]` 
            : `[]`;
        const domain = tree
            ? Domain.and([domainFromTree(tree), archiveDomain, companyDomain]).toString()
            : archiveDomain;
        this.props.update(domain);
    }
}
export class DomainSelectorBits2 extends Component {
    static template = "awdw.DomainSelectorBits";
    static components = { TreeEditorBits, CheckBox };
    static props = {
        domain: String,
        resModel: String,
        className: { type: String, optional: true },
        defaultConnector: { type: [{ value: "&" }, { value: "|" }], optional: true },
        isDebugMode: { type: Boolean, optional: true },
        allowExpressions: { type: Boolean, optional: true },
        readonly: { type: Boolean, optional: true },
        update: { type: Function, optional: true },
        debugUpdate: { type: Function, optional: true },
    };
    static defaultProps = {
        isDebugMode: false,
        allowExpressions: true,
        readonly: true,
        update: () => { },
    };

    setup() {

        this.fieldService = useService("field");
        this.treeProcessor = useService("tree_processor_bits");
        this.tree = null;
        this.showArchivedCheckbox = false;
        this.includeArchived = false;
        this.showCompanyFilterCheckbox = false;
        this.includeCompany = false;

        onWillStart(() => this.onPropsUpdated(this.props));
        onWillUpdateProps((np) => this.onPropsUpdated(np));
    }

    async onPropsUpdated(p) {
        let domain;
        let isSupported = true;
        try {
            domain = new Domain(p.domain);
        } catch {
            isSupported = false;
        }
        if (!isSupported) {
            this.tree = null;
            this.showArchivedCheckbox = false;
            this.includeArchived = false;
            return;
        }

        const [tree, { fieldDef: activeFieldDef }] = await Promise.all([
            this.treeProcessor.treeFromDomain(p.resModel, domain, !p.isDebugMode),
            this.fieldService.loadFieldInfo(p.resModel, "active"),
        ]);

        this.tree = tree;
        this.showArchivedCheckbox = this.getShowArchivedCheckBox(Boolean(activeFieldDef), p);
        this.includeArchived = false;
        if (this.showArchivedCheckbox) {
            if (this.tree.value === "&") {
                this.tree.children = this.tree.children.filter((child) => {
                    if (areEqualTrees(child, ARCHIVED_CONDITION)) {
                        this.includeArchived = true;
                        return false;
                    }
                    return true;
                });
                if (this.tree.children.length === 1) {
                    this.tree = this.tree.children[0];
                }
            } else if (areEqualTrees(this.tree, ARCHIVED_CONDITION)) {
                this.includeArchived = true;
                this.tree = connector("&");
            }
        }
        this.showCompanyFilterCheckbox = false;
        this.includeCompany = false;

        if (this.tree) {
            if (this.tree.value === "&") {
                this.tree.children = this.tree.children.filter((child) => {
                    // Only remove the SPECIFIC company filter pattern used by toggle
                    // ['|', ('company_id', '=', False), ('company_id', 'in', [0])]
                    if (child.value === "|" && child.children && child.children.length === 2) {
                        const [first, second] = child.children;
                        if (areEqualTrees(first, COMPANY_CONDITION_FALSE) &&
                            areEqualTrees(second, COMPANY_CONDITION_IN)) {
                            this.includeCompany = true;
                            return false; // Remove this specific pattern
                        }
                    }
                    // Keep all other company_id conditions in the tree for manual editing
                    return true;
                });
                if (this.tree.children.length === 1) {
                    this.tree = this.tree.children[0];
                }
            } else if (this.tree.value === "|" && this.tree.children && this.tree.children.length === 2) {
                // Handle case where the entire tree is the company OR condition
                const [first, second] = this.tree.children;
                if (areEqualTrees(first, COMPANY_CONDITION_FALSE) &&
                    areEqualTrees(second, COMPANY_CONDITION_IN)) {
                    this.includeCompany = true;
                    this.tree = await this.treeProcessor.treeFromDomain(p.resModel, `[]`, !p.isDebugMode);
                }
            }
            // Don't remove other company_id conditions - let them show in the tree editor
        }
        
    }

    getShowArchivedCheckBox(hasActiveField, props) {
        return hasActiveField;
    }

    getDefaultCondition(fieldDefs) {
        return getDefaultCondition(fieldDefs);
    }

    getDefaultOperator(fieldDef) {
        return getDomainDisplayedOperators(fieldDef, {
            allowExpressions: this.props.allowExpressions,
        })[0];
    }

     getOperatorEditorInfo(fieldDef) {
        const operators = getDomainDisplayedOperators(fieldDef, {
            allowExpressions: this.props.allowExpressions,
        });
        return getOperatorEditorInfo(operators, fieldDef, { resModel: this.props.resModel });
    }

    getPathEditorInfo(resModel, defaultCondition) {
        const { isDebugMode } = this.props;
        return {
            component: ModelFieldSelectorBits,
            extractProps: ({ update, value: path }) => ({
                path,
                update,
                resModel,
                isDebugMode,
                readonly: false,
            }),
            isSupported: (path) => [0, 1].includes(path) || typeof path === "string",
            defaultValue: () => defaultCondition.path,
            stringify: (path) => formatValue(path),
            message: _t("Invalid field chain"),
        };
    }

    toggleIncludeArchived() {
        this.includeArchived = !this.includeArchived;
        this.update(this.tree);
    }
     toggleApplyCompanyFilter() {
        this.includeCompany = !this.includeCompany;
        this.update(this.tree);
    }

    resetDomain() {
        this.props.update("[]");
    }

    onDomainInput(domain) {
        if (this.props.debugUpdate) {
            this.props.debugUpdate(domain);
        }
    }

    onDomainChange(domain) {
        this.props.update(domain, true);
    }
    update(tree) {
        const archiveDomain = this.includeArchived ? ARCHIVED_DOMAIN : `[]`;
         const companyDomain = this.includeCompany 
            ? `["|", ("company_id", "=", False), ("company_id", "in", [0])]` 
            : `[]`;
        const domain = tree
            ? Domain.and([domainFromTree(tree), archiveDomain, companyDomain]).toString()
            : archiveDomain;
        this.props.update(domain);
    }
}

