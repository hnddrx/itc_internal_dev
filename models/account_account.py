from odoo import models

class AccountAccount(models.Model):
    _inherit = 'account.account'

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
