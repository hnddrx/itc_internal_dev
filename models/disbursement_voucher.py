from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DisbursementVoucher(models.Model):
    _name = 'disbursement.voucher'
    _description = 'Disbursement Voucher Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'voucher_date desc, id desc'
    _rec_name = 'voucher_number'

    # ─── Header Fields ────────────────────────────────────────────────────────
    voucher_number = fields.Char(
        string='Voucher Number', copy=False, readonly=True,
        default='New', tracking=True,
        help='Auto-generated check voucher number (CV-XXXXXXXXXXXX). Assigned automatically on save.',
    )
    voucher_date = fields.Date(
        string='Voucher Date', required=True,
        default=fields.Date.today, tracking=True,
        help='The date this disbursement voucher is created or recorded.',
    )
    payment_date = fields.Date(
        string='Payment Date', tracking=True,
        help='The actual date the payment was or will be made to the supplier/payee. '
             'Set automatically when the voucher is released.',
    )
    status = fields.Selection([
        ('draft', 'Draft'),
        ('for_approval', 'For Approval'),
        ('payable_entry', 'Payable Voucher Entry'),
        ('disbursement_entry', 'Disbursement Voucher Entry'),
        ('released', 'Released'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True,
       tracking=True, copy=False,
    )

    # ─── Supplier / Payee ────────────────────────────────────────────────────
    payee_type = fields.Selection([
        ('supplier', 'Supplier/Payee'),
        ('employee', 'Employee/Agent'),
    ], string='Payee Type', default='supplier', required=True,
       help='Choose whether the disbursement is going to an external supplier/payee '
            'or an internal employee/agent.',
    )
    partner_id = fields.Many2one(
        'res.partner', string='Supplier/Payee',
        tracking=True,
        help='The external company or individual receiving the payment.',
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Employee/Agent',
        tracking=True,
        help='The internal employee or agent receiving the disbursement.',
    )
    supplier_tin = fields.Char(
        string='Supplier TIN',
        compute='_compute_supplier_tin', store=True, readonly=False,
        help='Tax Identification Number of the supplier. Auto-filled from the supplier record.',
    )
    particulars = fields.Text(
        string='Particulars', tracking=True,
        help='Brief description of what this disbursement is for '
             '(e.g., "Payment for monthly service fee acct.#8000234682 for December 2024").',
    )

    # ─── Expense Type ────────────────────────────────────────────────────────
    expense_type_id = fields.Many2one(
        'disbursement.expense.type', string='Expense Type',
        required=True, tracking=True,
        help='Category of the expense being disbursed '
             '(e.g., Import Request for Payment, Direct Payment, Utility Payment).',
    )
    source_type = fields.Selection([
        ('asset', 'Asset Data Entry'),
        ('importation', 'Importation Entry'),
        ('manual', 'Manual'),
    ], string='Source Type', default='manual', tracking=True,
       help='Indicates where this voucher originated from: an Asset entry, '
            'an Importation entry, or created manually.',
    )

    # ─── Amounts ─────────────────────────────────────────────────────────────
    voucher_amount = fields.Monetary(
        string='Voucher Amount', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Total amount computed from all voucher detail lines.',
    )
    payment_amount = fields.Monetary(
        string='Payment Amount', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help='Net amount to be paid after deductions. Equals the voucher amount.',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency used for this voucher. Defaults to the company currency.',
    )
    fx_rate = fields.Float(
        string='F/X Rate', default=1.0, digits=(12, 6),
        help='Foreign exchange rate to convert the voucher currency to PHP. '
             'Leave as 1.0 for PHP transactions.',
    )
    amount_in_php = fields.Monetary(
        string='Amount in PHP',
        currency_field='php_currency_id',
        compute='_compute_amount_php', store=True,
        help='Voucher amount converted to Philippine Peso using the F/X Rate.',
    )
    php_currency_id = fields.Many2one(
        'res.currency', string='PHP Currency',
        default=lambda self: self.env['res.currency'].search(
            [('name', '=', 'PHP')], limit=1
        ),
    )

    # ─── Remarks ─────────────────────────────────────────────────────────────
    show_in_print = fields.Boolean(
        string='Show in Print Out', default=False,
        help='If checked, the remarks will be printed on the disbursement voucher report.',
    )
    remarks = fields.Text(
        string='Regular Remarks',
        help='General remarks or notes about this disbursement visible on the voucher.',
    )
    detailed_remarks = fields.Text(
        string='Detailed Remarks',
        help='Detailed internal notes or breakdown. '
             'Example: "Payment for Monthly service fee acct.#8000234682 the month of December 2024".',
    )

    # ─── Approval / Control ──────────────────────────────────────────────────
    checked_by_id = fields.Many2one(
        'res.users', string='Checked By', tracking=True,
        help='The user who reviewed and verified this disbursement voucher before release.',
    )
    checked_date = fields.Date(
        string='Checked Date', tracking=True,
        help='Date the voucher was checked/verified.',
    )
    entry_date = fields.Date(
        string='Entry Date', default=fields.Date.today, readonly=True,
        help='Date this record was first created in the system.',
    )
    prepared_by_id = fields.Many2one(
        'res.users', string='Prepared By',
        default=lambda self: self.env.user, tracking=True,
        help='The user who created and prepared this disbursement voucher.',
    )

    # ─── Tabs / Lines ────────────────────────────────────────────────────────
    voucher_line_ids = fields.One2many(
        'disbursement.voucher.line', 'voucher_id',
        string='Voucher Details',
    )
    payment_detail_ids = fields.One2many(
        'disbursement.payment.detail', 'voucher_id',
        string='Payment Details',
    )
    extra_credit_ids = fields.One2many(
        'disbursement.extra.credit', 'voucher_id',
        string='Extra Credit',
    )

    # ─── Linked Records ──────────────────────────────────────────────────────
    account_move_id = fields.Many2one(
        'account.move', string='Journal Entry', readonly=True, copy=False,
    )
    payable_voucher_id = fields.Many2one(
        'disbursement.voucher', string='Payable Voucher',
        domain=[('status', '=', 'payable_entry')], copy=False,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # =========================================================================
    # Computed Methods
    # =========================================================================

    @api.depends('partner_id')
    def _compute_supplier_tin(self):
        for rec in self:
            rec.supplier_tin = rec.partner_id.vat if rec.partner_id and rec.partner_id.vat else False

    @api.depends('voucher_line_ids.amount', 'extra_credit_ids.amount')
    def _compute_amounts(self):
        for rec in self:
            total = sum(rec.voucher_line_ids.mapped('amount'))
            rec.voucher_amount = total
            rec.payment_amount = total

    @api.depends('voucher_amount', 'fx_rate')
    def _compute_amount_php(self):
        for rec in self:
            rec.amount_in_php = rec.voucher_amount * rec.fx_rate

    # =========================================================================
    # ORM Overrides
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('voucher_number', 'New') == 'New':
                vals['voucher_number'] = self.env['ir.sequence'].next_by_code(
                    'disbursement.voucher'
                ) or 'New'
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['voucher_number'] = 'New'
        default['status'] = 'draft'
        return super().copy(default)

    def name_get(self):
        result = []
        for rec in self:
            partner_name = rec.partner_id.display_name if rec.partner_id else ''
            result.append((rec.id, f"{rec.voucher_number} - {partner_name}"))
        return result
    # =========================================================================
    # Workflow Actions
    # =========================================================================

    def action_submit_for_approval(self):
        for rec in self:
            if not rec.voucher_line_ids:
                raise UserError(_('You must add at least one voucher detail line before submitting.'))
            rec.status = 'for_approval'
            rec.message_post(body=_('Disbursement Voucher submitted for approval.'))

    def action_payable_entry(self):
        for rec in self:
            rec.status = 'payable_entry'
            rec.message_post(body=_('Moved to Payable Voucher Data Entry stage.'))

    def action_disbursement_entry(self):
        for rec in self:
            rec.status = 'disbursement_entry'
            rec.checked_date = fields.Date.today()
            rec.message_post(body=_('Moved to Disbursement Voucher Data Entry stage.'))

    def action_release(self):
        for rec in self:
            if not rec.checked_by_id:
                raise UserError(_('Please set the Checked By field before releasing.'))
            rec.status = 'released'
            rec.payment_date = fields.Date.today()
            rec._create_journal_entry()
            rec.message_post(body=_('Disbursement Voucher has been released.'))

    def action_cancel(self):
        for rec in self:
            if rec.status == 'released':
                raise UserError(_('A released voucher cannot be cancelled directly. Please create a reversal.'))
            rec.status = 'cancelled'
            rec.message_post(body=_('Disbursement Voucher cancelled.'))

    def action_reset_to_draft(self):
        for rec in self:
            if rec.status == 'released':
                raise UserError(_('Cannot reset a released voucher to draft.'))
            rec.status = 'draft'
            rec.message_post(body=_('Disbursement Voucher reset to Draft.'))

    # =========================================================================
    # Journal Entry Creation
    # =========================================================================

    def _create_journal_entry(self):
        self.ensure_one()
        if self.account_move_id:
            return

        journal = self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')), ('company_id', '=', self.company_id.id)],
            limit=1
        )
        if not journal:
            raise UserError(_('No bank/cash journal found. Please configure a journal.'))

        ap_account = self.env['account.account'].search([
            ('account_type', '=', 'liability_payable'),
            ('deprecated', '=', False)
        ], limit=1)

        move_lines = [(0, 0, {
            'name': self.particulars or self.voucher_number,
            'partner_id': self.partner_id.id,
            'account_id': ap_account.id if ap_account else journal.default_account_id.id,
            'credit': self.amount_in_php,
            'debit': 0.0,
        })]

        for line in self.voucher_line_ids:
            move_lines.append((0, 0, {
                'name': line.description or line.expense_type_id.name,
                'partner_id': self.partner_id.id,
                'account_id': line.account_id.id if line.account_id else journal.default_account_id.id,
                'debit': line.amount,
                'credit': 0.0,
            }))

        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': self.payment_date or fields.Date.today(),
            'ref': self.voucher_number,
            'line_ids': move_lines,
            'move_type': 'entry',
        })
        move.action_post()
        self.account_move_id = move.id

    def action_view_journal_entry(self):
        self.ensure_one()
        if not self.account_move_id:
            raise UserError(_('No journal entry linked to this voucher.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
        }

    def action_print_voucher(self):
        return self.env.ref(
            'disbursement_voucher.action_report_disbursement_voucher'
        ).report_action(self)


# =============================================================================
class DisbursementVoucherLine(models.Model):
    _name = 'disbursement.voucher.line'
    _description = 'Disbursement Voucher Line (Voucher Details Tab)'
    _order = 'sequence, id'

    voucher_id = fields.Many2one(
        'disbursement.voucher', string='Voucher',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    expense_type_id = fields.Many2one(
        'disbursement.expense.type', string='Expense Type', required=True,
    )
    purchase_category = fields.Selection([
        ('domestic_service', 'Domestic Purchase of Service'),
        ('domestic_goods', 'Domestic Purchase of Goods'),
        ('importation', 'Importation'),
        ('capex', 'Capital Expenditure'),
        ('other', 'Other'),
    ], string='Purchase Category', default='domestic_service', required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Supplier/Payee',
        related='voucher_id.partner_id', store=True,
    )
    employee_id = fields.Many2one('hr.employee', string='Employee Name')
    description = fields.Char(string='Description')
    account_id = fields.Many2one('account.account', string='Account', required=True)
    
    vat_type = fields.Selection([
        ('vat_inclusive', 'VAT-Inclusive'),
        ('vat_exclusive', 'VAT-Exclusive'),
        ('vat_exempt', 'VAT-Exempt'),
        ('zero_rated', 'Zero-Rated'),
        ('non_vat', 'Non-VAT'),
    ], string='VAT-Type', default='vat_inclusive', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', related='voucher_id.currency_id', store=True)
    vat_amount = fields.Monetary(
        string='VAT Amount', currency_field='currency_id',
        compute='_compute_vat', store=True,
    )
    net_amount = fields.Monetary(
        string='Net Amount', currency_field='currency_id',
        compute='_compute_vat', store=True,
    )
    ewt_rate = fields.Float(string='EWT Rate (%)', default=0.0)
    ewt_amount = fields.Monetary(
        string='EWT Amount', currency_field='currency_id',
        compute='_compute_ewt', store=True,
    )
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    cost_center = fields.Char(string='Cost Center')
    notes = fields.Char(string='Notes')

    @api.depends('amount', 'vat_type')
    def _compute_vat(self):
        vat_rate = 0.12
        for line in self:
            if line.vat_type == 'vat_inclusive':
                line.vat_amount = line.amount - (line.amount / (1 + vat_rate))
                line.net_amount = line.amount / (1 + vat_rate)
            elif line.vat_type == 'vat_exclusive':
                line.vat_amount = line.amount * vat_rate
                line.net_amount = line.amount
            else:
                line.vat_amount = 0.0
                line.net_amount = line.amount

    @api.depends('net_amount', 'ewt_rate')
    def _compute_ewt(self):
        for line in self:
            line.ewt_amount = line.net_amount * (line.ewt_rate / 100)


# =============================================================================
class DisbursementPaymentDetail(models.Model):
    _name = 'disbursement.payment.detail'
    _description = 'Disbursement Voucher Payment Details'
    _order = 'id'

    voucher_id = fields.Many2one(
        'disbursement.voucher', string='Voucher',
        required=True, ondelete='cascade', index=True,
    )
    payment_mode = fields.Selection([
        ('check', 'Check'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ], string='Payment Mode', required=True, default='check')
    check_number = fields.Char(string='Check Number')
    check_date = fields.Date(string='Check Date')
    bank_id = fields.Many2one('res.bank', string='Bank')
    bank_account_id = fields.Many2one('res.partner.bank', string='Bank Account')
    reference = fields.Char(string='Reference / Control No.')
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', related='voucher_id.currency_id', store=True)
    payment_date = fields.Date(string='Payment Date')
    notes = fields.Char(string='Notes')


# =============================================================================
class DisbursementExtraCredit(models.Model):
    _name = 'disbursement.extra.credit'
    _description = 'Disbursement Voucher Extra Credit'
    _order = 'id'

    voucher_id = fields.Many2one(
        'disbursement.voucher', string='Voucher',
        required=True, ondelete='cascade', index=True,
    )
    credit_type = fields.Selection([
        ('advance', 'Advance Payment'),
        ('deduction', 'Deduction'),
        ('withholding_tax', 'Withholding Tax'),
        ('other', 'Other'),
    ], string='Credit Type', required=True, default='deduction')
    description = fields.Char(string='Description', required=True)
    account_id = fields.Many2one('account.account', string='Account')
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', related='voucher_id.currency_id', store=True)
    notes = fields.Char(string='Notes')


# =============================================================================
class DisbursementExpenseType(models.Model):
    _name = 'disbursement.expense.type'
    _description = 'Disbursement Expense Type'
    _order = 'name'

    name = fields.Char(string='Expense Type', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    account_id = fields.Many2one('account.account', string='Default Account')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Expense Type name must be unique.'),
    ]
