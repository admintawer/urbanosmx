import { constructDomainFromTree } from "@web/core/tree_editor/construct_domain_from_tree";
import { eliminateVirtualOperators } from "./virtual_operators";

export function domainFromTree(tree) {
    const simplifiedTree = eliminateVirtualOperators(tree);
    return constructDomainFromTree(simplifiedTree);
}
