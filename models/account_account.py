from odoo import models, fields

class AccountAccount(models.Model):
    _inherit = 'account.account'

    account_type = fields.Selection(
        selection_add=[
            ('expense_manufacturing_oh', 'Manufacturing-OH'),
            ('non_current_assets', 'Non-current Assets'),
            ('non_current_liabilities', 'Non-current Liabilities'),
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
            ('expenses', 'Expenses'),
            ('other_income', 'Other Income'),
            ('operating_expenses', 'Operating Expenses'),
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
            'expenses': 'cascade',
            'other_income': 'cascade',
            'operating_expenses': 'cascade',
            'non_current_liabilities': 'cascade',
            'non_current_assets': 'cascade',

        },
        tracking=True,
    )

    
    def _get_internal_group(self, account_type):
        mapping = {
            # Assets
            'non_current_assets': 'asset',
            'asset_non_current_assets_contra': 'asset',
            'asset_current_assets_contra': 'asset',
            'asset_current_assets': 'asset',

            # Liabilities
            'non_current_liabilities': 'liability',

            # Income
            'income_revenue': 'income',
            'income_revenue_contra': 'income',
            'income_sales': 'income',
            'income_sales_contra': 'income',
            'other_income': 'income',

            # Expenses
            'expense_cost_of_sales': 'expense',
            'expense_cost_of_services': 'expense',
            'expense_admin_expense': 'expense',
            'expense_manufacturing_oh': 'expense',
            'expense_non_deductable_expenses': 'expense',
            'operating_expenses': 'expense',
            'expenses': 'expense',
        }

        if account_type in mapping:
            return mapping[account_type]

        return super()._get_internal_group(account_type)

