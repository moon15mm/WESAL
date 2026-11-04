"""Permission catalog and system role definitions (Role-Based Access Control).

Business-scoped roles are assigned through business memberships; platform roles
through user_roles. Businesses may also define custom roles composed of the
permissions of their scope."""
from __future__ import annotations

from app.models.enums import RoleScope

PERMISSIONS: dict[RoleScope, list[str]] = {
    RoleScope.platform: [
        "admin.dashboard", "admin.users.view", "admin.users.manage", "admin.businesses.verify",
        "admin.reps.verify", "admin.catalog.manage", "admin.orders.view", "admin.complaints.manage",
        "admin.commissions.view", "admin.subscriptions.manage", "admin.ads.manage", "admin.content.manage",
        "admin.translations.manage", "admin.settings.manage", "admin.audit.view", "admin.system.view",
        "admin.ratings.moderate", "admin.roles.manage", "admin.reports.view", "admin.data_requests.manage",
    ],
    RoleScope.retailer: [
        "retailer.orders.view", "retailer.orders.create", "retailer.orders.approve", "retailer.orders.cancel",
        "retailer.deliveries.confirm", "retailer.returns.manage", "retailer.branches.manage",
        "retailer.team.manage", "retailer.business.manage", "retailer.reports.view",
        "retailer.complaints.manage", "retailer.ratings.create",
    ],
    RoleScope.supplier: [
        "supplier.catalog.manage", "supplier.pricing.manage", "supplier.inventory.manage",
        "supplier.orders.view", "supplier.orders.manage", "supplier.fulfillment.manage",
        "supplier.returns.manage", "supplier.collections.manage", "supplier.customers.view",
        "supplier.customers.manage", "supplier.customers.source_change", "supplier.reps.manage",
        "supplier.commissions.view", "supplier.commissions.manage", "supplier.coverage.manage",
        "supplier.team.manage", "supplier.business.manage", "supplier.reports.view",
        "supplier.complaints.manage",
    ],
}

ALL_PERMISSIONS = {p: scope for scope, perms in PERMISSIONS.items() for p in perms}


def _all(scope: RoleScope) -> list[str]:
    return list(PERMISSIONS[scope])


SYSTEM_ROLES: list[dict] = [
    # platform
    {"code": "platform_admin", "scope": RoleScope.platform, "perms": _all(RoleScope.platform),
     "name": {"ar": "مدير المنصة", "en": "Platform administrator", "ur": "پلیٹ فارم منتظم", "hi": "प्लेटफ़ॉर्म व्यवस्थापक"}},
    {"code": "platform_support", "scope": RoleScope.platform,
     "perms": ["admin.dashboard", "admin.users.view", "admin.orders.view", "admin.complaints.manage",
               "admin.ratings.moderate", "admin.commissions.view", "admin.reports.view"],
     "name": {"ar": "الدعم والعمليات", "en": "Support & operations", "ur": "سپورٹ اور آپریشنز", "hi": "सहायता और संचालन"}},
    {"code": "platform_reviewer", "scope": RoleScope.platform,
     "perms": ["admin.dashboard", "admin.users.view", "admin.businesses.verify", "admin.reps.verify", "admin.catalog.manage"],
     "name": {"ar": "مراجع التوثيق", "en": "Verification reviewer", "ur": "تصدیقی جائزہ کار", "hi": "सत्यापन समीक्षक"}},
    # retailer
    {"code": "retailer_owner", "scope": RoleScope.retailer, "perms": _all(RoleScope.retailer),
     "name": {"ar": "مالك المحل", "en": "Store owner", "ur": "دکان کا مالک", "hi": "दुकान मालिक"}},
    {"code": "branch_manager", "scope": RoleScope.retailer,
     "perms": ["retailer.orders.view", "retailer.orders.create", "retailer.orders.approve", "retailer.orders.cancel",
               "retailer.deliveries.confirm", "retailer.returns.manage", "retailer.reports.view",
               "retailer.complaints.manage", "retailer.ratings.create"],
     "name": {"ar": "مدير فرع", "en": "Branch manager", "ur": "برانچ مینیجر", "hi": "शाखा प्रबंधक"}},
    {"code": "purchasing_officer", "scope": RoleScope.retailer,
     "perms": ["retailer.orders.view", "retailer.orders.create", "retailer.deliveries.confirm", "retailer.returns.manage"],
     "name": {"ar": "موظف مشتريات", "en": "Purchasing officer", "ur": "خریداری افسر", "hi": "क्रय अधिकारी"}},
    {"code": "retailer_accountant", "scope": RoleScope.retailer,
     "perms": ["retailer.orders.view", "retailer.reports.view"],
     "name": {"ar": "محاسب", "en": "Accountant", "ur": "اکاؤنٹنٹ", "hi": "लेखाकार"}},
    {"code": "store_staff", "scope": RoleScope.retailer,
     "perms": ["retailer.orders.view", "retailer.deliveries.confirm"],
     "name": {"ar": "موظف استلام", "en": "Receiving staff", "ur": "وصولی عملہ", "hi": "प्राप्ति कर्मचारी"}},
    # supplier
    {"code": "supplier_owner", "scope": RoleScope.supplier, "perms": _all(RoleScope.supplier),
     "name": {"ar": "مدير الشركة", "en": "Company manager", "ur": "کمپنی مینیجر", "hi": "कंपनी प्रबंधक"}},
    {"code": "sales_manager", "scope": RoleScope.supplier,
     "perms": ["supplier.orders.view", "supplier.orders.manage", "supplier.customers.view", "supplier.customers.manage",
               "supplier.customers.source_change", "supplier.reps.manage", "supplier.commissions.view",
               "supplier.pricing.manage", "supplier.reports.view", "supplier.complaints.manage", "supplier.returns.manage"],
     "name": {"ar": "مدير مبيعات", "en": "Sales manager", "ur": "سیلز مینیجر", "hi": "बिक्री प्रबंधक"}},
    {"code": "sales_supervisor", "scope": RoleScope.supplier,
     "perms": ["supplier.orders.view", "supplier.customers.view", "supplier.customers.manage", "supplier.reps.manage",
               "supplier.commissions.view", "supplier.reports.view"],
     "name": {"ar": "مشرف مندوبي المبيعات", "en": "Sales supervisor", "ur": "سیلز سپروائزر", "hi": "बिक्री पर्यवेक्षक"}},
    {"code": "inventory_officer", "scope": RoleScope.supplier,
     "perms": ["supplier.catalog.manage", "supplier.inventory.manage", "supplier.orders.view", "supplier.fulfillment.manage",
               "supplier.returns.manage"],
     "name": {"ar": "مسؤول مخزون", "en": "Inventory officer", "ur": "انوینٹری افسر", "hi": "इन्वेंटरी अधिकारी"}},
    {"code": "supplier_accountant", "scope": RoleScope.supplier,
     "perms": ["supplier.orders.view", "supplier.collections.manage", "supplier.commissions.view",
               "supplier.commissions.manage", "supplier.reports.view"],
     "name": {"ar": "محاسب", "en": "Accountant", "ur": "اکاؤنٹنٹ", "hi": "लेखाकार"}},
]

OWNER_ROLE = {RoleScope.retailer: "retailer_owner", RoleScope.supplier: "supplier_owner"}
# Accounts whose sessions are considered sensitive (shorter TTL, MFA strongly recommended / enforced)
SENSITIVE_ROLE_CODES = {"platform_admin", "platform_support", "platform_reviewer", "supplier_owner"}
