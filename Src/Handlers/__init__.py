from aiogram import Router

def get_handlers_router() -> Router:
    from .Start import start_handler
    from .Booking import booking_handler

    router_main = Router()

    router_main.include_router(start_handler.router_start)
    router_main.include_router(booking_handler.router_booking)

    return router_main
