from odoo import models, fields, api
from datetime import date


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    x_regular_remarks = fields.Text(string="Regular Remarks")
    x_detailed_remarks = fields.Text(string="Detailed Remarks")
    x_particulars = fields.Text(string="Particulars")
    x_checked_by = fields.Many2one('res.users', string="Checked By")
    x_checked_by_date = fields.Date(string="Checked Date", readonly=True)


    x_vendor_tin = fields.Char(string="Vendor TIN", 
    readonly=True,
    store=True,
    help="Tax Identification Number of the vendor associated with this expense.")

    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        domain=[('supplier_rank', '>', 0)],
        help="Supplier for reference only. Appears in journal entries if Paid by Employee."
    )

    #field linked to payment_terms
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

    @api.onchange('vendor_id')
    def _onchange_vendor_id(self):
        for record in self:
            record.x_vendor_tin = record.vendor_id.vat or ''

    @api.depends('x_voucher_amount')
    def _compute_payment_amount(self):
        for record in self:
           discount_percentage = record.x_voucher.discount_percentage
           discount = 1 - (discount_percentage / 100) if discount_percentage else 1
           record.x_voucher_amount = record.x_voucher_amount * discount
           record.x_payment_amount = record.x_voucher_amount

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

    @api.onchange('x_checked_by')
    def _onchange_checked_by(self):
        for record in self:
            if record.x_checked_by and not record.x_checked_by_date:
                record.x_checked_by_date = date.today()

    def _prepare_move_line_values(self):
        """Set supplier on debit lines only if Paid by Employee."""
        move_line_vals = super()._prepare_move_line_values()

        for expense in self:
            # Check if Paid by Employee
            if expense.payment_mode == 'own_account':
                if expense.supplier_id:
                    for line in move_line_vals:
                        # Debit lines (Expense + VAT) → partner = supplier
                        if line.get('debit', 0) > 0:
                            line['partner_id'] = expense.supplier_id.id

                        # Credit line (Payable) → partner = Employee
                        if line.get('credit', 0) > 0:
                            if expense.employee_id.address_home_id:
                                line['partner_id'] = expense.employee_id.address_home_id.id
            # Else: Paid by Company → do nothing, normal cash/bank
        return move_line_vals
