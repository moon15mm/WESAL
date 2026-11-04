"""CRM helpers shared by orders/visits: keep customer records & acquisition source in sync."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import system_context
from app.core.utils import utcnow
from app.models.business import Branch, Business
from app.models.crm import Customer, CustomerAcquisition
from app.models.enums import AcquisitionSource, CustomerStatus, OrderChannel
from app.models.orders import Order


@dataclass
class Owner:
    supplier_id: uuid.UUID | None = None
    rep_id: uuid.UUID | None = None

    def filter(self):
        if self.supplier_id:
            return Customer.owner_supplier_id == self.supplier_id
        return Customer.owner_representative_id == self.rep_id

    def kwargs(self) -> dict:
        return {"owner_supplier_id": self.supplier_id, "owner_representative_id": self.rep_id}


def ensure_customer(db: Session, owner: Owner, retailer: Business, *, source: AcquisitionSource, created_by=None,
                    branch: Branch | None = None) -> Customer:
    c = db.scalar(select(Customer).where(owner.filter(), Customer.retailer_id == retailer.id))
    if c:
        return c
    branch = branch or next((b for b in retailer.branches if b.is_primary), None)
    c = Customer(**owner.kwargs(), retailer_id=retailer.id, branch_id=branch.id if branch else None,
                 name=retailer.trade_name_ar, phone=retailer.phone, email=retailer.email,
                 city_id=(branch.city_id if branch else None) or retailer.city_id,
                 district=branch.district if branch else None, address_line=branch.address_line if branch else None,
                 lat=branch.lat if branch else None, lng=branch.lng if branch else None,
                 status=CustomerStatus.prospect, source=source, created_by=created_by)
    db.add(c)
    db.flush()
    return c


def record_order_relationship(db: Session, order: Order) -> None:
    """Called when an order is approved: acquisition source (first order) + CRM stats."""
    with system_context(db):
        retailer = db.get(Business, order.retailer_id)
        acq = db.scalar(select(CustomerAcquisition).where(CustomerAcquisition.supplier_id == order.supplier_id,
                                                          CustomerAcquisition.retailer_id == order.retailer_id))
        if acq is None:
            source = AcquisitionSource.rep_visit if order.channel == OrderChannel.representative else AcquisitionSource.marketplace
            # a prior CRM lead created by a rep for this supplier takes precedence
            lead = db.scalar(select(Customer).where(Customer.owner_supplier_id == order.supplier_id,
                                                    Customer.retailer_id == order.retailer_id))
            if lead and lead.source in (AcquisitionSource.rep_invite, AcquisitionSource.supplier_import, AcquisitionSource.referral):
                source = lead.source
            db.add(CustomerAcquisition(supplier_id=order.supplier_id, retailer_id=order.retailer_id,
                                       representative_id=order.representative_id, source=source, first_order_id=order.id,
                                       recorded_by=order.created_by_user_id))
        owners = [Owner(supplier_id=order.supplier_id)]
        if order.representative_id:
            owners.append(Owner(rep_id=order.representative_id))
        for owner in owners:
            src = AcquisitionSource.rep_visit if order.channel == OrderChannel.representative else AcquisitionSource.marketplace
            c = ensure_customer(db, owner, retailer, source=src, branch=order.branch)
            c.status = CustomerStatus.active
            c.last_order_at = utcnow()
            c.orders_count = (c.orders_count or 0) + 1
            c.total_sales = (c.total_sales or 0) + order.total
            if order.representative_id and owner.supplier_id and not c.assigned_representative_id:
                c.assigned_representative_id = order.representative_id
