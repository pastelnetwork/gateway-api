from fastapi import APIRouter

from app.api.api_v1.endpoints import login, users, account, api_keys, cascade, sense, nft, collection    #, utils

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(api_keys.router, prefix="/api_keys", tags=["api_keys"])

api_router.include_router(cascade.router, prefix="/cascade", tags=["cascade"])
api_router.include_router(sense.router, prefix="/sense", tags=["sense"])
api_router.include_router(nft.router, prefix="/nft", tags=["nft"])
api_router.include_router(collection.router, prefix="/collection", tags=["collection"])

# api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
