"""Authorized file download. Public files (product images, logos, banners) are open;
private files require a relationship with the owning business/user or the order."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit_denied
from app.core.db import get_db, system_context
from app.core.deps import Principal, optional_principal
from app.core.errors import NotFound
from app.core.storage import file_path
from app.models.business import BusinessDocument, StoredFile
from app.models.enums import FilePurpose
from app.models.orders import DeliveryRecord, Order, OrderCollection, ReturnRequest
from app.models.reps import RepresentativeDocument
from app.models.system import Complaint

router = APIRouter(tags=["files"])


def _can_read(db: Session, principal: Principal | None, f: StoredFile) -> bool:
    if f.is_public:
        return True
    if principal is None:
        return False
    if principal.platform_perms:
        return True
    if f.owner_user_id == principal.id:
        return True
    bids = set(principal.business_ids())
    rep_id = principal.rep.id if principal.rep else None
    with system_context(db):
        if f.purpose in (FilePurpose.business_document,):
            return f.business_id in bids
        if f.purpose == FilePurpose.rep_document:
            doc = db.scalar(select(RepresentativeDocument).where(RepresentativeDocument.file_id == f.id))
            return bool(doc and rep_id and doc.representative_id == rep_id)
        order_ids = set()
        if f.purpose == FilePurpose.delivery_proof:
            order_ids |= set(db.scalars(select(DeliveryRecord.order_id).where(DeliveryRecord.proof_file_id == f.id)))
        if f.purpose == FilePurpose.invoice:
            order_ids |= set(db.scalars(select(Order.id).where(Order.invoice_file_id == f.id)))
        if f.purpose == FilePurpose.payment_proof:
            order_ids |= set(db.scalars(select(OrderCollection.order_id).where(OrderCollection.proof_file_id == f.id)))
            if f.business_id in bids:
                return True
        if f.purpose == FilePurpose.return_evidence:
            for r in db.scalars(select(ReturnRequest).where(ReturnRequest.evidence_file_ids.contains([str(f.id)]))):
                if r.retailer_id in bids or r.supplier_id in bids:
                    return True
        if f.purpose == FilePurpose.complaint_attachment:
            for c in db.scalars(select(Complaint).where(Complaint.attachment_file_ids.contains([str(f.id)]))):
                if c.raised_by_business_id in bids or c.against_business_id in bids or c.raised_by_user_id == principal.id \
                        or (rep_id and c.against_representative_id == rep_id):
                    return True
        for oid in order_ids:
            o = db.get(Order, oid)
            if o and (o.retailer_id in bids or o.supplier_id in bids or (rep_id and o.representative_id == rep_id)):
                return True
    return f.business_id in bids if f.business_id else False


@router.get("/files/{file_id}")
def download(file_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
             principal: Principal | None = Depends(optional_principal)):
    with system_context(db):
        f = db.get(StoredFile, file_id)
    if f is None:
        raise NotFound()
    if not _can_read(db, principal, f):
        audit_denied("file.read", actor_user_id=principal.id if principal else None, entity_type="file",
                     entity_id=file_id, request=request)
        raise NotFound()  # do not reveal existence
    path = file_path(f)
    if not path.exists():
        raise NotFound()
    headers = {"Cache-Control": "public, max-age=604800, immutable" if f.is_public else "private, no-store",
               "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"}
    disposition = "inline" if f.mime_type.startswith("image/") or f.mime_type == "application/pdf" else "attachment"
    return FileResponse(path, media_type=f.mime_type, headers=headers, filename=f.original_name,
                        content_disposition_type=disposition)
