from aiogram import Router

from .start import router as start_router
from .help import router as help_router
from .link import router as link_router
from .profile import router as profile_router
from .upgrade import router as upgrade_router
from .war_history import router as war_router


def setup_routers() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(profile_router)
    router.include_router(link_router)
    router.include_router(help_router)
    router.include_router(upgrade_router)
    router.include_router(war_router)
    return router
