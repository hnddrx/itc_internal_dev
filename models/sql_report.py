from odoo import models, fields, api
from odoo.exceptions import UserError
import psycopg2

class SqlReport(models.Model):
    _name = 'custom.sql.report'
    _description = 'Custom SQL Report'

    name = fields.Char("Report Name", required=True)
    module_id = fields.Many2one('ir.module.module', string="Module")
    sql_query = fields.Text("SQL Query", required=True)
    result_ids = fields.One2many('custom.sql.report.line', 'report_id', string="Results")

    def action_execute_query(self):
        self.ensure_one()
        try:
            self.env.cr.execute(self.sql_query)
            columns = [desc[0] for desc in self.env.cr.description]
            rows = self.env.cr.fetchall()

            # Clear previous results
            self.result_ids.unlink()

            # Save results
            for row in rows:
                values = dict(zip(columns, row))
                self.env['custom.sql.report.line'].create({
                    'report_id': self.id,
                    'data': values,
                })
        except Exception as e:
            raise UserError(f"Error executing query: {str(e)}")


class SqlReportLine(models.Model):
    _name = 'custom.sql.report.line'
    _description = 'Custom SQL Report Line'

    report_id = fields.Many2one('custom.sql.report', string="Report")
    data = fields.Json("Row Data")  # stores as JSON/dict
