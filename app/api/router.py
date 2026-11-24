"""汇总所有业务路由。"""
from fastapi import APIRouter

from app.api import auth, cart, orders, products, tickets

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(tickets.router)
