from odoo import models
from io import BytesIO
import base64

class GlobalReportXlsx(models.AbstractModel):
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        """Global header before every report"""
        sheet = workbook.add_worksheet("Report")

        company = self.env.company

        bold = workbook.add_format({'bold': True})
        small = workbook.add_format({'font_size': 9})

        # ==========================================
        # GLOBAL COMPANY DETAILS FOR ALL XLS REPORTS
        # ==========================================
        sheet.write(0, 0, company.name or "", bold)
        sheet.write(1, 0, company.partner_id.contact_address or "", small)
        sheet.write(2, 0, f"TIN: {company.vat or ''}", small)
        sheet.write(3, 0, f"Phone: {company.phone or ''}", small)
        sheet.write(4, 0, f"Email: {company.email or ''}", small)

        # Optional Custom Compliance Fields
        #sheet.write(5, 0, f"Acknowledgment Certificate No.: {company.acknowledgment_certificate_no or ''}", small)
        #sheet.write(6, 0, f"Acknowledgment Certificate Date Issued: {company.acknowledgment_certificate_date or ''}", small)
        #sheet.write(7, 0, f"Permitted Series Range: {company.permitted_series_from or ''} - {company.permitted_series_to or ''}", small)

        # Leave space before original content
        self._row_start = 9  # New attribute for child classes

        # ==========================================
        # CONTINUE NORMAL PROCESS (call original)
        # ==========================================
        return super(GlobalReportXlsx, self).generate_xlsx_report(workbook, data, objs)
