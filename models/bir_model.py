from odoo import models, fields, api
from datetime import date
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
    _rec_name = "reference_no"

    reference_no = fields.Char(
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
                        if "Expanded" in line.tax_line_id.name:
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


        
