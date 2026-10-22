# -*- coding: utf-8 -*-
#################################################################################
# Author      : Terabits Technolab (<www.terabits.xyz>)
# Copyright(c): 2023-26
# All Rights Reserved.
#
# This module is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
{
    "name": "Advanced Web Domain Widget",
    "version": "19.0.3.0.0",
    "summary": """This widget lets you build dynamic filters for relational fields using simple operators like "in" and "not in". Pick the records you want without wrestling with long domain expressions.
Web Domain Widget, Domain Filter, Dynamic Domain, Relational Fields, Domain Builder, Record Filtering, Many2one Domain, Many2many Domain, Odoo Domain Editor""",
    "sequence": 10,
    "author": "Terabits Technolab",
    "license": "OPL-1",
    "website": "https://www.terabits.xyz/apps/19.0/advanced_web_domain_widget",
    "description": """This widget lets you build dynamic filters for relational fields using simple operators like "in" and "not in". Pick the records you want without wrestling with long domain expressions.""",
    "price": "5.00",
    "currency": "USD",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "advanced_web_domain_widget/static/src/tree_editor/*.js",
            "advanced_web_domain_widget/static/src/tree_editor/*.xml",
            "advanced_web_domain_widget/static/src/domain_selector/*.js",
            "advanced_web_domain_widget/static/src/domain_selector/*.xml",
            "advanced_web_domain_widget/static/src/domain_selector_dialog/*.js",
            "advanced_web_domain_widget/static/src/domain_selector_dialog/*.xml",
            "advanced_web_domain_widget/static/src/domain/*.js",
            "advanced_web_domain_widget/static/src/domain/*.xml",
            "advanced_web_domain_widget/static/src/model_field_selector/*.js", 
            "advanced_web_domain_widget/static/src/model_field_selector/*.xml", 
            "advanced_web_domain_widget/static/src/autocomplete/*",
            "advanced_web_domain_widget/static/src/record_selectors/*.js",
            "advanced_web_domain_widget/static/src/record_selectors/*.xml",
            "advanced_web_domain_widget/static/src/name_service.js"
        ],
    },
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
}
