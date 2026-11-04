"""Import all models so that Base.metadata is complete (Alembic autogenerate, tests)."""
from app.models.business import (  # noqa: F401
    Branch, Business, BusinessAddress, BusinessDocument, BusinessMember, City, CoverageArea, Region, StoredFile,
)
from app.models.catalog import (  # noqa: F401
    Brand, Category, PriceList, PriceListItem, PriceRule, Product, ProductUnit, SupplierProduct,
)
from app.models.commissions import (  # noqa: F401
    Commission, CommissionAdjustment, CommissionDispute, CommissionPayment,
)
from app.models.crm import (  # noqa: F401
    Customer, CustomerAcquisition, CustomerAssignment, CustomerContact, CustomerNote, CustomerSourceChange,
    Opportunity, Visit,
)
from app.models.identity import (  # noqa: F401
    Permission, Role, RolePermission, User, UserRole, UserSession, VerificationCode,
)
from app.models.orders import (  # noqa: F401
    Cart, CartItem, DeliveryConfirmation, DeliveryRecord, Order, OrderApproval, OrderCollection, OrderItem,
    OrderOffer, OrderOfferItem, OrderSequence, OrderStatusHistory, ReturnItem, ReturnRequest,
)
from app.models.reps import (  # noqa: F401
    Authorization, AuthorizationArea, AuthorizationHistory, AuthorizationProduct, CommissionAgreement,
    CommissionRule, Representative, RepresentativeArea, RepresentativeCategory, RepresentativeCompany,
    RepresentativeDocument, RepTarget, RepTask,
)
from app.models.system import (  # noqa: F401
    AdStatus, Advertisement, AIInteraction, AuditLog, Complaint, ComplaintMessage, ContactMessage, ContentPage,
    DataRequest, JobRun, Language, Notification, NotificationDelivery, NotificationPreference, PlatformSetting,
    PushSubscription, Rating, RatingReport, Subscription, SubscriptionPlan, TranslationOverride,
)
