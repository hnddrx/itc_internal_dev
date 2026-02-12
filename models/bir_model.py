from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import base64

class BIRModel(models.Model):
    _name = "bir.model"
    _description = "BIR Forms"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    category = fields.Selection([
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
    ], string="Category")
    image_url = fields.Char(string="Image URL")
    action_id = fields.Many2one('ir.actions.act_window', string="Action")

    def open_action(self):
        self.ensure_one()

        if self.action_id:
            return self.action_id.read()[0]

        return False

# ==============================
# BIR 0619E Main Model
class Bir0619E(models.Model):
    _name = "bir.0619e"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "BIR 0619E Monthly Remittance"
    
    

    name = fields.Char(
        default="New",
        readonly=True,
        copy=False
    )

    month = fields.Date(required=True)
    due_date = fields.Date(readonly=True)

    # Company Auto Info
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company
    )

    tin = fields.Char(readonly=True)
    rdo_code = fields.Char(readonly=True)
    taxpayer_name = fields.Char(readonly=True)
    address = fields.Text(readonly=True)
    zip_code = fields.Char(readonly=True)
    email = fields.Char(readonly=True)

    # Tax Codes
    atc = fields.Char(default="WME10", readonly=True)
    tax_type_code = fields.Char(default="WE", readonly=True)

    # Computed Amounts
    amount_remittance = fields.Float(readonly=True)
    net_remittance = fields.Float(readonly=True)
    surcharge = fields.Float(readonly=True)
    interest = fields.Float(readonly=True)
    compromise = fields.Float(readonly=True)
    total_penalties = fields.Float(readonly=True)
    total_amount = fields.Float(readonly=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("generated", "Generated"),
        ("locked", "Locked"),
    ], default="draft")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            seq = self.env['ir.sequence'].next_by_code('bir.0619e') or 'New'
            vals['name'] = seq
        return super(Bir0619E, self).create(vals)

    # ==============================
    # 🔥 ONE CLICK GENERATION
    # ==============================
    def action_generate_0619e(self):
        for rec in self:
            company = rec.company_id

            # 1️⃣ Auto Company Info
            rec.tin = company.vat
            rec.taxpayer_name = company.name
            rec.address = company.street or ""
            rec.zip_code = company.zip or ""
            rec.email = company.email or ""

            # 2️⃣ Compute Due Date (10th of next month)
            if rec.month:
                year = rec.month.year
                month = rec.month.month + 1
                if month == 13:
                    month = 1
                    year += 1
                rec.due_date = date(year, month, 10)

            # 3️⃣ Get Withholding Tax from Vendor Bills
            start_date = rec.month.replace(day=1)
            end_date = rec.month.replace(day=28)

            moves = self.env["account.move"].search([
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start_date),
                ("invoice_date", "<=", end_date),
                ("company_id", "=", rec.company_id.id),
            ])

            total_withholding = 0.0

            for move in moves:
                for line in move.line_ids:
                    if line.tax_line_id:
                        if "WC100" in line.tax_line_id.name:
                            rec.name = line.move_id.name    
                            total_withholding += abs(line.balance)

            rec.amount_remittance = total_withholding
            rec.net_remittance = total_withholding

            # 4️⃣ Auto Penalty (if late)
            today = fields.Date.today()
            if rec.due_date and today > rec.due_date:
                rec.surcharge = rec.net_remittance * 0.25
                rec.interest = rec.net_remittance * 0.12 / 12
                rec.compromise = 1000
            else:
                rec.surcharge = 0
                rec.interest = 0
                rec.compromise = 0

            rec.total_penalties = (
                rec.surcharge +
                rec.interest +
                rec.compromise
            )

            rec.total_amount = (
                rec.net_remittance +
                rec.total_penalties
            )

            rec.state = "generated"


    def action_generate_report_chatter(self):
        self.ensure_one()

        # Get the report
        report = self.env.ref('itc_internal_dev.action_report_custom_bir_0619e')
        if not report:
            raise ValueError("Report not found")

        # Render PDF
        pdf_content = self.env['ir.actions.report']._render_qweb_pdf(report.id, [self.id])[0]

        # Delete previous attachments for this record with the same name
        previous_attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'bir.0619e'),
            ('res_id', '=', self.id),
            ('name', '=', 'BIR_0619e.pdf')
        ])
        if previous_attachments:
            previous_attachments.unlink()

        # Create new attachment
        attachment = self.env['ir.attachment'].create({
            'name': 'BIR_0619e.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'bir.0619e',
            'res_id': self.id,
            'mimetype': 'application/pdf',
            'store_fname': 'BIR_0619e.pdf',
        })

        # Post in chatter
        self.with_context(
            mail_notify_force_send=False,
            mail_auto_subscribe_no_notify=True
        ).message_post(
            body="BIR 0619E report generated.",
            message_type="comment",
            subtype_xmlid="mail.mt_log",
            attachment_ids=[attachment.id],
        )


# -*- coding: utf-8 -*-
# BIR Form 1702Q Model for Odoo 18
# File: models/bir_1702q.py




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
                # Get last day of the end month
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
            
            # 1. Get revenue (Income is usually stored as negative in Odoo)
            revenue = self._get_account_balance(['income'], record.date_from, record.date_to, record.company_id.id)
            record.s2_sales = abs(revenue)
            
            # 2. Get COGS (Expenses are usually positive in Odoo)
            cogs = self._get_account_balance(['cogs'], record.date_from, record.date_to, record.company_id.id)
            record.s2_cost = abs(cogs)
            
            # 3. Gross income (Sales - Cost) 
            # For tax purposes, if Cost > Sales, Gross Income is reported as 0.00
            gross_op = record.s2_sales - record.s2_cost
            record.s2_gross_income = max(0, gross_op) 
            
            # 4. Other income
            other_income = self._get_account_balance(['other_income'], record.date_from, record.date_to, record.company_id.id)
            record.s2_other_income = abs(other_income)
            
            # 5. Total gross income (Sum of Items 18 & 19 on Form 1702Q)
            record.s2_total_gross = record.s2_gross_income + record.s2_other_income
            
            # 6. Deductions
            if record.deduction_method == 'osd':
                # OSD is 40% of Gross Income
                record.s2_deductions = record.s2_total_gross * 0.40
            else:
                expenses = self._get_account_balance(['expense'], record.date_from, record.date_to, record.company_id.id)
                record.s2_deductions = abs(expenses)
            
            # 7. Taxable income this quarter
            # If Deductions > Total Gross, result must be 0, not negative
            taxable_this_q = record.s2_total_gross - record.s2_deductions
            record.s2_taxable_income = max(0, taxable_this_q)
            
            # 8. Previous quarters and Total taxable to date
            record.s2_previous_quarters = record._get_previous_quarters_taxable_income()
            record.s2_total_taxable = record.s2_taxable_income + record.s2_previous_quarters
            
            # 9. Normal tax
            record.s2_normal_tax = record.s2_total_taxable * (record.s2_tax_rate / 100)
            
            # 10. Final Tax due (higher of normal tax or MCIT)
            record.s2_tax_due = max(record.s2_normal_tax, record.s2_mcit)
    
    @api.depends('s2_total_gross', 'quarter')
    def _compute_schedule3(self):
        for record in self:
            # Calculate gross income for each quarter
            if record.quarter == '1':
                record.s3_gross_q1 = record.s2_total_gross
                record.s3_gross_q2 = 0
                record.s3_gross_q3 = 0
            elif record.quarter == '2':
                prev_q1 = record._get_previous_quarter_gross_income('1')
                record.s3_gross_q1 = prev_q1
                record.s3_gross_q2 = record.s2_total_gross
                record.s3_gross_q3 = 0
            elif record.quarter == '3':
                prev_q1 = record._get_previous_quarter_gross_income('1')
                prev_q2 = record._get_previous_quarter_gross_income('2')
                record.s3_gross_q1 = prev_q1
                record.s3_gross_q2 = prev_q2
                record.s3_gross_q3 = record.s2_total_gross
            
            # Total gross income
            record.s3_total_gross = record.s3_gross_q1 + record.s3_gross_q2 + record.s3_gross_q3
            
            # MCIT calculation
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
            # Income tax due - normal rate
            record.tax_due_normal = record.s2_tax_due
            
            # Balance after unexpired excess MCIT
            record.balance_tax_normal = record.tax_due_normal - record.unexpired_excess_mcit
            
            # Income tax due - special rate
            record.tax_due_special = record.s1_special_net_tax
            
            # Aggregate tax due
            record.aggregate_tax_due = record.balance_tax_normal + record.tax_due_special
            
            # Total tax credits
            record.total_tax_credits = record.s4_total_credits
            
            # Net tax payable
            record.net_tax_payable = record.aggregate_tax_due - record.total_tax_credits
            
            # Total penalties
            record.total_penalties = record.surcharge + record.interest + record.compromise
            
            # Total amount payable
            record.total_amount_payable = record.net_tax_payable + record.total_penalties
    
    def _get_account_balance(self, account_types, date_from, date_to, company_id):
        """Get account balance for specific account types within date range"""

        move_line_obj = self.env['account.move.line']

        # Map account types
        type_mapping = {
            'income': ['income', 'income_other'],
            'cogs': ['expense'],
            'other_income': ['income_other'],
            'expense': ['expense'],
        }

        domain_types = []
        for atype in account_types:
            domain_types.extend(type_mapping.get(atype, []))

        domain = [
            ('account_id.account_type', 'in', domain_types),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company_id),
        ]

        move_lines = move_line_obj.search(domain)

        return sum(move_lines.mapped('balance'))

    
    def _get_previous_quarters_taxable_income(self):
        """Get sum of taxable income from previous quarters in the same year"""
        self.ensure_one()
        
        if self.quarter == '1':
            return 0.0
        
        previous_quarters = []
        if self.quarter == '2':
            previous_quarters = ['1']
        elif self.quarter == '3':
            previous_quarters = ['1', '2']
        
        domain = [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('quarter', 'in', previous_quarters),
            ('state', '!=', 'cancelled'),
            ('id', '!=', self.id),
        ]
        
        previous_records = self.search(domain)
        return sum(previous_records.mapped('s2_taxable_income'))
    
    def _get_previous_quarter_gross_income(self, quarter):
        """Get gross income from a specific previous quarter"""
        self.ensure_one()
        
        domain = [
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('quarter', '=', quarter),
            ('state', '!=', 'cancelled'),
            ('id', '!=', self.id),
        ]
        
        previous_record = self.search(domain, limit=1)
        return previous_record.s2_total_gross if previous_record else 0.0
    
    # ==================== ACTION METHODS ====================
    
    def action_generate_data(self):
        """Generate/Regenerate data from accounting records"""
        self.ensure_one()
        # Trigger recomputation
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
        """Confirm the return"""
        self.ensure_one()
        self.write({'state': 'confirmed'})
    
    def action_file(self):
        """Mark as filed"""
        self.ensure_one()
        self.write({'state': 'filed'})
    
    def action_cancel(self):
        """Cancel the return"""
        self.ensure_one()
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        """Reset to draft"""
        self.ensure_one()
        self.write({'state': 'draft'})
    
    def action_print_report(self):
        """Print BIR 1702Q Report"""
        self.ensure_one()
        return self.env.ref('bir_1702q_report.action_report_bir_1702q').report_action(self)


# BIT 2550q model would be similar in structure but with fields and computations specific to that form.
class Bir2550Q(models.Model):
    _name = 'bir.2550q'
    _description = 'Quarterly Value-Added Tax (VAT) Return'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Part I - Background Information
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    year_ended = fields.Char(string='Fiscal Year Ended (MM/YYYY)', required=True)
    quarter = fields.Selection([('1', '1st'), ('2', '2nd'), ('3', '3rd'), ('4', '4th')], string='Quarter', required=True)
    return_period_from = fields.Date(string='Return Period From', readonly=True)
    return_period_to = fields.Date(string='Return Period To', readonly=True)
    is_amended = fields.Boolean(string='Amended Return?')
    is_short_period = fields.Boolean(string='Short Period Return?')
    taxpayer_classification = fields.Selection([
        ('micro', 'Micro'), ('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')
    ], string='Taxpayer Classification')

    # Part IV - VAT Computation
    vatable_sales = fields.Monetary(string='31A VATable Sales', readonly=True)
    output_tax_31b = fields.Monetary(string='31B Output Tax', readonly=True)
    zero_rated_sales = fields.Monetary(string='32 Zero-Rated Sales', readonly=True)
    exempt_sales = fields.Monetary(string='33 Exempt Sales', readonly=True)
    total_adjusted_output_tax = fields.Monetary(string='37 Total Adjusted Output Tax Due', readonly=True)

    input_tax_carried_over = fields.Monetary(string='38 Input Tax Carried Over')
    transitional_input_tax = fields.Monetary(string='40 Transitional Input Tax')
    presumptive_input_tax = fields.Monetary(string='41 Presumptive Input Tax')
    total_current_purchases = fields.Monetary(string='50A Total Current Purchases', readonly=True)
    total_current_input_tax = fields.Monetary(string='50B Total Current Input Tax', readonly=True)
    total_available_input_tax = fields.Monetary(string='51 Total Available Input Tax', readonly=True)
    total_allowable_input_tax = fields.Monetary(string='60 Total Allowable Input Tax', readonly=True)

    # Part III - Tax Credits & Adjustments
    creditable_vat_withheld = fields.Monetary(string='16 Creditable VAT Withheld')
    advance_vat_payments = fields.Monetary(string='17 Advance VAT Payments')
    total_penalties = fields.Monetary(string='25 Total Penalties')

    # Part II - Tax Payable
    net_vat_payable = fields.Monetary(string='15 Net VAT Payable', readonly=True)
    total_amount_payable = fields.Monetary(string='26 TOTAL AMOUNT PAYABLE', readonly=True)

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    # ==================== Status ====================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('filed', 'Filed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # ==================== Sequence ====================
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('bir.2550q') or 'New'
        return super(Bir2550Q, self).create(vals)

    # ==================== Quarter Dates ====================
    @api.onchange('quarter', 'year_ended')
    def _onchange_quarter_year(self):
        for record in self:
            if record.year_ended and record.quarter:
                try:
                    year = int(record.year_ended.split('/')[-1])
                except ValueError:
                    year = fields.Date.today().year
                quarters = {
                    '1': (f'{year}-01-01', f'{year}-03-31'),
                    '2': (f'{year}-04-01', f'{year}-06-30'),
                    '3': (f'{year}-07-01', f'{year}-09-30'),
                    '4': (f'{year}-10-01', f'{year}-12-31'),
                }
                date_from, date_to = quarters.get(record.quarter, (False, False))
                record.return_period_from = date_from
                record.return_period_to = date_to

    # ==================== Data Computation ====================
    def action_generate_data(self):
        for record in self:
            if not record.return_period_from or not record.return_period_to:
                record._onchange_quarter_year()

            domain = [
                ('company_id', '=', record.company_id.id),
                ('date', '>=', record.return_period_from),
                ('date', '<=', record.return_period_to),
                ('parent_state', '=', 'posted')
            ]

            # Output VAT
            sales_lines = self.env['account.move.line'].search(domain + [
                ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                ('tax_ids', '!=', False)
            ])
            vatable_sales = output_tax = zero_rated = exempt = 0.0
            for line in sales_lines:
                for tax in line.tax_ids:
                    if tax.amount > 0:
                        vatable_sales += line.price_subtotal
                        output_tax += line.price_subtotal * (tax.amount / 100)
                    elif tax.amount == 0 and tax.tax_group_id.name == 'Zero-Rated':
                        zero_rated += line.price_subtotal
                    elif tax.amount == 0 and tax.tax_group_id.name == 'Exempt':
                        exempt += line.price_subtotal

            # Input VAT
            purchase_lines = self.env['account.move.line'].search(domain + [
                ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
                ('tax_ids', '!=', False)
            ])
            total_purchases = total_input_tax = 0.0
            for line in purchase_lines:
                total_purchases += line.price_subtotal
                for tax in line.tax_ids:
                    total_input_tax += line.price_subtotal * (tax.amount / 100)

            total_available_input_tax = (record.input_tax_carried_over or 0.0) + total_input_tax
            net_vat = output_tax - total_available_input_tax
            total_payable = net_vat - (record.creditable_vat_withheld or 0.0) - (record.advance_vat_payments or 0.0) + (record.total_penalties or 0.0)

            record.write({
                'vatable_sales': vatable_sales,
                'output_tax_31b': output_tax,
                'zero_rated_sales': zero_rated,
                'exempt_sales': exempt,
                'total_adjusted_output_tax': output_tax,
                'total_current_purchases': total_purchases,
                'total_current_input_tax': total_input_tax,
                'total_available_input_tax': total_available_input_tax,
                'total_allowable_input_tax': total_available_input_tax,
                'net_vat_payable': net_vat,
                'total_amount_payable': total_payable
            })

    # ==================== Workflow Methods ====================
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_file(self):
        self.write({'state': 'filed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_set_draft(self):
        self.write({'state': 'draft'})
