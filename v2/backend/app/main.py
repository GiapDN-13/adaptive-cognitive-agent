import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from app.api.routes_http import router as http_router
from app.api.routes_ws import websocket_endpoint
from app.config import settings
from app.deps import get_session_manager, init_managers


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_managers()

    # Initialize tool registry: builtins → meta-tools → persisted extensions
    from app.agent.builtin_tools import register_all_builtins
    from app.agent.extension_loader import load_all_extensions
    from app.agent.meta_tools import register_meta_tools
    from app.agent.tool_registry import tool_registry

    register_all_builtins(tool_registry)
    register_meta_tools(tool_registry)
    ext_summary = load_all_extensions()
    logging.getLogger(__name__).info(
        f"ToolRegistry ready: {tool_registry.count} tools registered "
        f"(runtime: {ext_summary['tools']} tools, {ext_summary['skills']} skills, {ext_summary['hooks']} hooks)"
    )

    # Khôi phục session từ container còn sống sau khi backend restart (sessions
    # in-memory bị mất mỗi lần restart → tránh lỗi 404 khi frontend giữ id cũ).
    try:
        from app.deps import get_session_manager as _gsm
        recovered = await _gsm().rehydrate()
        if recovered:
            logging.getLogger(__name__).info(f"Rehydrated {recovered} session(s) from running containers")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Session rehydrate skipped: {e}")

    cleanup_task = asyncio.create_task(_idle_cleanup_loop())

    yield

    cleanup_task.cancel()
    # KHÔNG destroy container khi shutdown: backend restart (đổi creds/code) rất
    # thường xuyên, mà xóa sandbox ở đây khiến session của user chết → lỗi 404
    # "container not found" liên tục. Để container sống; rehydrate() lúc khởi động
    # sẽ nhặt lại, và idle-cleanup (30') sẽ dọn cái thật sự bỏ hoang.
    # (Nếu cần dọn toàn bộ thủ công: docker rm -f $(docker ps -aq -f name=smartagent-).)


async def _idle_cleanup_loop():
    while True:
        await asyncio.sleep(300)
        sm = get_session_manager()
        cleaned = await sm.cleanup_idle()
        if cleaned:
            print(f"[cleanup] Removed {cleaned} idle sessions")


app = FastAPI(
    title="SmartAgent V2",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(http_router, prefix="/api")
app.add_api_websocket_route("/ws/{session_id}", websocket_endpoint)
