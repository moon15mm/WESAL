"""Domain enumerations. Stored as VARCHAR + CHECK constraints (non-native enums)
so new values can be added with a simple migration."""
from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def db_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=40,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class UserStatus(StrEnum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class VerificationPurpose(StrEnum):
    verify_email = "verify_email"
    verify_phone = "verify_phone"
    reset_password = "reset_password"
    login_otp = "login_otp"
    order_approval = "order_approval"


class Channel(StrEnum):
    in_app = "in_app"
    email = "email"
    sms = "sms"
    push = "push"
    whatsapp = "whatsapp"


class RoleScope(StrEnum):
    platform = "platform"
    retailer = "retailer"
    supplier = "supplier"


class BusinessType(StrEnum):
    retailer = "retailer"
    supplier = "supplier"


class VerificationStatus(StrEnum):
    unverified = "unverified"
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class BusinessStatus(StrEnum):
    active = "active"
    suspended = "suspended"
    closed = "closed"


class MemberStatus(StrEnum):
    invited = "invited"
    active = "active"
    disabled = "disabled"


class DocumentStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class FilePurpose(StrEnum):
    product_image = "product_image"
    business_logo = "business_logo"
    business_document = "business_document"
    rep_document = "rep_document"
    avatar = "avatar"
    delivery_proof = "delivery_proof"
    return_evidence = "return_evidence"
    payment_proof = "payment_proof"
    invoice = "invoice"
    ad_banner = "ad_banner"
    complaint_attachment = "complaint_attachment"


class Availability(StrEnum):
    in_stock = "in_stock"
    low_stock = "low_stock"
    out_of_stock = "out_of_stock"
    discontinued = "discontinued"


class ProductStatus(StrEnum):
    active = "active"
    pending_review = "pending_review"
    rejected = "rejected"
    archived = "archived"


class SaleUnit(StrEnum):
    piece = "piece"
    carton = "carton"


class PriceListType(StrEnum):
    default = "default"
    customer = "customer"
    region = "region"


class PromotionKind(StrEnum):
    percent = "percent"  # % off unit price
    fixed = "fixed"  # fixed SAR off per unit
    quantity_tier = "quantity_tier"  # % off when qty >= min_qty


class RepKind(StrEnum):
    independent = "independent"
    company = "company"


class RepAvailability(StrEnum):
    available = "available"
    limited = "limited"
    unavailable = "unavailable"


class RepCompanyRelation(StrEnum):
    employee = "employee"
    partner = "partner"


class RepCompanyStatus(StrEnum):
    active = "active"
    ended = "ended"


class AuthorizationStatus(StrEnum):
    draft = "draft"
    sent = "sent"  # requested by representative, awaiting company
    pending_rep = "pending_rep"  # terms issued by company, awaiting representative acceptance
    active = "active"
    suspended = "suspended"
    expired = "expired"
    cancelled = "cancelled"


class AuthorizationType(StrEnum):
    full_sales = "full_sales"  # promote + take orders
    order_taking = "order_taking"
    promotion_only = "promotion_only"  # visits/marketing only, cannot create orders


class CommissionBasis(StrEnum):
    percent = "percent"
    fixed_per_order = "fixed_per_order"
    per_unit = "per_unit"


class CommissionScope(StrEnum):
    all = "all"
    product = "product"
    category = "category"
    brand = "brand"


class CustomerStatus(StrEnum):
    lead = "lead"
    prospect = "prospect"
    active = "active"
    inactive = "inactive"
    lost = "lost"


class AcquisitionSource(StrEnum):
    rep_visit = "rep_visit"
    rep_invite = "rep_invite"
    direct_signup = "direct_signup"
    marketplace = "marketplace"
    supplier_import = "supplier_import"
    referral = "referral"


class OpportunityStage(StrEnum):
    open = "open"
    negotiation = "negotiation"
    won = "won"
    lost = "lost"


class VisitStatus(StrEnum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    missed = "missed"


class VisitPurpose(StrEnum):
    introduction = "introduction"
    order_taking = "order_taking"
    follow_up = "follow_up"
    promotion = "promotion"
    collection = "collection"
    complaint = "complaint"
    other = "other"


class VisitOutcome(StrEnum):
    order_created = "order_created"
    interested = "interested"
    follow_up_needed = "follow_up_needed"
    not_interested = "not_interested"
    decision_maker_absent = "decision_maker_absent"
    closed = "closed"


class OrderChannel(StrEnum):
    direct = "direct"
    representative = "representative"


class OrderStatus(StrEnum):
    draft = "draft"
    pending_retailer_approval = "pending_retailer_approval"
    new = "new"
    supplier_review = "supplier_review"
    quoted = "quoted"
    awaiting_retailer_approval = "awaiting_retailer_approval"
    approved = "approved"
    preparing = "preparing"
    ready = "ready"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    completed = "completed"
    rejected = "rejected"
    cancelled = "cancelled"
    partially_returned = "partially_returned"
    fully_returned = "fully_returned"
    disputed = "disputed"


class PaymentStatus(StrEnum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"


class ApprovalDecision(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    changes_requested = "changes_requested"
    superseded = "superseded"


class ApprovalMethod(StrEnum):
    session = "session"  # authenticated session + explicit confirmation
    password = "password"
    otp = "otp"


class OfferStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"
    expired = "expired"


class DeliveryStatus(StrEnum):
    pending = "pending"
    preparing = "preparing"
    ready = "ready"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    failed = "failed"


class ReturnStatus(StrEnum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    received = "received"
    settled = "settled"
    cancelled = "cancelled"


class CommissionStatus(StrEnum):
    estimated = "estimated"
    pending = "pending"
    due = "due"
    approved = "approved"
    paid = "paid"
    disputed = "disputed"
    adjusted = "adjusted"
    cancelled = "cancelled"


class DisputeStatus(StrEnum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    rejected = "rejected"


class RatingTarget(StrEnum):
    representative = "representative"
    supplier = "supplier"


class RatingStatus(StrEnum):
    published = "published"
    flagged = "flagged"
    hidden = "hidden"


class ComplaintKind(StrEnum):
    complaint = "complaint"
    order_dispute = "order_dispute"


class ComplaintStatus(StrEnum):
    open = "open"
    in_review = "in_review"
    awaiting_response = "awaiting_response"
    resolved = "resolved"
    rejected = "rejected"
    closed = "closed"


class ComplaintCategory(StrEnum):
    delivery = "delivery"
    product_quality = "product_quality"
    pricing = "pricing"
    representative_conduct = "representative_conduct"
    payment = "payment"
    account = "account"
    other = "other"


class Priority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class OutboxStatus(StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class SubscriptionStatus(StrEnum):
    trial = "trial"
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"


class AdStatus(StrEnum):
    draft = "draft"
    active = "active"
    paused = "paused"
    ended = "ended"


class TaskStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class DataRequestKind(StrEnum):
    export = "export"
    deletion = "deletion"


class DataRequestStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"
