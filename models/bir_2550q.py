from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import base64
import calendar

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
