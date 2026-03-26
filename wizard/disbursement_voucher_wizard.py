from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DisbursementVoucherWizard(models.TransientModel):
    _name = 'disbursement.voucher.wizard'
    _description = 'Disbursement Voucher Batch Action Wizard'

    action_type = fields.Selection([
        ('release', 'Release Selected Vouchers'),
        ('cancel', 'Cancel Selected Vouchers'),
    ], string='Action', required=True, default='release')

    notes = fields.Text(string='Notes / Remarks')
    voucher_ids = fields.Many2many(
        'disbursement.voucher', string='Vouchers',
        default=lambda self: self.env.context.get('active_ids', []),
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.voucher_ids:
            raise UserError(_('No vouchers selected.'))

        if self.action_type == 'release':
            for v in self.voucher_ids.filtered(lambda r: r.status == 'disbursement_entry'):
                v.action_release()
                if self.notes:
                    v.message_post(body=_('Batch release note: %s') % self.notes)
        elif self.action_type == 'cancel':
            for v in self.voucher_ids.filtered(lambda r: r.status != 'released'):
                v.action_cancel()
                if self.notes:
                    v.message_post(body=_('Batch cancel note: %s') % self.notes)

        return {'type': 'ir.actions.act_window_close'}
