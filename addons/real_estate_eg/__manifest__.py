{
    "name": "Real Estate Installments (Egypt)",
    "summary": "Installment sales and collections for Egyptian real-estate developers",
    "version": "19.0.1.1.0",
    "category": "Real Estate",
    "license": "LGPL-3",
    "author": "Mostafa Abdallah",
    "website": "https://github.com/MAbdallaDev/odoo-real-estate-eg",
    # Odoo Apps listing cover; the page is static/description/index.html.
    "images": ["static/description/contracts.png"],
    "depends": ["account", "mail"],
    # US-08: .xlsx import; already in Odoo's own requirements.
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "data/ir_sequence_data.xml",
        "data/product_data.xml",
        "data/ir_cron_data.xml",
        "data/real_estate_reservation_data.xml",
        "views/real_estate_project_views.xml",
        "views/real_estate_unit_views.xml",
        "views/real_estate_plan_template_views.xml",
        "views/res_partner_views.xml",
        "views/real_estate_contract_views.xml",
        "views/real_estate_installment_views.xml",
        "views/real_estate_cheque_views.xml",
        "views/real_estate_reservation_views.xml",
        "wizard/real_estate_contract_cancel_views.xml",
        "wizard/real_estate_schedule_generate_views.xml",
        "wizard/real_estate_unit_import_views.xml",
        "views/res_config_settings_views.xml",
        "views/real_estate_menus.xml",
        "report/real_estate_contract_report.xml",
        "report/real_estate_contract_templates.xml",
    ],
    # S10.1: Nile Heights Developments (Chapter 6); never used by the tests.
    "demo": ["demo/real_estate_demo.xml"],
    "assets": {
        # BR-38: the contract report's CSS, in the bundle every PDF report
        # loads (as account adds report_invoice.css).
        "web.report_assets_common": [
            "real_estate_eg/static/src/css/contract_report.css",
        ],
    },
    "installable": True,
    "application": True,
}
