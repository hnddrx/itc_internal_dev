{
    'name': 'ITC Development',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Manage Employee Salary Advances with Accounting Integration',
    'author': 'ITC - Odoo Team',
    'depends': ['hr', 'hr_payroll', 'account', 'mail', 'base', 'web', 'helpdesk'],
    'data': [
        #Security
        'security/custom_sql_report_security.xml',
        'security/salary_advance_security.xml',
        'security/ir.model.access.csv',

        #Data
        'data/salary_advance.xml',

        #Report
        'report/sales_invoice_report.xml',
        'report/sales_order_report.xml',
        'report/purchase_order_report.xml',
        'report/official_receipt_report.xml',
        'report/service_invoice_report.xml',
        'report/credit_memo_report.xml',
        'report/report_statement_of_account_template.xml',
        'report/acknowledgement_report.xml',
        #Views
        'views/salary_advance_views.xml',
        'views/expense_view.xml',
        'views/purchase_order.xml',
        'views/account_account_views.xml',
        'views/sales_order.xml',
        'views/account_move_views.xml',
        'views/sql_report_views.xml',
        #'views/sales_order_line.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'itc_internal_dev/static/src/css/custom_buttons.css',
            'itc_internal_dev/static/src/css/required.css',
        ],
    },
    'installable': True,
    'application': True,
    'icon': '/itc_internal_dev/static/description/ITCLOGO.jpg',
}