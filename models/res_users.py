from odoo import models, api

class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def create(self, vals):
        user = super().create(vals)

        # Automatically assign Helpdesk Manager group to new users
        group = self.env.ref("itc_internal_dev.group_helpdesk_manager", raise_if_not_found=False)
        if group and group.id not in user.groups_id.ids:
            user.groups_id = [(4, group.id)]

        return user
