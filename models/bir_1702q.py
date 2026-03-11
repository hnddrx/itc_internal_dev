from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import base64
import calendar

class Bir1702Q(models.Model):
    _name = 'bir.1702q'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BIR Form 1702Q - Quarterly Income Tax Return'
    _order = 'year desc, quarter desc, id desc'

    # ==================== Header Information ====================
    name = fields.Char(string='Reference', required=True, copy=False,
                      default='New', readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                required=True, default=lambda self: self.env.company)
    year = fields.Integer(string='Year', required=True,
                         default=lambda self: fields.Date.today().year)
    quarter = fields.Selection([
        ('1', '1st Quarter'),
        ('2', '2nd Quarter'),
        ('3', '3rd Quarter'),
    ], string='Quarter', required=True, default='1')

    fiscal_year = fields.Boolean(string='Fiscal Year', default=False)
    year_ended = fields.Char(string='Year Ended (MM/YYYY)', compute='_compute_year_ended', store=True)
    is_amended = fields.Boolean(string='Amended Return', default=False)

    # ==================== Tax Codes ====================
    atc_code = fields.Selection([
        ('IC010', 'IC 010 - Domestic Corporation (In General)'),
        ('IC055', 'IC 055 - Minimum Corporate Income Tax (MCIT)'),
        ('IC011', 'IC 011 - Proprietary Educational Institutions'),
        ('IC031', 'IC 031 - Non-Stock, Non-Profit Hospitals'),
        ('IC040', 'IC 040 - GOCC, Agencies & Instrumentalities'),
        ('IC041', 'IC 041 - National Gov\'t & LGU\'s'),
        ('IC020', 'IC 020 - Taxable Partnership'),
        ('IC070', 'IC 070 - Resident Foreign Corporation (In General)'),
        ('IC080', 'IC 080 - International Carriers'),
        ('IC101', 'IC 101 - Regional Operating Headquarters'),
    ], string='Alphanumeric Tax Code', default='IC055', required=True)

    # ==================== Company Details ====================
    tin = fields.Char(string='TIN', related='company_id.vat', readonly=True)
    rdo_code = fields.Char(string='RDO Code', size=3)
    registered_name = fields.Char(string='Registered Name',
                                 related='company_id.name', readonly=True)
    registered_address = fields.Text(string='Registered Address',
                                    compute='_compute_registered_address', store=True)
    zip_code = fields.Char(string='ZIP Code', related='company_id.zip', readonly=True)
    contact_number = fields.Char(string='Contact Number', related='company_id.phone', readonly=True)
    email = fields.Char(string='Email Address', related='company_id.email', readonly=True)

    # ==================== Method of Deductions ====================
    deduction_method = fields.Selection([
        ('itemized', 'Itemized Deductions'),
        ('osd', 'Optional Standard Deduction (40% of Gross Income)'),
    ], string='Method of Deductions', default='itemized', required=True)

    # ==================== Tax Relief ====================
    has_tax_relief = fields.Boolean(string='Tax Relief under Special Law/Treaty')
    tax_relief_specify = fields.Char(string='Specify Tax Relief')

    # ==================== Date Range ====================
    date_from = fields.Date(string='Date From', compute='_compute_date_range', store=True)
    date_to = fields.Date(string='Date To', compute='_compute_date_range', store=True)

    # ==================== Schedule 1 - EXEMPT Income ====================
    s1_exempt_sales = fields.Monetary(string='Sales/Receipts (Exempt)', currency_field='currency_id')
    s1_exempt_cost = fields.Monetary(string='Cost of Sales (Exempt)', currency_field='currency_id')
    s1_exempt_gross_income = fields.Monetary(string='Gross Income (Exempt)',
                                            compute='_compute_schedule1', store=True)
    s1_exempt_other_income = fields.Monetary(string='Other Income (Exempt)', currency_field='currency_id')
    s1_exempt_total_gross = fields.Monetary(string='Total Gross Income (Exempt)',
                                           compute='_compute_schedule1', store=True)
    s1_exempt_deductions = fields.Monetary(string='Deductions (Exempt)', currency_field='currency_id')
    s1_exempt_taxable_income = fields.Monetary(string='Taxable Income (Exempt)',
                                              compute='_compute_schedule1', store=True)
    s1_exempt_previous_quarters = fields.Monetary(string='Previous Quarters (Exempt)',
                                                 currency_field='currency_id')
    s1_exempt_total_taxable = fields.Monetary(string='Total Taxable to Date (Exempt)',
                                             compute='_compute_schedule1', store=True)
    s1_exempt_tax_rate = fields.Float(string='Tax Rate (Exempt) %', default=0.0)
    s1_exempt_tax_due = fields.Monetary(string='Tax Due (Exempt)',
                                       compute='_compute_schedule1', store=True)
    s1_exempt_share_agencies = fields.Monetary(string='Share of Agencies (Exempt)',
                                              currency_field='currency_id')
    s1_exempt_net_tax = fields.Monetary(string='Net Tax Due (Exempt)',
                                       compute='_compute_schedule1', store=True)

    # ==================== Schedule 1 - SPECIAL Rate Income ====================
    s1_special_sales = fields.Monetary(string='Sales/Receipts (Special)',
                                      currency_field='currency_id')
    s1_special_cost = fields.Monetary(string='Cost of Sales (Special)', currency_field='currency_id')
    s1_special_gross_income = fields.Monetary(string='Gross Income (Special)',
                                             compute='_compute_schedule1', store=True)
    s1_special_other_income = fields.Monetary(string='Other Income (Special)',
                                             currency_field='currency_id')
    s1_special_total_gross = fields.Monetary(string='Total Gross Income (Special)',
                                            compute='_compute_schedule1', store=True)
    s1_special_deductions = fields.Monetary(string='Deductions (Special)', currency_field='currency_id')
    s1_special_taxable_income = fields.Monetary(string='Taxable Income (Special)',
                                               compute='_compute_schedule1', store=True)
    s1_special_previous_quarters = fields.Monetary(string='Previous Quarters (Special)',
                                                  currency_field='currency_id')
    s1_special_total_taxable = fields.Monetary(string='Total Taxable to Date (Special)',
                                              compute='_compute_schedule1', store=True)
    s1_special_tax_rate = fields.Float(string='Tax Rate (Special) %', default=0.0)
    s1_special_tax_due = fields.Monetary(string='Tax Due (Special)',
                                        compute='_compute_schedule1', store=True)
    s1_special_share_agencies = fields.Monetary(string='Share of Agencies (Special)',
                                               currency_field='currency_id')
    s1_special_net_tax = fields.Monetary(string='Net Tax Due (Special)',
                                        compute='_compute_schedule1', store=True)

    # ==================== Schedule 2 - REGULAR/NORMAL RATE ====================
    s2_sales = fields.Monetary(string='Sales/Receipts', compute='_compute_schedule2',
                              store=True, currency_field='currency_id')
    s2_cost = fields.Monetary(string='Cost of Sales', compute='_compute_schedule2',
                             store=True, currency_field='currency_id')
    s2_gross_income = fields.Monetary(string='Gross Income from Operation',
                                     compute='_compute_schedule2', store=True)
    s2_other_income = fields.Monetary(string='Non-Operating Income',
                                     compute='_compute_schedule2', store=True)
    s2_total_gross = fields.Monetary(string='Total Gross Income',
                                    compute='_compute_schedule2', store=True)
    s2_deductions = fields.Monetary(string='Deductions', compute='_compute_schedule2',
                                   store=True)
    s2_taxable_income = fields.Monetary(string='Taxable Income this Quarter',
                                       compute='_compute_schedule2', store=True)
    s2_previous_quarters = fields.Monetary(string='Taxable Income Previous Quarters',
                                          compute='_compute_schedule2', store=True)
    s2_total_taxable = fields.Monetary(string='Total Taxable Income to Date',
                                      compute='_compute_schedule2', store=True)
    s2_tax_rate = fields.Float(string='Applicable Tax Rate %', default=30.0)
    s2_normal_tax = fields.Monetary(string='Normal Income Tax',
                                   compute='_compute_schedule2', store=True)
    s2_mcit = fields.Monetary(string='MCIT', compute='_compute_schedule3', store=True)
    s2_tax_due = fields.Monetary(string='Income Tax Due', compute='_compute_schedule2',
                                store=True)

    # ==================== Schedule 3 - MCIT Computation ====================
    s3_gross_q1 = fields.Monetary(string='Gross Income Q1', compute='_compute_schedule3',
                                 store=True)
    s3_gross_q2 = fields.Monetary(string='Gross Income Q2', compute='_compute_schedule3',
                                 store=True)
    s3_gross_q3 = fields.Monetary(string='Gross Income Q3', compute='_compute_schedule3',
                                 store=True)
    s3_total_gross = fields.Monetary(string='Total Gross Income', compute='_compute_schedule3',
                                    store=True)
    s3_mcit_rate = fields.Float(string='MCIT Rate %', default=2.0, readonly=True)
    s3_mcit = fields.Monetary(string='MCIT Amount', compute='_compute_schedule3', store=True)

    # ==================== Schedule 4 - Tax Credits/Payments ====================
    s4_prior_year_excess = fields.Monetary(string='Prior Year Excess Credits',
                                          currency_field='currency_id')
    s4_previous_quarters_payment = fields.Monetary(string='Previous Quarters Payment',
                                                  currency_field='currency_id')
    s4_previous_mcit = fields.Monetary(string='Previous MCIT Payments',
                                      currency_field='currency_id')
    s4_previous_creditable = fields.Monetary(string='Previous Creditable Tax Withheld',
                                            currency_field='currency_id')
    s4_current_creditable = fields.Monetary(string='Current Quarter Creditable (2307)',
                                           currency_field='currency_id')
    s4_amended_tax_paid = fields.Monetary(string='Tax Paid in Amended Return',
                                         currency_field='currency_id')
    s4_other_credits = fields.Monetary(string='Other Tax Credits', currency_field='currency_id')
    s4_total_credits = fields.Monetary(string='Total Tax Credits',
                                      compute='_compute_schedule4', store=True)

    # ==================== Part II - Total Tax Payable ====================
    tax_due_normal = fields.Monetary(string='Income Tax Due - Normal Rate',
                                    compute='_compute_tax_payable', store=True)
    unexpired_excess_mcit = fields.Monetary(string='Unexpired Excess MCIT',
                                           currency_field='currency_id')
    balance_tax_normal = fields.Monetary(string='Balance Tax Due - Normal',
                                        compute='_compute_tax_payable', store=True)
    tax_due_special = fields.Monetary(string='Income Tax Due - Special Rate',
                                     compute='_compute_tax_payable', store=True)
    aggregate_tax_due = fields.Monetary(string='Aggregate Income Tax Due',
                                       compute='_compute_tax_payable', store=True)
    total_tax_credits = fields.Monetary(string='Total Tax Credits',
                                       compute='_compute_tax_payable', store=True)
    net_tax_payable = fields.Monetary(string='Net Tax Payable/(Overpayment)',
                                     compute='_compute_tax_payable', store=True)

    # ==================== Penalties ====================
    surcharge = fields.Monetary(string='Surcharge', currency_field='currency_id')
    interest = fields.Monetary(string='Interest', currency_field='currency_id')
    compromise = fields.Monetary(string='Compromise', currency_field='currency_id')
    total_penalties = fields.Monetary(string='Total Penalties',
                                     compute='_compute_tax_payable', store=True)
    total_amount_payable = fields.Monetary(string='Total Amount Payable',
                                          compute='_compute_tax_payable', store=True)

    # ==================== Payment Details ====================
    payment_method = fields.Selection([
        ('cash', 'Cash/Bank Debit Memo'),
        ('check', 'Check'),
        ('tax_debit', 'Tax Debit Memo'),
        ('other', 'Others'),
    ], string='Payment Method')
    payment_bank = fields.Char(string='Drawee Bank/Agency')
    payment_number = fields.Char(string='Payment Number')
    payment_date = fields.Date(string='Payment Date')
    payment_amount = fields.Monetary(string='Payment Amount', currency_field='currency_id')

    # ==================== Attachments ====================
    attachment_count = fields.Integer(string='Number of Attachments', default=0)

    # ==================== Status ====================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('filed', 'Filed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    currency_id = fields.Many2one('res.currency', string='Currency',
                                 related='company_id.currency_id', readonly=True)

    # ==================== METHODS ====================

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('bir.1702q') or 'New'
        return super(Bir1702Q, self).create(vals)

    @api.depends('year', 'quarter')
    def _compute_year_ended(self):
        for record in self:
            if record.fiscal_year:
                record.year_ended = ''
            else:
                quarter_month = int(record.quarter) * 3
                record.year_ended = f"{quarter_month:02d}/{record.year}"

    @api.depends('company_id')
    def _compute_registered_address(self):
        for record in self:
            company = record.company_id
            address_parts = []
            if company.street:
                address_parts.append(company.street)
            if company.street2:
                address_parts.append(company.street2)
            if company.city:
                address_parts.append(company.city)
            if company.state_id:
                address_parts.append(company.state_id.name)
            if company.country_id:
                address_parts.append(company.country_id.name)
            record.registered_address = ', '.join(address_parts)

    @api.depends('year', 'quarter')
    def _compute_date_range(self):
        for record in self:
            if record.year and record.quarter:
                quarter_num = int(record.quarter)
                start_month = (quarter_num - 1) * 3 + 1
                end_month = quarter_num * 3

                record.date_from = date(record.year, start_month, 1)
                if end_month == 12:
                    record.date_to = date(record.year, 12, 31)
                else:
                    next_month = date(record.year, end_month + 1, 1)
                    record.date_to = next_month - relativedelta(days=1)

    @api.depends('s1_exempt_sales', 's1_exempt_cost', 's1_exempt_other_income',
                 's1_exempt_deductions', 's1_exempt_previous_quarters', 's1_exempt_tax_rate',
                 's1_exempt_share_agencies', 's1_special_sales', 's1_special_cost',
                 's1_special_other_income', 's1_special_deductions', 's1_special_previous_quarters',
                 's1_special_tax_rate', 's1_special_share_agencies')
    def _compute_schedule1(self):
        for record in self:
            # Exempt calculations
            record.s1_exempt_gross_income = record.s1_exempt_sales - record.s1_exempt_cost
            record.s1_exempt_total_gross = record.s1_exempt_gross_income + record.s1_exempt_other_income
            record.s1_exempt_taxable_income = record.s1_exempt_total_gross - record.s1_exempt_deductions
            record.s1_exempt_total_taxable = record.s1_exempt_taxable_income + record.s1_exempt_previous_quarters
            record.s1_exempt_tax_due = record.s1_exempt_total_taxable * (record.s1_exempt_tax_rate / 100)
            record.s1_exempt_net_tax = record.s1_exempt_tax_due - record.s1_exempt_share_agencies

            # Special calculations
            record.s1_special_gross_income = record.s1_special_sales - record.s1_special_cost
            record.s1_special_total_gross = record.s1_special_gross_income + record.s1_special_other_income
            record.s1_special_taxable_income = record.s1_special_total_gross - record.s1_special_deductions
            record.s1_special_total_taxable = record.s1_special_taxable_income + record.s1_special_previous_quarters
            record.s1_special_tax_due = record.s1_special_total_taxable * (record.s1_special_tax_rate / 100)
            record.s1_special_net_tax = record.s1_special_tax_due - record.s1_special_share_agencies

    @api.depends('company_id', 'date_from', 'date_to', 'deduction_method', 's2_tax_rate', 'quarter')
    def _compute_schedule2(self):
        for record in self:
            if not record.date_from or not record.date_to:
                continue

            # 1. Revenue — income accounts have credit-normal balance.
            #    Sum credits - debits (i.e. use -balance since income balance is negative in Odoo).
            record.s2_sales = record._get_credit_balance(
                ['income', 'income_other'], record.date_from, record.date_to, record.company_id.id
            )

            # 2. COGS — expense accounts have debit-normal balance.
            #    Sum debits only (positive balance = cost incurred).
            record.s2_cost = record._get_debit_balance(
                ['expense'], record.date_from, record.date_to, record.company_id.id
            )

            # 3. Gross income from operations (floor at 0 per BIR rules)
            record.s2_gross_income = max(0.0, record.s2_sales - record.s2_cost)

            # 4. Other/non-operating income (income_other accounts, credit-normal)
            record.s2_other_income = record._get_credit_balance(
                ['income_other'], record.date_from, record.date_to, record.company_id.id
            )

            # 5. Total gross income
            record.s2_total_gross = record.s2_gross_income + record.s2_other_income

            # 6. Deductions
            if record.deduction_method == 'osd':
                # OSD = 40% of Gross Income per NIRC Sec. 34(L)
                record.s2_deductions = record.s2_total_gross * 0.40
            else:
                # Itemized — operating expenses (debit-normal, exclude COGS)
                record.s2_deductions = record._get_debit_balance(
                    ['expense'], record.date_from, record.date_to, record.company_id.id
                )

            # 7. Taxable income this quarter (floor at 0)
            record.s2_taxable_income = max(0.0, record.s2_total_gross - record.s2_deductions)

            # 8. Cumulative from prior quarters
            record.s2_previous_quarters = record._get_previous_quarters_taxable_income()
            record.s2_total_taxable = record.s2_taxable_income + record.s2_previous_quarters

            # 9. Normal income tax
            record.s2_normal_tax = record.s2_total_taxable * (record.s2_tax_rate / 100)

            # 10. Tax due = higher of normal tax or MCIT (NIRC Sec. 27(E))
            record.s2_tax_due = max(record.s2_normal_tax, record.s2_mcit)

    @api.depends('s2_total_gross', 'quarter')
    def _compute_schedule3(self):
        for record in self:
            if record.quarter == '1':
                record.s3_gross_q1 = record.s2_total_gross
                record.s3_gross_q2 = 0
                record.s3_gross_q3 = 0
            elif record.quarter == '2':
                record.s3_gross_q1 = record._get_previous_quarter_gross_income('1')
                record.s3_gross_q2 = record.s2_total_gross
                record.s3_gross_q3 = 0
            elif record.quarter == '3':
                record.s3_gross_q1 = record._get_previous_quarter_gross_income('1')
                record.s3_gross_q2 = record._get_previous_quarter_gross_income('2')
                record.s3_gross_q3 = record.s2_total_gross

            record.s3_total_gross = record.s3_gross_q1 + record.s3_gross_q2 + record.s3_gross_q3
            record.s3_mcit = record.s3_total_gross * (record.s3_mcit_rate / 100)
            record.s2_mcit = record.s3_mcit

    @api.depends('s4_prior_year_excess', 's4_previous_quarters_payment', 's4_previous_mcit',
                 's4_previous_creditable', 's4_current_creditable', 's4_amended_tax_paid',
                 's4_other_credits')
    def _compute_schedule4(self):
        for record in self:
            record.s4_total_credits = (
                record.s4_prior_year_excess +
                record.s4_previous_quarters_payment +
                record.s4_previous_mcit +
                record.s4_previous_creditable +
                record.s4_current_creditable +
                record.s4_amended_tax_paid +
                record.s4_other_credits
            )

    @api.depends('s2_tax_due', 'unexpired_excess_mcit', 's1_special_net_tax', 's4_total_credits',
                 'surcharge', 'interest', 'compromise')
    def _compute_tax_payable(self):
        for record in self:
            record.tax_due_normal = record.s2_tax_due
            record.balance_tax_normal = record.tax_due_normal - record.unexpired_excess_mcit
            record.tax_due_special = record.s1_special_net_tax
            record.aggregate_tax_due = record.balance_tax_normal + record.tax_due_special
            record.total_tax_credits = record.s4_total_credits
            record.net_tax_payable = record.aggregate_tax_due - record.total_tax_credits
            record.total_penalties = record.surcharge + record.interest + record.compromise
            record.total_amount_payable = record.net_tax_payable + record.total_penalties

    # ==================== ACCOUNT BALANCE HELPERS ====================

    def _get_credit_balance(self, account_types, date_from, date_to, company_id):
        """
        Return the NET CREDIT amount for income-type accounts.
        Income accounts are credit-normal in double-entry accounting:
          credit > debit  → positive income (normal)
          debit > credit  → negative income (reversal/refund)

        We sum (credit - debit) per line = sum of -balance (since income
        balance is stored as negative in Odoo's sign convention).
        This gives a positive number representing total income earned.

        Only pulls POSTED move lines — draft entries are excluded.
        """
        type_mapping = {
            'income':       ['income'],
            'income_other': ['income_other'],
        }
        domain_types = []
        for atype in account_types:
            domain_types.extend(type_mapping.get(atype, [atype]))
        domain_types = list(set(domain_types))

        lines = self.env['account.move.line'].search([
            ('account_id.account_type', 'in', domain_types),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company_id),
            ('credit', '>', 0),          # credit-only: actual income postings
        ])
        # sum(credit - debit) = net income in natural positive form
        return sum(lines.mapped(lambda l: l.credit - l.debit))

    def _get_debit_balance(self, account_types, date_from, date_to, company_id):
        """
        Return the NET DEBIT amount for expense/COGS-type accounts.
        Expense accounts are debit-normal in double-entry accounting:
          debit > credit  → positive cost (normal)
          credit > debit  → negative cost (reversal/vendor credit note)

        We sum (debit - credit) per line to get net cost incurred.
        Only pulls POSTED move lines.
        """
        type_mapping = {
            'expense': ['expense'],
            'cogs':    ['expense'],
        }
        domain_types = []
        for atype in account_types:
            domain_types.extend(type_mapping.get(atype, [atype]))
        domain_types = list(set(domain_types))

        lines = self.env['account.move.line'].search([
            ('account_id.account_type', 'in', domain_types),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company_id),
            ('debit', '>', 0),           # debit-only: actual expense postings
        ])
        # sum(debit - credit) = net cost in natural positive form
        return sum(lines.mapped(lambda l: l.debit - l.credit))

    def _get_previous_quarters_taxable_income(self):
        """Sum of taxable income from confirmed/filed previous quarters in the same year."""
        self.ensure_one()
        if self.quarter == '1':
            return 0.0

        previous_quarters = {'2': ['1'], '3': ['1', '2']}.get(self.quarter, [])
        records = self.search([
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('quarter', 'in', previous_quarters),
            ('state', 'not in', ('cancelled', 'draft')),
            ('id', '!=', self.id),
        ])
        return sum(records.mapped('s2_taxable_income'))

    def _get_previous_quarter_gross_income(self, quarter):
        """Get total gross income from a specific confirmed/filed previous quarter."""
        self.ensure_one()
        record = self.search([
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('quarter', '=', quarter),
            ('state', 'not in', ('cancelled', 'draft')),
            ('id', '!=', self.id),
        ], limit=1)
        return record.s2_total_gross if record else 0.0

    # ==================== ACTION METHODS ====================

    def action_generate_data(self):
        """Trigger recomputation of all schedules from posted journal entries."""
        self.ensure_one()
        self._compute_schedule2()
        self._compute_schedule3()
        self._compute_schedule4()
        self._compute_tax_payable()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Data has been generated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_confirm(self):
        self.ensure_one()
        self.write({'state': 'confirmed'})

    def action_file(self):
        self.ensure_one()
        self.write({'state': 'filed'})

    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('bir_1702q_report.action_report_bir_1702q').report_action(self)