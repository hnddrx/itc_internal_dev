from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import io
import base64
import logging
import xlsxwriter
import json
from datetime import date, datetime

_logger = logging.getLogger(__name__)

# -------------------------
# Constants for Selections
# -------------------------
REPORT_NAMES = [
    ('sales_subsidiary_journal_rr9', 'Sales Subsidiary Journal RR9'),
    ('sales_journal', 'Sales Subsidiary Journal'),
    ('purchase_subsidiary_journal_rr9', 'Purchase Subsiday Journal RR9'),
    ('purchase_journal', 'Purchase Subsidiary Journal'),
    ('general_ledger', 'General Ledger'),
    ('general_ledger_rr9', 'General Ledger RR9'),
    ('general_journal', 'General Journal'),
    ('general_journal_rr9', 'General Journal RR9'),
    ('disbursement_journal', 'Disbursment Subsidiary Journal'),
    ('cash_receipt_journal', 'Cash Receipt Journal'),
    ('ar_history', 'Account Receivable History'),
    ('ap_by_transaction_date', 'Account Payable by Transaction Date'),
    ('aging_ar', 'Aging of Account Receivable'),
    ('aging_ap', 'Aging of Accout Payable'),
    ('ap_history', 'AP History'),
    ('cancelled_sales_invoice_summary', 'Cancelled Sales Invoice Summary Report'),
    ('cash_collection_summary', 'Cash Collection Summary Report'),
    ('check_collection_summary', 'Check Collection Summary Report'),
    ('deferred_vat_schedule', 'Deferred Vat Schedule'),
    ('depreciation_schedule', 'Depreciation Schedule'),
    ('disbursement_summary_by_date', 'Disbursement Summary Report by Date'),
    ('disbursement_summary_by_series', 'Disbursment Summary Report By Series No.'),
    ('disbursement_summary_detailed', 'Disbursement Summary Report Detailed'),
    ('disbursement_summary', 'Disbursement Summary Report'),
    ('lapsing_schedule', 'Lapsing Schedule'),
    ('or_by_customer', 'Official Receipt Report By Customer'),
    ('or_by_sales_rep', 'Official Receipt Report By Sales Representative'),
    ('or_by_series', 'Official Receipt Report By Series Number'),
    ('or_linked_invoice', 'Official Receipt Report Linked With service Invoice'),
    ('or_summary', 'OR Summary'),
    ('summary_ap', 'Summary of Accounts Payable'),
    ('summary_outstanding_ar', 'Summary of outstanding account receivable'),
    ('summary_outstanding_ap', 'Summary of Accounts outstanding paybale'),
    ('summary_paid_ap', 'Summary of Paid accounts payable'),
    ('summary_released_disbursement', 'Summary of Released Disbursement'),
    ('trial_balance', 'Trial Balance'),
    ('unpaid_sales_invoice_summary', 'Unpaid Sales Invoice Summary Report'),
    ('form_1604e', 'Form 1604E Schedule'),
    ('map_summary', 'MAP Summary  List'),
    ('qap_summary', 'QAP Summary List'),
    ('sawt', 'SAWT'),
    ('semestral_suppliers', 'Semestral List of Regular Supplier'),
    ('vat_summary_purchase', 'Vat Summary List - Purchase'),
    ('vat_summary_sales', 'Vat Summary List - Sales'),
    ('vat_summary_importation', 'Vat Summary List Importation'),
    ('audit_logs', 'Audit Logs'),
    ('form_1900', 'Form 1900'),
    ('secretary_cert', 'Secretary Cert'),
]

REPORT_CATEGORIES = [
    ('annex', 'Annex'),
    ('books', 'Books'),
    ('other_reports', 'Other Reports'),
    ('tax_returns', 'Tax Returns Mandatory Attachments'),
    ('none', 'None'),
]

# -------------------------
# SQL Queries Mapping
# -------------------------
SQL_QUERIES = {
    'sales_subsidiary_journal_rr9': """
        SELECT 
            r.vat as "TIN",
            r."name" as "CUSTOMER CODE",
            r.complete_name as "CUSTOMER NAME",
            '' as "DESCRIPTION",
            a.name as "REFERENCE",
            a.amount_total as "AMOUNT",
            '' as "DISCOUNT",
            a.amount_tax as "VAT AMOUNT",
            abs(a.amount_total - a.amount_tax) as "NET SALES"
        FROM sale_order s
        INNER JOIN account_move a ON s.name = a.invoice_origin 
        LEFT JOIN res_partner r ON s.partner_id = r.id
        WHERE a.invoice_date BETWEEN %s AND %s;
    """,
    'sales_journal': """
        SELECT 
            a.invoice_date AS "DATE",
            r.name AS "NAME OF CLIENT",
            r.contact_address_complete AS "ADDRESS",
            r.vat AS "TIN",
            a.name AS "PRIMARY",
            a.ref AS "SUPPLIMENTARY",
            '' AS "OTHERS",
            a.amount_total_signed AS "GROSS AMOUNT",
            '' AS "DISCOUNT AMOUNT",
            s.amount_total AS "SALES AMOUNT",
            CASE WHEN s.x_invoice_type = 'consu' THEN s.amount_untaxed ELSE 0 END AS "GOODS",
            CASE WHEN s.x_invoice_type = 'service' THEN s.amount_untaxed ELSE 0 END AS "SERVICE",
            s.amount_untaxed AS "TOTAL UNTAXED",
            '' AS "PRIVATE",
            '' AS "GOVERNMENT",
            '' AS "TOTAL GOV/PRIVATE",
            '' AS "VATABLE",
            '' AS "ZERO RATED",
            '' AS "EXEMPT",
            ABS(s.amount_total - s.amount_tax) AS "TOTAL TAXABLE SALES",
            a.amount_tax AS "OUTPUT TAX TWELVE PERCENT",
            a.amount_total AS "SI/OR AMOUNT",
            '' AS "SEVER PERCENT STANDARD INPUT VAT",
            '' AS "BIR FORM VAT 2307",
            '' AS "BIR FORM EWT 2307"
        FROM sale_order s
        INNER JOIN account_move a ON s.name = a.invoice_origin 
        LEFT JOIN res_partner r ON s.partner_id = r.id
        WHERE a.invoice_date BETWEEN %s AND %s;
    """,
    'purchase_journal': """
        SELECT 
            a.invoice_date "TRANSACTION DATE",
            a.invoice_origin "AP NUMBER",
            '' "DV NUMBER",
            '' "OTHERS",
            r."name" "NAME OF PAYEE/SUPPLIER",
            r.contact_address_complete "ADDRESS",
            r.vat "TIN",
            p.date_order "REF DATE",
            a.name "PRIMARY",
            '' "SUPPLIMENTARY",
            '' "OTHERS",
            a.amount_total "GROSS AMOUNT",
            a.amount_tax "ACTUAL INPUT TAX TWELVE PERCENT",
            a.amount_untaxed "NET OF VAT",
            '' " CAPITAL GOODS (AGGREGATE NOT EXCEEDING 1M) ",
            '' " CAPITAL GOODS (AGGREGATE EXCEEDING 1M) ",
            '' " PURCHASE OTHER THAN CAPITAL GOODS ",
            '' " PURCHASE OTHER THAN CAPITAL GOODS ",
            '' "  DOMESTIC PURCHASE OF SERVICES ",
            '' " IMPORTATION PURCHASES ",
            '' " PURCHASE NOT QUALIFIED TO INPUT TAX ",
            '' " OTHERS ",
            '' "ACCOUNT TITLE ",
            '' "ATC",
            '' "RATE",
            '' " AMOUNT ",
            '' " ALLOWED INPUT TAX ",
            '' " DISALLOWED INPUT TAX ",
            '' " DEFFERED INPUT TAX "
        FROM purchase_order p 
        INNER JOIN account_move a ON p.name = a.invoice_origin 
        LEFT JOIN res_partner r ON p.partner_id = r.id
        WHERE a.invoice_date BETWEEN %s AND %s;
    """,
    'disbursement_journal': """
        SELECT 
            ap."date" "RELEASE DATE",
            he."date" "DATE",
            am.name "NUMBER",
            p.default_code  "TYPE",
            '' "NUM",
            he.payment_mode "PAYEE/SUPPLIER",
            he.x_particulars "PARTICULARS",
            '' "PRIMARY",
            '' "SUPPLEMENTARY",
            '' "OTHER REFERENCES",
            he.total_amount  "AMOUNT",
            '' "ZERO RATED",
            '' "EXEMP / NON - VAT",
            he.untaxed_amount_currency "VATABLE",
            he.tax_amount "INPUT TAX TWELVE PERCENT",
            he.total_amount "GROSS AMOUNT",
            CASE WHEN he.account_id IS NOT NULL THEN 'Y' ELSE NULL END "INPUT TAX ALLOWED?",
            he.untaxed_amount_currency "TAX BASE",
            '' "RATE",
            'TAX BASE * RATE'"AMOUNT",
            '' "EWT ABSORBED BY COMPANY?",
            '' " CV AMOUNT (CREDIT) ",
            p.default_code "ACCOUNT TITLE"
        FROM hr_expense he
        INNER JOIN hr_expense_sheet hes ON he.sheet_id = hes.id
        INNER JOIN account_payment ap ON hes.journal_id = ap.id
        INNER JOIN account_move am ON ap.move_id = am.id
        LEFT JOIN product_product p ON he.product_id = p.id
        WHERE he.date BETWEEN %s AND %s;
    """,
    
}


class SqlReport(models.Model):
    _name = 'custom.sql.report'
    _description = 'Custom SQL Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "generated_on desc"

    name = fields.Selection(REPORT_NAMES, string="Report Name", required=True, tracking=True)
    report_category = fields.Selection(REPORT_CATEGORIES, string="Report Category", required=True, tracking=True)

    generated_on = fields.Datetime("Generated On", tracking=True, store=True)
    generated_by = fields.Many2one('res.users', string="Generated By", tracking=True, store=True)

    exported_on = fields.Datetime("Exported On", tracking=True, store=True)
    exported_by = fields.Many2one('res.users', string="Exported By", tracking=True, store=True)

    description = fields.Text("Description")

    from_date = fields.Date("From Date", required=True)
    to_date = fields.Date("To Date", required=True)

    sql_query = fields.Text("SQL Query")
    result_ids = fields.One2many('custom.sql.report.line', 'report_id', string="Results")
    result_columns = fields.Text("Result Columns")  # JSON array

    _sql_constraints = [
        ('unique_report_name', 'unique(name)', 'Each report name must be unique!')
    ]

    def action_execute_query(self):
        self.ensure_one()

        if self.report_category not in ['books', 'annex', 'other_reports', 'tax_returns']:
            raise ValidationError("Please select a valid report category.")

        sql = SQL_QUERIES.get(self.name)
        if not sql:
            raise ValidationError("Please select a valid report.")

        try:
            self.env.cr.execute(sql, (self.from_date, self.to_date))
            columns = [desc[0] for desc in self.env.cr.description]
            rows = self.env.cr.fetchall()

            serializable_rows, row_html_parts = [], []
            for row in rows:
                row_dict, cells = {}, []
                for col, val in zip(columns, row):
                    if isinstance(val, (datetime, date)):
                        val = val.isoformat()
                    row_dict[col] = val
                    cells.append(f"<td style='width:200px;'>{val or ''}</td>")
                serializable_rows.append(row_dict)
                row_html_parts.append(f"<tr>{''.join(cells)}</tr>")

            table_html = f"""
                <table class="table table-sm table-bordered" style="width:100%; border-collapse: collapse;">
                    <thead>
                        <tr>{"".join(f"<th style='width:200px;'>{col}</th>" for col in columns)}</tr>
                    </thead>
                    <tbody>
                        {''.join(row_html_parts)}
                    </tbody>
                </table>
            """

            self.result_columns = json.dumps(columns)
            self.result_ids.unlink()
            self.env['custom.sql.report.line'].create({
                'report_id': self.id,
                'data': json.dumps(serializable_rows, ensure_ascii=False),
                'html_result': table_html,
            })

            self.generated_on = fields.Datetime.now()
            self.generated_by = self.env.user

        except Exception as e:
            raise UserError(f"Error executing query: {e}")

    def get_table_data(self):
        columns = json.loads(self.result_columns or "[]")
        rows = [json.loads(r.data) for r in self.result_ids]
        return columns, rows

    def action_export_excel(self):
        self.ensure_one()
        if not self.result_ids:
            raise UserError("No data to export. Execute a query first.")

        columns = json.loads(self.result_columns or "[]")
        rows = [item for r in self.result_ids for item in json.loads(r.data or "[]")]

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Report")

        # Formats
        bold_format = workbook.add_format({'bold': True})
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#ADD8E6',
            'border': 1, 'align': 'center',
            'valign': 'vcenter', 'text_wrap': True,
        })
        title_format = workbook.add_format({'bold': True, 'align': 'center'})
        small_format = workbook.add_format({'font_size': 9})
        cell_format = workbook.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})

        # Header Info
        worksheet.write("A1", "INNOVATHINK CORPORATION", bold_format)
        worksheet.write("A2", "4/F, Vista Mall IT Hub Alabang-Zapote Road corner C. V. Starr Avenue PhilAm Life Village, Pamplona 2 Las Pinas City", small_format)
        worksheet.write("A3", "TIN: 008-168-070-00000", small_format)
        worksheet.write("A5", dict(self._fields['name'].selection).get(self.name, self.name), title_format)
        worksheet.write("A6", f"Period Covered: {self.from_date.strftime('%m/%d/%Y')} - {self.to_date.strftime('%m/%d/%Y')}", small_format)

        worksheet.freeze_panes(7, 0)

        # Table Header
        start_row = 6
        for col, col_name in enumerate(columns):
            worksheet.write(start_row, col, col_name, header_format)
            worksheet.set_column(col, col, len(col_name) + 5)

        # Table Rows
        for row_idx, row in enumerate(rows, start=start_row + 1):
            for col_idx, col_name in enumerate(columns):
                worksheet.write(row_idx, col_idx, row.get(col_name, ""), cell_format)

        workbook.close()
        output.seek(0)

        file_data = base64.b64encode(output.read())
        filename = f"{self.name.replace(' ', '_')}.xlsx"

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        self.exported_on = fields.Datetime.now()
        self.exported_by = self.env.user

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }


class SqlReportLine(models.Model):
    _name = 'custom.sql.report.line'
    _description = 'Custom SQL Report Line'

    report_id = fields.Many2one('custom.sql.report', string="Report", ondelete="cascade")
    data = fields.Text("Row Data")  # JSON string
    html_result = fields.Html("Result")  # HTML table
