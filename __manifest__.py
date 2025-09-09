{
    'name': 'ITC Development',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Manage Employee Salary Advances with Accounting Integration',
    'author': 'ITC - Odoo Team',
    'depends': ['hr', 'hr_payroll', 'account', 'mail'],
    'data': [
        #Security
        'security/ir.model.access.csv',
        'security/salary_advance_security.xml',

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
        #Views
        'views/salary_advance_views.xml',
        'views/expense_view.xml',
        'views/purchase_order.xml',
        'views/account_account_views.xml',
        'views/sales_order.xml',
        'views/account_move_views.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'itc_internal_dev/static/src/css/custom_buttons.css',
        ],
    },
    'installable': True,
    'application': True,
    'icon': '/itc_internal_dev/static/description/ITCLOGO.jpg',
}