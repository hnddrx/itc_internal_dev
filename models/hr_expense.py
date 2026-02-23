from odoo import models, fields, api
from datetime import date
import logging

_logger = logging.getLogger(__name__)

class HrExpense(models.Model):
    _inherit = 'hr.expense'

    # ----------------------
    # Custom Fields
    # ----------------------
    x_regular_remarks = fields.Text(string="Regular Remarks")
    x_detailed_remarks = fields.Text(string="Detailed Remarks")
    x_particulars = fields.Text(string="Particulars")
    x_checked_by = fields.Many2one('res.users', string="Checked By")
    x_checked_by_date = fields.Date(string="Checked Date", readonly=True)

    x_vendor_tin = fields.Char(
        string="Vendor TIN",
        readonly=True,
        store=True,
        help="Tax Identification Number of the vendor associated with this expense."
    )

    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        domain=[('supplier_rank', '>', 0)],
        help="Supplier for reference only. Appears in journal entries if Paid by Employee."
    )

    x_voucher = fields.Many2one(
        'account.payment.term',
        string='Voucher ID',
        help="Payment terms for the expense voucher.",
    )

    x_voucher_amount = fields.Monetary(
        string='Voucher Amount',
        currency_field='currency_id',
        help="Amount of the voucher associated with this expense.",
    )

    x_payment_amount = fields.Monetary(
        string='Payment Amount',
        currency_field='currency_id',
        compute='_compute_payment_amount',
        readonly=False,  
        store=True,
        help="Amount to be paid for this expense.",
    )

    x_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ----------------------
    # Onchange & Compute
    # ----------------------
    @api.onchange('vendor_id')
    def _onchange_vendor_id(self):
        for record in self:
            record.x_vendor_tin = record.vendor_id.vat or ''

    @api.depends('x_voucher_amount', 'x_voucher')
    def _compute_payment_amount(self):
        for record in self:
            amount = record.x_voucher_amount or 0
            discount_percentage = getattr(record.x_voucher, 'discount_percentage', 0)
            discount = 1 - (discount_percentage / 100) if discount_percentage else 1
            record.x_payment_amount = amount * discount

    @api.onchange('x_checked_by')
    def _onchange_checked_by(self):
        for record in self:
            if record.x_checked_by and not record.x_checked_by_date:
                record.x_checked_by_date = date.today()

    # ----------------------
    # Create / Write Overrides
    # ----------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('x_checked_by') and not vals.get('x_checked_by_date'):
                vals['x_checked_by_date'] = date.today()
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if vals.get('x_checked_by') and not rec.x_checked_by_date:
                vals['x_checked_by_date'] = date.today()
        return super().write(vals)

    # ----------------------
    # Journal Entry Override
    # ----------------------
    def action_approve_expense_sheet(self):
        res = super().action_approve_expense_sheet()
        # Loop through expense lines to set partners if journal entries already exist
        for sheet in self:
            for expense in sheet.expense_line_ids:
                for move in expense.account_move_ids:
                    for line in move.line_ids:
                        # Debit lines → Supplier
                        if expense.payment_mode == 'own_account' and expense.supplier_id and line.debit > 0:
                            line.partner_id = expense.supplier_id.id
                        # Credit lines → Employee
                        if expense.payment_mode == 'own_account' and expense.employee_id.address_home_id and line.credit > 0:
                            line.partner_id = expense.employee_id.address_home_id.id
        return res