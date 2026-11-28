{
    "name": "Real Estate Installments (Egypt): Customer Portal",
    "summary": "Customer portal pages and REST API: available units, reservation "
    "requests, their contracts and installments",
    "version": "19.0.1.2.0",
    "category": "Real Estate",
    "license": "LGPL-3",
    "author": "Mostafa Abdallah",
    "website": "https://github.com/MAbdallaDev/odoo-real-estate-eg",
    # US-15 (v1.1): customers are Odoo portal users (portal), the business
    # rules live in real_estate_eg.
    "depends": ["real_estate_eg", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "views/real_estate_reservation_views.xml",
        # US-17: photos, floor plan, description and plans offered.
        "views/real_estate_image_views.xml",
        # US-16: the customer's pages under /my/real-estate/.
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "real_estate_eg_portal/static/src/scss/portal.scss",
            "real_estate_eg_portal/static/src/js/**/*",
            "real_estate_eg_portal/static/src/xml/**/*",
        ],
    },
    "installable": True,
}
