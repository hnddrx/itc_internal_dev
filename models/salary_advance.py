import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)  # Initialize logger


class SalaryAdvance(models.Model):
    _name = 'salary.advance'
    _description = 'Salary Advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string="Reference", required=True, copy=False,  readonly=True, default='New')
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    
    advance_amount = fields.Monetary(
        string="Advance Amount",
        currency_field='currency_id',
        required=True,
        tracking=True,
    )

    date = fields.Date(string="Request Date", default=fields.Date.today())
    reason = fields.Text(string="Reason")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
        ('cancelled','Cancelled'),
    ], string="Status", tracking=True)

    journal_id = fields.Many2one('account.journal', string="Journal", domain=[('type', '=', 'cash')], tracking=True)
    is_urgent = fields.Boolean(string="Urgent", tracking=True, default=False, help="Mark this transaction as urgent. A gold star indicates urgency.")

    @api.model
    def create(self, vals):
        _logger.info("Creating Salary Advance with values: %s", vals)
        try:
            if vals.get('name', 'New') == 'New':
                sequence_code = 'salary.advance'
                company = self.env.company
                company_initials = ''.join(word[0].upper() for word in company.name.split())

                # Fetch sequence
                seq_value = self.env['ir.sequence'].next_by_code(sequence_code)
                if seq_value:
                    vals['name'] = f"{company_initials}/{seq_value}"  # e.g. OP/SA00001
                else:
                    vals['name'] = f"{company_initials}/SA00001"  # Fallback

            salary_advance = super(SalaryAdvance, self).create(vals)
            return salary_advance

        except Exception as e:
            _logger.error("Error creating salary advance: %s", e)
            raise

    def action_toggle_urgent(self):
        for rec in self:
            rec.is_urgent = not rec.is_urgent
            _logger.info("Toggled urgent for Salary Advance ID %s: %s", rec.id, rec.is_urgent)

    def action_submit(self):
        self.write({'state': 'draft'})
        _logger.info("Salary Advance %s submitted and set to Draft.", self.ids)

    def action_approve(self):
        self.write({'state': 'approved'})
        _logger.info("Salary Advance %s approved.", self.ids)

    def action_reject(self):
        self.write({'state': 'rejected'})
        _logger.info("Salary Advance %s rejected.", self.ids)

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        _logger.info("Salary Advance %s cancelled.", self.ids) 
        
    def action_pay(self):
        if not self.journal_id:
            _logger.error("Payment attempted without selecting a Journal.")
            raise UserError("Please select a Journal for payment.")

        advance_account = self.env['account.account'].search([
            ('account_type', '=', 'asset_receivable')
        ], limit=1)

        if not advance_account:
            _logger.error("No Employee Advance account found in Chart of Accounts.")
            raise UserError("Please configure an Employee Advance account in your Chart of Accounts.")

        _logger.info("Creating account move for Salary Advance ID %s", self.id)

        move = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.name,
            'line_ids': [
                (0, 0, {
                    'name': 'Salary Advance',
                    'account_id': self.journal_id.default_account_id.id,
                    'debit': self.advance_amount,
                }),
                (0, 0, {
                    'name': 'Salary Advance',
                    'account_id': advance_account.id,
                    'credit': self.advance_amount,
                }),
            ]
        })
        move.action_post()
        self.write({'state': 'paid'})
        _logger.info("Salary Advance %s marked as Paid.", self.ids)
