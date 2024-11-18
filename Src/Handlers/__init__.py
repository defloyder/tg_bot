from aiogram import Router

def get_handlers_router() -> Router:
    from .Start import start_handler
    from .Booking import booking_handler
    from .Admin import admin_handler
    from .Master import master_handler
    from .MyBookings import my_bookings_handler


    router_main = Router()

    router_main.include_router(start_handler.router_start)
    router_main.include_router(booking_handler.router_booking)
    router_main.include_router(admin_handler.router_admin)
    router_main.include_router(master_handler.router_master)
    router_main.include_router(my_bookings_handler.router_bookings)


    return router_main
