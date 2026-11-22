{
    "name": "Real Estate Installments (Egypt)",
    "summary": "Installment sales and collections for Egyptian real-estate developers",
    "version": "19.0.1.0.0",
    "category": "Real Estate",
    "license": "LGPL-3",
    "author": "Mostafa Abdallah",
    "website": "https://github.com/MAbdallaDev/odoo-real-estate-eg",
    "depends": ["account", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/real_estate_project_views.xml",
        "views/real_estate_menus.xml",
    ],
    "installable": True,
    "application": True,
}
