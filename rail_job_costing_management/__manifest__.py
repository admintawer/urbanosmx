# -*- coding: utf-8 -*-
{
    'name': "Job Costing",
    'version': '6.7.4.20',
    'depends': [
                'sale',
                'project', #Odoo11
                'hr_timesheet', #Odoo11
#               'project_issue',
#               'hr_timesheet_sheet',
                'purchase',
                'note', 
                'stock',
                #'account_budget',
                'stock_account',
                'rail_material_purchase_requisitions',
                ],
    'category' : 'Projects',
    'price': 99.0,
    'currency': 'EUR',
    'author': "Rail Consulting / Kevin Lopez",
    'website': "http://www.probuse.com",
    'data':[
            'security/construction_security.xml',
            'security/ir.model.access.csv',
            'data/jobcost_sequence.xml',
            'wizard/project_user_subtask_view.xml',
#             'wizard/purchase_order_view.xml',
            'views/job_costing_view.xml',
            'views/project.xml',
            'views/job_type.xml',
            'views/job_cost_to_lines.xml',
            'views/construction_management_view.xml',
            'views/note_view.xml',
            'views/product_view.xml',
            'views/project_report.xml',
            'views/project_task_view.xml',
            'views/project_view_construct.xml',
            'views/purchase_view.xml',
            'views/report_noteview.xml',
            'views/report_reg.xml',
            'views/stock_picking.xml',
            'views/task_report.xml',
            'views/order_lines_view.xml',
            'report/job_costing_report.xml',
            'views/purchase_requisition_view.xml',
            'report/purchase_requisition_report.xml',
    ],
    'installable' : True,
    'application' : False,
    'auto_install' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
