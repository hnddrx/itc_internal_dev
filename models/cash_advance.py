from odoo import models, fields, api
from odoo.exceptions import UserError

class CashAdvance(models.Model):
    _name = 'cash.advance'
    _description = 'Employee Cash Advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # -----------------------------
    # Basic Info
    # -----------------------------
    name = fields.Char(string="Reference", default='New', copy=False, tracking=True)
    employee_id = fields.Many2one('res.partner', string="Employee", required=True, tracking=True)
    request_date = fields.Date(string="Request Date", default=fields.Date.today)
    department_id = fields.Many2one('hr.department', string="Department")
    purpose = fields.Text(string="Purpose", required=True)

    # -----------------------------
    # Amounts
    # -----------------------------
    amount_requested = fields.Float(string="Requested Amount", required=True)
    amount_released = fields.Float(string="Released Amount", readonly=True)
    amount_liquidated = fields.Float(string="Total Liquidated", compute="_compute_liquidation", store=True)
    balance = fields.Float(string="Remaining Balance", compute="_compute_balance", store=True)

    # -----------------------------
    # Accounting
    # -----------------------------
    advance_account_id = fields.Many2one(
        'account.account',
        string="Advance Account",
        required=True,
        domain=[('account_type', '=', 'asset_current'), ('deprecated', '=', False)],
        help="Select a Current Asset account for the cash advance"
    )
    journal_id = fields.Many2one(
        'account.journal',
        string="Payment Journal",
        help="Select the Cash/Bank journal to release the advance"
    )

    # -----------------------------
    # Liquidation
    # -----------------------------
    liquidation_line_ids = fields.One2many(
        'cash.advance.liquidation.line',
        'cash_advance_id',
        string="Liquidation Lines"
    )

    # -----------------------------
    # Workflow status
    # -----------------------------
    status = fields.Selection([
        ('draft', 'Draft'),
        ('for_approval', 'For Manager Approval'),
        ('finance_approval', 'For Finance Approval'),
        ('approved', 'Approved'),
        ('released', 'Released'),
        ('for_liquidation', 'For Liquidation'),
        ('liquidated', 'Liquidated'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)

    # -----------------------------
    # Computed Fields
    # -----------------------------
    @api.depends('liquidation_line_ids.amount')
    def _compute_liquidation(self):
        for rec in self:
            rec.amount_liquidated = sum(rec.liquidation_line_ids.mapped('amount'))

    @api.depends('amount_released', 'amount_liquidated')
    def _compute_balance(self):
        for rec in self:
            rec.balance = rec.amount_released - rec.amount_liquidated

    # -----------------------------
    # Workflow Buttons
    # -----------------------------
    def action_submit(self):
        self.status = 'for_approval'

    def action_manager_approve(self):
        self.status = 'finance_approval'

    def action_finance_approve(self):
        self.status = 'approved'

    def action_release(self):
        if self.amount_requested <= 0:
            raise UserError("Requested amount must be greater than 0")
        if not self.advance_account_id:
            raise UserError("Select an advance account.")
        if not self.journal_id:
            raise UserError("Select a journal for releasing cash.")
        if not self.journal_id.default_account_id:
            raise UserError("Selected journal must have a default account set.")

        cash_account_id = self.journal_id.default_account_id.id
         
        move = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.request_date,
            'ref': f"CA-{self.name}",
            'move_type': 'entry',
            'line_ids': [
                (0, 0, {
                    'account_id': self.advance_account_id.id,
                    'partner_id': self.employee_id.id,
                    'debit': self.amount_requested,
                    'credit': 0.0,
                    'name': f"Cash Advance to {self.employee_id.name}"
                }),
                (0, 0, {
                    'account_id': cash_account_id,
                    'partner_id': self.employee_id.id,
                    'debit': 0.0,
                    'credit': self.amount_requested,
                    'name': f"Cash Paid to {self.employee_id.name}"
                }),
            ]
        })
        move.action_post()
        self.amount_released = self.amount_requested
        self.status = 'released'

    def action_submit_liquidation(self):
        if not self.liquidation_line_ids:
            raise UserError("Add at least one liquidation line before submitting.")
        self.status = 'for_liquidation'

    def action_liquidate(self):
        if not self.liquidation_line_ids:
            raise UserError("Cannot liquidate without any liquidation lines.")
        if self.balance > 0:
            self._create_cash_return_entry()
        elif self.balance < 0:
            self._create_reimbursement_entry()
        self.status = 'liquidated'

    def action_cancel(self):
        self.status = 'cancelled'

    def action_draft(self):
        self.status = 'draft'

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('cash.advance') or 'New'
        return super().create(vals)

    # -----------------------------
    # Internal Accounting Helpers
    # -----------------------------
    def _create_cash_return_entry(self):
        cash_account_id = self.journal_id.default_account_id.id
       
        move = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'move_type': 'entry',
            'date': self.liquidation_line_ids.date,
            'ref': f"{self.liquidation_line_ids.description}",
            'line_ids': [
                (0, 0, {'account_id': cash_account_id, 'debit': self.balance, 'credit': 0.0}),
                (0, 0, {'account_id': self.advance_account_id.id, 'debit': 0.0, 'credit': self.balance}),
            ]
        })
        move.action_post()

    def _create_reimbursement_entry(self):
        cash_account_id = self.journal_id.default_account_id.id
        move = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.liquidation_line_ids.date,
            'ref': f"{self.liquidation_line_ids.description}",
            'move_type': 'entry',
            'line_ids': [
                (0, 0, {'account_id': self.advance_account_id.id, 'debit': 0.0, 'credit': abs(self.balance)}),
                (0, 0, {'account_id': cash_account_id, 'debit': abs(self.balance), 'credit': 0.0}),
            ]
        })
        move.action_post()


class CashAdvanceLiquidationLine(models.Model):
    _name = 'cash.advance.liquidation.line'
    _description = 'Cash Advance Liquidation Line'

    cash_advance_id = fields.Many2one('cash.advance', string="Cash Advance", ondelete='cascade')
    date = fields.Date(string="Date", required=True)
    description = fields.Char(string="Description", required=True)
    reference = fields.Char(string="OR / Receipt No.")
    amount = fields.Float(string="Amount", required=True)
    attachment = fields.Binary(string="Receipt / Attachment")