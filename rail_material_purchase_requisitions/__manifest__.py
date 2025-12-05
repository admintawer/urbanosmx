# -*- coding: utf-8 -*-

{
    'name': 'Product/Material Purchase Requisitions by Employees/Users',
    'version': '2.7.6',
    'price': 79.0,
    'currency': 'EUR',
    'license': 'Other proprietary',
    'summary': """This module allow your employees/users to create Purchase Requisitions.""",
    'author': 'Rail Consulting / Kevin Lopez',
    'website': 'http://rail.com.mx',
    'category': 'Warehouse',
    'depends': [
                'stock',
                'hr',
                'purchase',
                ],
    'data':[
        'security/security.xml',
        'security/multi_company_security.xml',
        'security/ir.model.access.csv',
        'data/purchase_requisition_sequence.xml',
        'data/employee_purchase_approval_template.xml',
        'data/confirm_template_material_purchase.xml',
        'report/purchase_requisition_report.xml',
        'views/purchase_requisition_view.xml',
        'views/hr_employee_view.xml',
        'views/hr_department_view.xml',
        'views/stock_picking_view.xml',
    ],
    'installable' : True,
    'application' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
