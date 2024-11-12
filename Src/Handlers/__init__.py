from aiogram import Router


def get_handlers_router() -> Router:

    from .Start import start_handler

    router_main = Router()

    router_main.include_router(start_handler.router_start)

    return router_main