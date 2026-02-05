from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.modules.module import get_resource_path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader, PdfWriter
import io
import base64


class Account(models.Model):
    _inherit = "account.move"

    x_invoice_type = fields.Selection(
        [('service', 'Service'), ('consu', 'Sales')],
        string="Invoice Type",
        default='service',
    )

    x_partner_tin = fields.Char(
        string="Customer TIN",
        related='partner_id.vat',
        readonly=True,
        store=True,
    )

    x_reference_number = fields.Char(string="Reference Number")

    @api.model
    def create(self, vals):
        move = super().create(vals)
        if move.invoice_origin:
            sale_order = self.env['sale.order'].search(
                [('name', '=', move.invoice_origin)], limit=1
            )
            if sale_order:
                move.x_reference_number = sale_order.name
                move.x_invoice_type = sale_order.x_invoice_type or 'service'
        return move

    # ---------------------------------------------------------
    # BIR 2306 PDF GENERATION (CORRECTED ALIGNMENT)
    # ---------------------------------------------------------
    def action_generate_2306(self):
        self.ensure_one()

        template_path = get_resource_path(
            'itc_internal_dev', 
            'static/src/pdf', 
            'bir_2306.pdf'
        )
        if not template_path:
            raise UserError(_("BIR 2306 template not found."))

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        
        # Helper for TIN mapping based on the 12-box grid
        # spacing and group offsets adjusted for the 01/18 ENCS version
        def draw_tin_aligned(tin, x_start, y):
            clean = (tin or "").replace("-", "").replace(" ", "").ljust(12, " ")
            digit_spacing = 15.2  # Fine-tuned for the box width
            group_spacing = 5.5   # Space between the 3-digit groups
            
            for i, digit in enumerate(clean[:9]):
                group_offset = (i // 3) * group_spacing
                c.drawString(x_start + (i * digit_spacing) + group_offset, y, digit)
            
            # Branch Code (last 3 digits) start after the third group gap
            branch_start = x_start + (9 * digit_spacing) + (3 * group_spacing) + 2
            for i, digit in enumerate(clean[9:12]):
                c.drawString(branch_start + (i * digit_spacing), y, digit)

        # =========================================================
        # RE-CALIBRATED COORDINATES FOR 2307 01/18 ENCS
        # =========================================================
        
        # 1. Period (From and To) - Fixed overlap with labels
        c.setFont("Helvetica", 10)
        if self.invoice_date:
            from_date = self.invoice_date.replace(day=1).strftime('%m  %d  %Y')
            to_date = self.invoice_date.strftime('%m  %d  %Y')
            c.drawString(120, 502, from_date) # Moved slightly left and down
            c.drawString(345, 502, to_date)   # Moved slightly right and down

        # 2. Part I - Payee Information
        # TIN boxes
        draw_tin_aligned(self.partner_id.vat, 82, 706) # Adjusted x and y
        
        # Payee Name (Moved down to avoid overlapping "Payee's Name" label)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(82, 678, (self.partner_id.name or "").upper())
        
        # Registered Address
        c.setFont("Helvetica", 8)
        addr = f"{self.partner_id.street or ''} {self.partner_id.city or ''} {self.partner_id.state_id.name or ''}"
        lines = simpleSplit(addr, "Helvetica", 8, 380)
        for i, line in enumerate(lines[:2]):
            c.drawString(82, 656 - (i * 10), line)
        
        # ZIP Code
        c.drawString(525, 656, self.partner_id.zip or "")

        # 3. Part II - Payor Information
        # TIN boxes
        draw_tin_aligned(self.company_id.vat, 82, 615)
        
        # Payor Name
        c.setFont("Helvetica-Bold", 9)
        c.drawString(82, 588, (self.company_id.name or "").upper())
        
        # Registered Address
        comp_addr = f"{self.company_id.street or ''}, {self.company_id.city or ''}"
        c.setFont("Helvetica", 8)
        c.drawString(82, 566, comp_addr)
        
        # ZIP Code
        c.drawString(525, 566, self.company_id.zip or "")

        # 4. Part III - Table Data (ATC Section)
        # Your test showed WC160 mapping correctly, but alignment was off
        ATC_Y = 468 
        c.setFont("Helvetica", 9)
        
        atc = "WC160" if self.x_invoice_type == 'service' else "WC158"
        c.drawString(70, ATC_Y, atc)
        
        # Total Amount column (5th column)
        c.drawRightString(510, ATC_Y, f"{self.amount_untaxed:,.2f}")
        
        # Tax Withheld column (6th column)
        tax_withheld = abs(sum(self.line_ids.filtered(lambda l: l.tax_line_id).mapped('price_subtotal')))
        c.drawRightString(595, ATC_Y, f"{tax_withheld:,.2f}")

        # Total Rows (Bottom of table)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(510, 312, f"{self.amount_untaxed:,.2f}")
        c.drawRightString(595, 312, f"{tax_withheld:,.2f}")

        c.save()
        packet.seek(0)

        # (Merge logic remains the same as your previous working version)

        # MERGE LOGIC
        overlay_pdf = PdfReader(packet)
        template_pdf = PdfReader(template_path)
        writer = PdfWriter()
        
        page = template_pdf.pages[0]
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': f'BIR_2306_{self.name.replace("/", "_")}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }