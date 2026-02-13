from odoo import models, api, _
from odoo.exceptions import UserError
from datetime import date

class AccountStatementWizard(models.TransientModel):
    _name = "account.statement.wizard"
    _description = "Statement of Account Wizard"

    @api.model
    def action_generate_all_due_statements(self):
        """Generate SOA for all customers with due invoices."""
        today = date.today()
        due_invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', '!=', 'paid'),
            ('invoice_date_due', '<=', today)
        ])

        if not due_invoices:
            raise UserError(_("No due invoices found."))

        partners = due_invoices.mapped('partner_id')

        return self.env.ref('itc_internal_dev.action_report_statement_of_account').report_action(partners)
