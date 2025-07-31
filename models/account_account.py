from odoo import models, fields

class AccountAccount(models.Model):
    _inherit = 'account.account'

    account_type = fields.Selection(
        selection_add=[
            ('expense_manufacturing_oh', 'Manufacturing-OH'),
            ('asset_non_current_assets_contra', 'Non-current Assets (Contra)'),
            ('asset_current_assets_contra', 'Current Assets (Contra)'),
            ('expense_cost_of_sales', 'Cost of Sales'),
            ('expense_cost_of_services', 'Cost of Services'),
            ('expense_admin_expense', 'Admin Expenses'),
            ('asset_current_assets', 'Other Current Assets'),
            ('expense_non_deductable_expenses', 'Non-Deductible Expenses'),
            ('income_revenue_contra', 'Revenue (Contra)'),
            ('income_revenue', 'Revenue'),
            ('income_sales_contra', 'Sales (Contra)'),
            ('income_sales', 'Sales'),
        ],
        ondelete={
            'expense_manufacturing_oh': 'cascade',
            'asset_non_current_assets_contra': 'cascade',
            'asset_current_assets_contra': 'cascade',
            'expense_cost_of_sales': 'cascade',
            'expense_cost_of_services': 'cascade',
            'expense_admin_expense': 'cascade',
            'asset_current_assets': 'cascade',
            'expense_non_deductable_expenses': 'cascade',
            'income_revenue_contra': 'cascade',
            'income_revenue': 'cascade',
            'income_sales_contra': 'cascade',
            'income_sales': 'cascade',
        },
        tracking=True,
    )
