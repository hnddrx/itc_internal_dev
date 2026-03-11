from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import base64
import calendar


class Bir1601EQ(models.Model):
    _name = "bir.1601eq"
    _description = "BIR 1601-EQ Quarterly Return"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "year desc, quarter desc"
    _rec_name = "name"

    # ======================================================== 
    # BASIC INFO
    # ======================================================== 
    name = fields.Char(
        string="Reference No.",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('filed', 'Filed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related="company_id.currency_id",
        store=True
    )

    # ======================================================== 
    # PART I – BACKGROUND INFORMATION
    # ======================================================== 
    year = fields.Integer(required=True, tracking=True)
    
    quarter = fields.Selection([
        ('1', '1st Quarter'),
        ('2', '2nd Quarter'),
        ('3', '3rd Quarter'),
        ('4', '4th Quarter'),
    ], required=True, tracking=True)
    
    return_period_from = fields.Date(
        compute="_compute_return_period",
        store=True
    )

    return_period_to = fields.Date(
        compute="_compute_return_period",
        store=True
    )
    
    is_amended = fields.Boolean(string="Amended Return")
    any_taxes_withheld = fields.Boolean(string="Any Taxes Withheld?")
    no_of_sheets = fields.Integer(string="No. of Sheets Attached")
    
    tin = fields.Char(string="TIN")
    rdo_code = fields.Char(string="RDO Code")
    withholding_agent_name = fields.Char(string="Withholding Agent Name")
    
    category = fields.Selection([
        ('private', 'Private'),
        ('government', 'Government'),
    ], string="Category of Withholding Agent")
    
    contact_number = fields.Char()
    email = fields.Char()
    zip_code = fields.Char()
    
    registered_address = fields.Text(
        compute="_compute_registered_address",
        store=True
    )

    # ======================================================== 
    # PART II – TAX COMPUTATION
    # ======================================================== 
    line_ids = fields.One2many(
        "bir.1601eq.line",
        "parent_id",
        string="ATC Lines"
    )
    
    total_tax_withheld = fields.Monetary(
        compute="_compute_totals",
        store=True
    )
    
    # Remittances
    remittance_1st_month = fields.Monetary()
    remittance_2nd_month = fields.Monetary()
    tax_remitted_prev = fields.Monetary()
    over_remittance_prev = fields.Monetary()
    other_payments = fields.Monetary()
    
    total_remittances = fields.Monetary(
        compute="_compute_totals",
        store=True
    )
    
    tax_still_due = fields.Monetary(
        compute="_compute_totals",
        store=True
    )
    
    # Penalties
    surcharge = fields.Monetary()
    interest = fields.Monetary()
    compromise = fields.Monetary()
    
    total_penalties = fields.Monetary(
        compute="_compute_totals",
        store=True
    )
    
    total_amount_due = fields.Monetary(
        compute="_compute_totals",
        store=True
    )
    
    over_remittance_option = fields.Selection([
        ('refund', 'To be Refunded'),
        ('tcc', 'To be Issued Tax Credit Certificate'),
        ('carry_over', 'To be Carried Over to Next Quarter'),
    ])

    # ======================================================== 
    # PART III – PAYMENT DETAILS
    # ======================================================== 
    payment_cash = fields.Monetary(string="Cash/Bank Debit Memo")
    payment_check = fields.Monetary(string="Check")
    payment_tax_debit = fields.Monetary(string="Tax Debit Memo")
    payment_others = fields.Monetary(string="Others")
    other_payment_details = fields.Text()

    # ======================================================== 
    # CREATE OVERRIDE FOR SEQUENCE
    # ======================================================== 
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            sequence = self.env['ir.sequence'].next_by_code('bir.1601eq')
            vals['name'] = sequence or 'New'
        return super().create(vals)

    # ======================================================== 
    # AUTOFILL COMPANY DETAILS
    # ======================================================== 
    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Autofill TIN and other company details"""
        if self.company_id:
            self.tin = self.company_id.vat or ''
            self.withholding_agent_name = self.company_id.name or ''
            self.contact_number = self.company_id.phone or ''
            self.email = self.company_id.email or ''
            self.zip_code = self.company_id.zip or ''
            
            # You can add custom fields if you have them in res.company
            # self.rdo_code = self.company_id.rdo_code or ''
            # self.category = self.company_id.category or 'private'

    # ======================================================== 
    # COMPUTE REGISTERED ADDRESS
    # ======================================================== 
    @api.depends(
        'company_id.street',
        'company_id.street2',
        'company_id.city',
        'company_id.state_id',
        'company_id.country_id'
    )
    def _compute_registered_address(self):
        for rec in self:
            company = rec.company_id
            parts = [
                company.street or '',
                company.street2 or '',
                company.city or '',
                company.state_id.name if company.state_id else '',
                company.country_id.name if company.country_id else '',
            ]
            rec.registered_address = ', '.join(filter(None, parts))

    # ======================================================== 
    # COMPUTE TOTALS
    # ======================================================== 
    @api.depends(
        "line_ids.tax_withheld",
        "remittance_1st_month",
        "remittance_2nd_month",
        "tax_remitted_prev",
        "over_remittance_prev",
        "other_payments",
        "surcharge",
        "interest",
        "compromise",
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_tax_withheld = sum(rec.line_ids.mapped("tax_withheld"))
            
            rec.total_remittances = sum([
                rec.remittance_1st_month or 0,
                rec.remittance_2nd_month or 0,
                rec.tax_remitted_prev or 0,
                rec.over_remittance_prev or 0,
                rec.other_payments or 0,
            ])
            
            rec.tax_still_due = rec.total_tax_withheld - rec.total_remittances
            
            rec.total_penalties = sum([
                rec.surcharge or 0,
                rec.interest or 0,
                rec.compromise or 0,
            ])
            
            rec.total_amount_due = rec.tax_still_due + rec.total_penalties

    # ======================================================== 
    # AUTO QUARTER DATE RANGE
    # ======================================================== 
    @api.depends('year', 'quarter')
    def _compute_return_period(self):
        for rec in self:
            if rec.year and rec.quarter:
                q = int(rec.quarter)
                start_month = (q - 1) * 3 + 1
                end_month = start_month + 2
                last_day = calendar.monthrange(rec.year, end_month)[1]
                
                rec.return_period_from = date(rec.year, start_month, 1)
                rec.return_period_to = date(rec.year, end_month, last_day)
            else:
                rec.return_period_from = False
                rec.return_period_to = False

    def _inverse_return_period_from(self):
        pass

    def _inverse_return_period_to(self):
        pass
    # ======================================================== 
    # WORKFLOW BUTTONS
    # ======================================================== 
    def action_generate(self):
        """Generate withholding tax lines from posted account moves"""
        self.ensure_one()

        if self.state != 'draft':
            raise ValidationError(_("You can only generate in Draft state."))

        if not self.return_period_from or not self.return_period_to:
            raise ValidationError(_("Please set Year and Quarter first."))

        # 1️⃣ Clear existing ATC lines
        self.write({'line_ids': [(5, 0, 0)]})

        # 2️⃣ Collect posted account moves in the period
        moves = self.env['account.move'].search([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.return_period_from),
            ('date', '<=', self.return_period_to),
            ('state', '=', 'posted'),
        ])

        atc_data = {}
        for move in moves:
            tax_lines = move.line_ids.filtered(
                lambda l: l.tax_line_id and l.tax_line_id.type_tax_use == 'purchase'
            )
            for line in tax_lines:
                atc = line.tax_line_id.name or 'Unspecified'
                if atc not in atc_data:
                    atc_data[atc] = {
                        'atc': atc,
                        'tax_base': 0.0,
                        'tax_rate': line.tax_line_id.amount or 0.0,
                        'tax_withheld': 0.0,
                    }
                atc_data[atc]['tax_base'] += abs(line.tax_base_amount or 0.0)
                atc_data[atc]['tax_withheld'] += abs(line.balance or 0.0)

        # 3️⃣ Create new ATC lines
        lines_vals = [(0, 0, data) for data in atc_data.values()]
        if lines_vals:
            self.write({'line_ids': lines_vals})

        # 4️⃣ Recompute totals immediately
        self._compute_totals()

        # 5️⃣ Show success notification AND reload form
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%s withholding tax line(s) generated.') % len(atc_data),
                'type': 'success',
                'sticky': False,
            },
            'target': 'self',  # ensures it affects the current view
            'next': {'type': 'ir.actions.client', 'tag': 'reload'},  # reloads the form
        }



    def action_confirm(self):
        self.state = 'confirmed'

    def action_file(self):
        self.state = 'filed'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_set_draft(self):
        self.state = 'draft'

# ============================================================
# ATC LINE MODEL
# ============================================================

class Bir1601EQLine(models.Model):
    _name = "bir.1601eq.line"
    _description = "BIR 1601EQ ATC Lines"

    parent_id = fields.Many2one(
        "bir.1601eq",
        required=True,
        ondelete="cascade"
    )

    atc = fields.Char(string="ATC")
    nature_of_payment = fields.Char()
    tax_base = fields.Monetary()
    tax_rate = fields.Float()
    tax_withheld = fields.Monetary()

    currency_id = fields.Many2one(
        related="parent_id.currency_id",
        store=True
    )
