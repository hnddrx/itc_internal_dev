{
    'name': 'ITC Development',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Manage Employee Salary Advances with Accounting Integration',
    'author': 'ITC Odoo Team',
    'depends': ['hr', 'hr_payroll', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/salary_advance_security.xml',
        'data/salary_advance.xml',
        'views/salary_advance_views.xml',
        'views/expense_view.xml',
        'views/purchase_order.xml',

        #account_account
        'views/account_account_views.xml',
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