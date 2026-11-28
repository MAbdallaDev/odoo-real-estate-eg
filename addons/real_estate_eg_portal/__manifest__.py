{
    "name": "Real Estate Installments (Egypt): Customer Portal API",
    "summary": "REST API for customers: available units, reservation requests, "
    "their contracts and installments",
    "version": "19.0.1.0.0",
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
    ],
    "installable": True,
}
