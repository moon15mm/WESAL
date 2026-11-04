"""Central list of API routers (one per module)."""
from app.modules.admin.router import router as admin_router
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.complaints.router import router as complaints_router
from app.modules.notifications.router import router as notifications_router
from app.modules.privacy.router import router as privacy_router
from app.modules.ratings.router import router as ratings_router
from app.modules.reports.router import router as reports_router
from app.modules.authorizations.router import router as authorizations_router
from app.modules.businesses.router import router as business_router
from app.modules.catalog.router import router as catalog_router
from app.modules.commissions.router import router as commissions_router
from app.modules.crm.router import router as crm_router
from app.modules.files.router import router as files_router
from app.modules.orders.router import router as orders_router
from app.modules.public.health import router as health_router
from app.modules.public.router import public as public_router
from app.modules.public.router import router as ref_router
from app.modules.reps.router import router as reps_router
from app.modules.returns.router import router as returns_router
from app.modules.visits.router import router as visits_router

ROUTERS = [health_router, ref_router, public_router, auth_router, business_router, files_router, catalog_router,
           reps_router, authorizations_router, crm_router, visits_router, orders_router, returns_router, commissions_router,
           ratings_router, complaints_router, notifications_router, reports_router, ai_router, admin_router, privacy_router]
