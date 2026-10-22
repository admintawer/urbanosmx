import { Component } from "@odoo/owl";
import { TagsList } from "@web/core/tags_list/tags_list";
import { _t } from "@web/core/l10n/translation";

export class Input extends Component {
    static props = ["value", "update", "placeholder?", "startEmpty?"];
    static template = "awdw.TreeEditor.Input";
}

export class Select extends Component {
    static props = ["value", "update", "options", "placeholder?", "addBlankOption?"];
    static template = "awdw.TreeEditor.Select";

    deserialize(value) {
        return JSON.parse(value);
    }

    serialize(value) {
        return JSON.stringify(value);
    }
}

export class Range extends Component {
    static props = ["value", "update", "editorInfo"];
    static template = "awdw.TreeEditor.Range";

    update(index, newValue) {
        const result = [...this.props.value];
        result[index] = newValue;
        return this.props.update(result);
    }
}

export class InRange extends Component {
    static props = ["value", "update", "valueTypeEditorInfo", "betweenEditorInfo"];
    static template = "awdw.TreeEditor.InRange";
    static options = [
        ["today", _t("Today")],
        ["this week", _t("This Week")],
        ["this month", _t("This Month")],
        ["this quarter", _t("This Quarter")],
        ["this year", _t("This Year")],
        ["month to date", _t("Month to Date")],
        ["year to date", _t("Year to Date")],
        ["last day", _t("Last Day")],
        ["last 7 days", _t("Last 7 Days")],
        ["last 30 days", _t("Last 30 Days")],
        ["last quarter", _t("Last Quarter")],
        ["last 12 months", _t("Last 12 Months")],
        ["next day", _t("Next Day")],
        ["next week", _t("Next Week")],
        ["next month", _t("Next Month")],
        ["next quarter", _t("Next Quarter")],
        ["custom range", _t("Custom Range")],
    ];

    updateValueType(newValueType) {
        const [fieldType, currentValueType] = this.props.value;
        if (currentValueType !== newValueType) {
            const values =
                newValueType === "custom range"
                    ? this.props.betweenEditorInfo.defaultValue()
                    : [false, false];
            return this.props.update([fieldType, newValueType, ...values]);
        }
    }
    updateValues(values) {
        const [fieldType, currentValueType] = this.props.value;
        return this.props.update([fieldType, currentValueType, ...values]);
    }
}

export class List extends Component {
    static components = { TagsList };
    static props = ["value", "update", "editorInfo"];
    static template = "awdw.TreeEditor.List";

    get tags() {
        const { isSupported, stringify } = this.props.editorInfo;
        return this.props.value.map((val, index) => ({
            text: stringify(val),
            colorIndex: isSupported(val) ? 0 : 2,
            onDelete: () => {
                this.props.update([
                    ...this.props.value.slice(0, index),
                    ...this.props.value.slice(index + 1),
                ]);
            },
        }));
    }

    update(newValue) {
        return this.props.update([...this.props.value, newValue]);
    }
}
