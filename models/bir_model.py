from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import base64
import calendar


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
