# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import xlsxwriter
import base64
from io import BytesIO
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class BIR1604E(models.Model):
    _name = 'bir.1604e'
    _description = 'BIR Form 1604-E - Annual Information Return'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    
    # Period Information
    year = fields.Integer(string='Year', required=True, default=lambda self: datetime.now().year, tracking=True)
    date_from = fields.Date(string='Period From', compute='_compute_period_dates', store=True)
    date_to = fields.Date(string='Period To', compute='_compute_period_dates', store=True)
    
    # Company Information
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    tin = fields.Char(string='TIN', related='company_id.vat', readonly=True)
    withholding_agent_name = fields.Char(string='Withholding Agent Name', related='company_id.name', readonly=True)
    registered_address = fields.Text(string='Registered Address', compute='_compute_company_address', store=True)
    rdo_code = fields.Char(string='RDO Code')
    line_of_business = fields.Char(string='Line of Business/Occupation')
    
    # Return Information
    amended_return = fields.Boolean(string='Amended Return?', default=False)
    num_sheets_attached = fields.Integer(string='No. of Sheets Attached', compute='_compute_sheets_attached', store=True)
    
    # Category
    category_private = fields.Boolean(string='Private', default=True)
    category_government = fields.Boolean(string='Government', default=False)
    
    # Schedule 1: Form 1601-E Remittances
    schedule1_line_ids = fields.One2many('bir.1604e.schedule1', 'form_id', string='Schedule 1 - Form 1601-E Remittances')
    total_1601e_taxes = fields.Float(string='Total 1601-E Taxes', compute='_compute_schedule_totals', store=True)
    total_1601e_penalties = fields.Float(string='Total 1601-E Penalties', compute='_compute_schedule_totals', store=True)
    total_1601e_remitted = fields.Float(string='Total 1601-E Remitted', compute='_compute_schedule_totals', store=True)
    
    # Schedule 2: Form 1606 Remittances
    schedule2_line_ids = fields.One2many('bir.1604e.schedule2', 'form_id', string='Schedule 2 - Form 1606 Remittances')
    total_1606_taxes = fields.Float(string='Total 1606 Taxes', compute='_compute_schedule_totals', store=True)
    total_1606_penalties = fields.Float(string='Total 1606 Penalties', compute='_compute_schedule_totals', store=True)
    total_1606_remitted = fields.Float(string='Total 1606 Remitted', compute='_compute_schedule_totals', store=True)
    
    # Schedule 3: Exempt from Withholding
    schedule3_line_ids = fields.One2many('bir.1604e.schedule3', 'form_id', string='Schedule 3 - Exempt from Withholding')
    total_schedule3_amount = fields.Float(string='Total Schedule 3', compute='_compute_schedule_totals', store=True)
    
    # Schedule 4: Expanded Withholding Tax
    schedule4_line_ids = fields.One2many('bir.1604e.schedule4', 'form_id', string='Schedule 4 - Expanded Withholding Tax')
    total_schedule4_income = fields.Float(string='Total Schedule 4 Income', compute='_compute_schedule_totals', store=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('submitted', 'Submitted')
    ], string='Status', default='draft', tracking=True)
    
    # Signatory
    signatory_name = fields.Char(string='Signatory Name')
    signatory_title = fields.Char(string='Signatory Title')
    
    # Export
    excel_file = fields.Binary(string='Excel File', readonly=True)
    excel_filename = fields.Char(string='Excel Filename', readonly=True)
    
    report_date = fields.Date(string='Report Date', default=fields.Date.today)
    
    @api.depends('year')
    def _compute_period_dates(self):
        for record in self:
            if record.year:
                record.date_from = date(record.year, 1, 1)
                record.date_to = date(record.year, 12, 31)
    
    @api.depends('company_id')
    def _compute_company_address(self):
        for record in self:
            if record.company_id:
                address_parts = []
                if record.company_id.street:
                    address_parts.append(record.company_id.street)
                if record.company_id.street2:
                    address_parts.append(record.company_id.street2)
                if record.company_id.city:
                    address_parts.append(record.company_id.city)
                if record.company_id.state_id:
                    address_parts.append(record.company_id.state_id.name)
                if record.company_id.zip:
                    address_parts.append(record.company_id.zip)
                if record.company_id.country_id:
                    address_parts.append(record.company_id.country_id.name)
                
                record.registered_address = ', '.join(address_parts)
    
    @api.depends('schedule3_line_ids', 'schedule4_line_ids')
    def _compute_sheets_attached(self):
        for record in self:
            sheets = 0
            if record.schedule3_line_ids:
                sheets += (len(record.schedule3_line_ids) // 20) + 1
            if record.schedule4_line_ids:
                sheets += (len(record.schedule4_line_ids) // 30) + 1
            record.num_sheets_attached = sheets
    
    @api.depends('schedule1_line_ids.taxes_withheld', 'schedule1_line_ids.penalties', 'schedule1_line_ids.total_remitted',
                 'schedule2_line_ids.taxes_withheld', 'schedule2_line_ids.penalties', 'schedule2_line_ids.total_remitted',
                 'schedule3_line_ids.income_payment', 'schedule4_line_ids.income_payment')
    def _compute_schedule_totals(self):
        for record in self:
            record.total_1601e_taxes = sum(record.schedule1_line_ids.mapped('taxes_withheld'))
            record.total_1601e_penalties = sum(record.schedule1_line_ids.mapped('penalties'))
            record.total_1601e_remitted = sum(record.schedule1_line_ids.mapped('total_remitted'))
            
            record.total_1606_taxes = sum(record.schedule2_line_ids.mapped('taxes_withheld'))
            record.total_1606_penalties = sum(record.schedule2_line_ids.mapped('penalties'))
            record.total_1606_remitted = sum(record.schedule2_line_ids.mapped('total_remitted'))
            
            record.total_schedule3_amount = sum(record.schedule3_line_ids.mapped('income_payment'))
            record.total_schedule4_income = sum(record.schedule4_line_ids.mapped('income_payment'))
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('bir.1604e') or 'New'
        return super(BIR1604E, self).create(vals)
    
    def action_generate_data(self):
        """Generate annual data from various sources"""
        self.ensure_one()
        
        # Clear existing lines
        self.schedule1_line_ids.unlink()
        self.schedule2_line_ids.unlink()
        self.schedule3_line_ids.unlink()
        self.schedule4_line_ids.unlink()
        
        # Generate Schedule 1: From quarterly 1601-EQ forms (if using that module)
        self._generate_schedule1()
        
        # Generate Schedule 2: From Form 1606 data (if exists)
        self._generate_schedule2()
        
        # Generate Schedule 3: Exempt from withholding (from vendor bills)
        self._generate_schedule3()
        
        # Generate Schedule 4: Expanded withholding tax (from vendor bills with EWT)
        self._generate_schedule4()
        
        self.state = 'computed'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Generated annual data for year {self.year}',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _generate_schedule1(self):
        """Generate Schedule 1 from monthly/quarterly tax remittances"""
        Schedule1 = self.env['bir.1604e.schedule1']
        
        # Try to get data from BIR 1601-EQ forms if module is installed
        if 'bir.1601eq' in self.env:
            forms_1601eq = self.env['bir.1601eq'].search([
                ('year', '=', self.year),
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'submitted')
            ])
            
            # Group by quarter and aggregate monthly data
            months_data = {}
            for form in forms_1601eq:
                quarter_map = {
                    '1': [(1, 'JAN'), (2, 'FEB'), (3, 'MAR')],
                    '2': [(4, 'APR'), (5, 'MAY'), (6, 'JUN')],
                    '3': [(7, 'JUL'), (8, 'AUG'), (9, 'SEPT')],
                    '4': [(10, 'OCT'), (11, 'NOV'), (12, 'DEC')]
                }
                
                if form.quarter in quarter_map:
                    # Distribute quarterly amount across months (simplified)
                    monthly_amount = form.tax_withheld_current_month / 3
                    for month_num, month_name in quarter_map[form.quarter]:
                        months_data[month_num] = {
                            'month': month_name,
                            'taxes': monthly_amount,
                            'penalties': form.penalties / 3 if form.penalties else 0.0
                        }
        else:
            # If no 1601-EQ module, create empty monthly entries
            month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 
                          'JUL', 'AUG', 'SEPT', 'OCT', 'NOV', 'DEC']
            for idx, month in enumerate(month_names, 1):
                months_data[idx] = {
                    'month': month,
                    'taxes': 0.0,
                    'penalties': 0.0
                }
        
        # Create Schedule 1 lines
        for month_num in sorted(months_data.keys()):
            data = months_data[month_num]
            Schedule1.create({
                'form_id': self.id,
                'month': data['month'],
                'date_remittance': date(self.year, month_num, 1),
                'taxes_withheld': data['taxes'],
                'penalties': data['penalties'],
            })
    
    def _generate_schedule2(self):
        """Generate Schedule 2 from Form 1606 data"""
        Schedule2 = self.env['bir.1604e.schedule2']
        
        # Create monthly entries (can be populated from actual 1606 data if available)
        month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 
                      'JUL', 'AUG', 'SEPT', 'OCT', 'NOV', 'DEC']
        
        for idx, month in enumerate(month_names, 1):
            Schedule2.create({
                'form_id': self.id,
                'month': month,
                'date_remittance': date(self.year, idx, 1),
                'taxes_withheld': 0.0,
                'penalties': 0.0,
            })
    
    def _generate_schedule3(self):
        """Generate Schedule 3: Payees exempt from withholding tax"""
        Schedule3 = self.env['bir.1604e.schedule3']
        
        # Query vendor bills that are exempt from withholding
        AccountMove = self.env['account.move']
        bills = AccountMove.search([
            ('move_type', '=', 'in_invoice'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        
        # Group by partner
        partner_data = {}
        for bill in bills:
            partner = bill.partner_id
            if partner.id not in partner_data:
                partner_data[partner.id] = {
                    'partner_id': partner.id,
                    'tin': partner.vat or '',
                    'name': partner.name,
                    'amount': 0.0
                }
            partner_data[partner.id]['amount'] += bill.amount_total
        
        # Create Schedule 3 lines (limit to sample for demonstration)
        seq = 1
        for partner_id, data in list(partner_data.items())[:100]:  # Limit for demo
            Schedule3.create({
                'form_id': self.id,
                'sequence': seq,
                'tin': data['tin'],
                'payee_name': data['name'],
                'atc_code': 'WI010',  # Default ATC, should be configurable
                'nature_income': 'Professional Fees',
                'income_payment': data['amount'],
            })
            seq += 1
    
    def _generate_schedule4(self):
        """Generate Schedule 4: Payees subject to expanded withholding tax"""
        Schedule4 = self.env['bir.1604e.schedule4']
        
        # Query vendor bills with withholding tax
        AccountMove = self.env['account.move']
        bills = AccountMove.search([
            ('move_type', '=', 'in_invoice'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        
        # Group by partner
        partner_data = {}
        for bill in bills:
            partner = bill.partner_id
            
            # Look for withholding tax in bill lines
            wht_amount = 0.0
            base_amount = bill.amount_untaxed
            
            # Try to find withholding tax lines
            for line in bill.line_ids:
                if 'withholding' in (line.name or '').lower() or 'ewt' in (line.name or '').lower():
                    wht_amount += abs(line.balance)
            
            if partner.id not in partner_data:
                partner_data[partner.id] = {
                    'partner_id': partner.id,
                    'tin': partner.vat or '',
                    'name': partner.name,
                    'amount': 0.0,
                    'wht': 0.0
                }
            partner_data[partner.id]['amount'] += base_amount
            partner_data[partner.id]['wht'] += wht_amount
        
        # Create Schedule 4 lines
        seq = 1
        for partner_id, data in list(partner_data.items())[:100]:  # Limit for demo
            tax_rate = (data['wht'] / data['amount'] * 100) if data['amount'] > 0 else 0.0
            
            Schedule4.create({
                'form_id': self.id,
                'sequence': seq,
                'tin': data['tin'],
                'payee_name': data['name'],
                'atc_code': 'WC010',  # Default ATC
                'nature_income': 'Professional Fees',
                'income_payment': data['amount'],
                'tax_rate': tax_rate,
            })
            seq += 1
    
    def action_export_excel(self):
        """Export to Excel matching BIR 1604-E format"""
        self.ensure_one()
        
        # Create Excel file in memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#D3D3D3'
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        label_format = workbook.add_format({
            'bold': True,
            'align': 'left',
            'border': 1
        })
        
        data_format = workbook.add_format({
            'align': 'right',
            'border': 1,
            'num_format': '#,##0.00'
        })
        
        text_format = workbook.add_format({
            'align': 'left',
            'border': 1
        })
        
        center_format = workbook.add_format({
            'align': 'center',
            'border': 1
        })
        
        # Main Sheet
        sheet = workbook.add_worksheet('BIR Form 1604-E')
        sheet.set_column('A:A', 8)
        sheet.set_column('B:C', 12)
        sheet.set_column('D:P', 15)
        
        row = 0
        
        # Header
        sheet.write(row, 0, '(To be filled up by the BIR)', text_format)
        row += 1
        sheet.write(row, 1, 'DLN:', label_format)
        sheet.write(row, 24, 'PSOC:', label_format)
        row += 2
        
        # Instructions
        sheet.write(row, 0, 'Fill in all applicable spaces. Mark all appropriate boxes with an "X".', text_format)
        row += 1
        
        # Basic Info Row
        sheet.write(row, 0, '1', center_format)
        sheet.write(row, 1, 'For the Year', label_format)
        sheet.write(row, 12, '2', center_format)
        sheet.write(row, 13, 'Amended Return?', label_format)
        sheet.write(row, 24, '3', center_format)
        sheet.write(row, 25, 'No of Sheets Attached', label_format)
        row += 1
        
        sheet.write(row, 1, str(self.year), center_format)
        sheet.write(row, 20, 'X' if self.amended_return else '', center_format)
        sheet.write(row, 23, 'X' if not self.amended_return else '', center_format)
        sheet.write(row, 25, self.num_sheets_attached, center_format)
        row += 1
        
        # Part I: Background Information
        sheet.merge_range(row, 0, row, 4, 'Part I - Background Information', title_format)
        row += 1
        
        sheet.write(row, 0, '4', center_format)
        sheet.write(row, 1, 'TIN', label_format)
        sheet.write(row, 17, '5', center_format)
        sheet.write(row, 18, 'RDO Code', label_format)
        sheet.write(row, 23, '6', center_format)
        sheet.write(row, 24, 'Line of Business/Occupation', label_format)
        row += 1
        
        sheet.write(row, 1, self.tin or '', text_format)
        sheet.write(row, 18, self.rdo_code or '', text_format)
        sheet.write(row, 24, self.line_of_business or '', text_format)
        row += 2
        
        sheet.write(row, 0, '7', center_format)
        sheet.write(row, 1, 'Withholding Agent Name', label_format)
        row += 1
        sheet.merge_range(row, 1, row, 10, self.withholding_agent_name or '', text_format)
        row += 2
        
        sheet.write(row, 0, '9', center_format)
        sheet.write(row, 1, 'Registered Address', label_format)
        row += 1
        sheet.merge_range(row, 1, row, 15, self.registered_address or '', text_format)
        row += 2
        
        sheet.write(row, 0, '11', center_format)
        sheet.write(row, 1, 'Category of Withholding Agent', label_format)
        sheet.write(row, 12, 'X' if self.category_private else '', center_format)
        sheet.write(row, 13, 'Private', text_format)
        sheet.write(row, 16, 'X' if self.category_government else '', center_format)
        sheet.write(row, 17, 'Government', text_format)
        row += 2
        
        # Part II: Summary of Remittances
        sheet.merge_range(row, 0, row, 10, 'Part II - Summary of Remittances', title_format)
        row += 1
        
        # Schedule 1: Form 1601-E
        sheet.write(row, 0, 'Schedule 1', label_format)
        sheet.merge_range(row, 5, row, 10, 'Remittance per BIR Form No. 1601-E', title_format)
        row += 1
        
        # Schedule 1 Headers
        sheet.write(row, 0, 'MONTH', header_format)
        sheet.merge_range(row, 3, row, 3, 'DATE OF REMITTANCE', header_format)
        sheet.merge_range(row, 7, row, 15, 'NAME OF BANK/BANKCODE/ROR NO., IF ANY', header_format)
        sheet.merge_range(row, 16, row, 23, 'TAXES WITHHELD', header_format)
        sheet.merge_range(row, 24, row, 27, 'PENALTIES', header_format)
        sheet.merge_range(row, 28, row, 30, 'TOTAL AMOUNT REMITTED', header_format)
        row += 1
        
        # Schedule 1 Data
        for line in self.schedule1_line_ids:
            sheet.write(row, 0, line.month, text_format)
            sheet.write(row, 3, line.date_remittance.strftime('%m/%d/%Y') if line.date_remittance else '', text_format)
            sheet.write(row, 7, line.bank_name or '', text_format)
            sheet.write(row, 16, line.taxes_withheld, data_format)
            sheet.write(row, 24, line.penalties, data_format)
            sheet.write(row, 28, line.total_remitted, data_format)
            row += 1
        
        # Schedule 1 Total
        sheet.write(row, 0, 'Total', label_format)
        sheet.write(row, 16, self.total_1601e_taxes, data_format)
        sheet.write(row, 24, self.total_1601e_penalties, data_format)
        sheet.write(row, 28, self.total_1601e_remitted, data_format)
        row += 2
        
        # Schedule 2: Form 1606
        sheet.write(row, 0, 'Schedule 2', label_format)
        sheet.merge_range(row, 5, row, 10, 'Remittance per BIR Form No. 1606', title_format)
        row += 1
        
        # Schedule 2 Headers
        sheet.write(row, 0, 'MONTH', header_format)
        sheet.merge_range(row, 3, row, 3, 'DATE OF REMITTANCE', header_format)
        sheet.merge_range(row, 7, row, 15, 'NAME OF BANK/BANKCODE/ROR NO., IF ANY', header_format)
        sheet.merge_range(row, 16, row, 23, 'TAXES WITHHELD', header_format)
        sheet.merge_range(row, 24, row, 27, 'PENALTIES', header_format)
        sheet.merge_range(row, 28, row, 30, 'TOTAL AMOUNT REMITTED', header_format)
        row += 1
        
        # Schedule 2 Data
        for line in self.schedule2_line_ids:
            sheet.write(row, 0, line.month, text_format)
            sheet.write(row, 3, line.date_remittance.strftime('%m/%d/%Y') if line.date_remittance else '', text_format)
            sheet.write(row, 7, line.bank_name or '', text_format)
            sheet.write(row, 16, line.taxes_withheld, data_format)
            sheet.write(row, 24, line.penalties, data_format)
            sheet.write(row, 28, line.total_remitted, data_format)
            row += 1
        
        # Schedule 2 Total
        sheet.write(row, 0, 'Total', label_format)
        sheet.write(row, 16, self.total_1606_taxes, data_format)
        sheet.write(row, 24, self.total_1606_penalties, data_format)
        sheet.write(row, 28, self.total_1606_remitted, data_format)
        row += 2
        
        # Signatory Section
        sheet.write(row, 2, '12', center_format)
        sheet.write(row, 4, self.signatory_name or '', text_format)
        sheet.write(row, 21, '13', center_format)
        sheet.write(row, 22, self.signatory_title or '', text_format)
        row += 1
        sheet.merge_range(row, 3, row, 15, "Taxpayer/Authorized Agent Signature over Printed Name", label_format)
        sheet.merge_range(row, 22, row, 27, "Title/Position of Signatory", label_format)
        
        # Sheet 2: Schedule 3
        sheet3 = workbook.add_worksheet('Schedule 3')
        sheet3.set_column('A:A', 6)
        sheet3.set_column('B:G', 12)
        sheet3.set_column('H:R', 20)
        
        row3 = 0
        sheet3.merge_range(row3, 0, row3, 30, 'Schedule 3: ALPHALIST OF OTHER PAYEES WHOSE INCOME PAYMENTS ARE EXEMPT FROM WITHHOLDING TAX', title_format)
        row3 += 1
        
        # Headers
        sheet3.write(row3, 0, 'SEQ NO.', header_format)
        sheet3.merge_range(row3, 2, row3, 7, 'Taxpayer Identification Number (TIN)', header_format)
        sheet3.merge_range(row3, 8, row3, 17, 'NAME OF PAYEES', header_format)
        sheet3.write(row3, 18, 'ATC', header_format)
        sheet3.merge_range(row3, 21, row3, 25, 'NATURE OF INCOME PAYMENT', header_format)
        sheet3.merge_range(row3, 27, row3, 30, 'AMOUNT OF INCOME PAYMENT', header_format)
        row3 += 1
        
        # Schedule 3 Data
        for line in self.schedule3_line_ids:
            sheet3.write(row3, 0, line.sequence, center_format)
            sheet3.write(row3, 2, line.tin or '', text_format)
            sheet3.write(row3, 8, line.payee_name, text_format)
            sheet3.write(row3, 18, line.atc_code, text_format)
            sheet3.write(row3, 21, line.nature_income, text_format)
            sheet3.write(row3, 27, line.income_payment, data_format)
            row3 += 1
        
        # Sheet 3: Schedule 4
        sheet4 = workbook.add_worksheet('Schedule 4')
        sheet4.set_column('A:A', 6)
        sheet4.set_column('B:G', 12)
        sheet4.set_column('H:R', 20)
        
        row4 = 0
        sheet4.merge_range(row4, 0, row4, 30, 'Schedule 4: Alphalist of Payees Subject to Expanded Withholding Tax', title_format)
        row4 += 1
        
        # Headers
        sheet4.write(row4, 0, 'SEQ NO.', header_format)
        sheet4.merge_range(row4, 2, row4, 7, 'TAXPAYER IDENTIFICATION NUMBER (TIN)', header_format)
        sheet4.merge_range(row4, 8, row4, 17, 'NAME OF PAYEES', header_format)
        sheet4.write(row4, 18, 'ATC', header_format)
        sheet4.merge_range(row4, 21, row4, 25, 'NATURE OF INCOME PAYMENT', header_format)
        sheet4.merge_range(row4, 27, row4, 30, 'AMOUNT OF INCOME PAYMENT', header_format)
        sheet4.write(row4, 31, 'RATE OF TAX', header_format)
        row4 += 1
        
        # Schedule 4 Data
        for line in self.schedule4_line_ids:
            sheet4.write(row4, 0, line.sequence, center_format)
            sheet4.write(row4, 2, line.tin or '', text_format)
            sheet4.write(row4, 8, line.payee_name, text_format)
            sheet4.write(row4, 18, line.atc_code, text_format)
            sheet4.write(row4, 21, line.nature_income, text_format)
            sheet4.write(row4, 27, line.income_payment, data_format)
            sheet4.write(row4, 31, line.tax_rate, data_format)
            row4 += 1
        
        # Close workbook and save
        workbook.close()
        output.seek(0)
        
        # Save to record
        filename = f'BIR_1604E_{self.year}_{self.company_id.name}.xlsx'
        self.write({
            'excel_file': base64.b64encode(output.read()),
            'excel_filename': filename
        })
        
        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/bir.1604e/{self.id}/excel_file/{filename}?download=true',
            'target': 'self',
        }
    
    def action_reset_to_draft(self):
        self.state = 'draft'
    
    def action_submit(self):
        self.state = 'submitted'


class BIR1604ESchedule1(models.Model):
    _name = 'bir.1604e.schedule1'
    _description = 'BIR 1604-E Schedule 1 - Form 1601-E Remittances'
    _order = 'form_id, month'
    
    form_id = fields.Many2one('bir.1604e', string='Form', required=True, ondelete='cascade')
    month = fields.Selection([
        ('JAN', 'January'),
        ('FEB', 'February'),
        ('MAR', 'March'),
        ('APR', 'April'),
        ('MAY', 'May'),
        ('JUN', 'June'),
        ('JUL', 'July'),
        ('AUG', 'August'),
        ('SEPT', 'September'),
        ('OCT', 'October'),
        ('NOV', 'November'),
        ('DEC', 'December'),
    ], string='Month', required=True)
    date_remittance = fields.Date(string='Date of Remittance')
    bank_name = fields.Char(string='Bank Name/Bank Code/ROR No.')
    taxes_withheld = fields.Float(string='Taxes Withheld')
    penalties = fields.Float(string='Penalties')
    total_remitted = fields.Float(string='Total Amount Remitted', compute='_compute_total', store=True)
    
    @api.depends('taxes_withheld', 'penalties')
    def _compute_total(self):
        for record in self:
            record.total_remitted = record.taxes_withheld + record.penalties


class BIR1604ESchedule2(models.Model):
    _name = 'bir.1604e.schedule2'
    _description = 'BIR 1604-E Schedule 2 - Form 1606 Remittances'
    _order = 'form_id, month'
    
    form_id = fields.Many2one('bir.1604e', string='Form', required=True, ondelete='cascade')
    month = fields.Selection([
        ('JAN', 'January'),
        ('FEB', 'February'),
        ('MAR', 'March'),
        ('APR', 'April'),
        ('MAY', 'May'),
        ('JUN', 'June'),
        ('JUL', 'July'),
        ('AUG', 'August'),
        ('SEPT', 'September'),
        ('OCT', 'October'),
        ('NOV', 'November'),
        ('DEC', 'December'),
    ], string='Month', required=True)
    date_remittance = fields.Date(string='Date of Remittance')
    bank_name = fields.Char(string='Bank Name/Bank Code/ROR No.')
    taxes_withheld = fields.Float(string='Taxes Withheld')
    penalties = fields.Float(string='Penalties')
    total_remitted = fields.Float(string='Total Amount Remitted', compute='_compute_total', store=True)
    
    @api.depends('taxes_withheld', 'penalties')
    def _compute_total(self):
        for record in self:
            record.total_remitted = record.taxes_withheld + record.penalties


class BIR1604ESchedule3(models.Model):
    _name = 'bir.1604e.schedule3'
    _description = 'BIR 1604-E Schedule 3 - Exempt from Withholding'
    _order = 'form_id, sequence'
    
    form_id = fields.Many2one('bir.1604e', string='Form', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Seq No.', required=True)
    tin = fields.Char(string='TIN')
    payee_name = fields.Char(string='Name of Payee', required=True)
    atc_code = fields.Char(string='ATC')
    nature_income = fields.Char(string='Nature of Income Payment')
    income_payment = fields.Float(string='Amount of Income Payment')


class BIR1604ESchedule4(models.Model):
    _name = 'bir.1604e.schedule4'
    _description = 'BIR 1604-E Schedule 4 - Expanded Withholding Tax'
    _order = 'form_id, sequence'
    
    form_id = fields.Many2one('bir.1604e', string='Form', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Seq No.', required=True)
    tin = fields.Char(string='TIN')
    payee_name = fields.Char(string='Name of Payee', required=True)
    atc_code = fields.Char(string='ATC')
    nature_income = fields.Char(string='Nature of Income Payment')
    income_payment = fields.Float(string='Amount of Income Payment')
    tax_rate = fields.Float(string='Rate of Tax (%)')