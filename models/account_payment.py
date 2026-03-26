from odoo import models, fields

class AccountPayment(models.Model):
    _inherit = "account.payment"

    expense_type = fields.Many2one(
        'product.template',
        string="Expense Type",
        domain=[('can_be_expensed', '=', True)]
    )