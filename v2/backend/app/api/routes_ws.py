import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
):
    from app.deps import _session_manager
    sm = _session_manager

    session = await sm.get(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    await sm.touch(session_id)

    send_queue: asyncio.Queue = asyncio.Queue()
    agent_task: asyncio.Task | None = None

    async def ws_send(msg: dict):
        await send_queue.put(msg)

    async def sender_loop():
        try:
            while True:
                msg = await send_queue.get()
                await websocket.send_json(msg)
        except asyncio.CancelledError:
            pass

    async def ping_loop():
        try:
            while True:
                await asyncio.sleep(15)
                await send_queue.put({"type": "ping"})
        except asyncio.CancelledError:
            pass

    async def cancel_agent():
        nonlocal agent_task
        if agent_task and not agent_task.done():
            from app.agent.loop import handle_cancel
            await handle_cancel(session_id)
            agent_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(agent_task), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass
            agent_task = None

    async def receiver_loop():
        nonlocal agent_task
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")

                await sm.touch(session_id)

                if msg_type == "user_message":
                    logger.info(f"[{session_id[:8]}] user_message: {message['content'][:50]}")
                    await cancel_agent()
                    from app.agent.loop import run_agent_loop
                    agent_task = asyncio.create_task(
                        run_agent_loop(
                            session=session,
                            user_message=message["content"],
                            ws_send=ws_send,
                        )
                    )

                elif msg_type == "approval_response":
                    from app.agent.loop import handle_approval
                    await handle_approval(session_id, message)

                elif msg_type == "user_response":
                    from app.agent.loop import handle_user_response
                    await handle_user_response(session_id, message["content"])

                elif msg_type == "cancel":
                    await cancel_agent()
                    await ws_send({"type": "agent_message", "content": "Đã hủy.", "metadata": None})

                elif msg_type == "resource_update":
                    from app.deps import _docker_manager
                    if session.container_id:
                        mem = f"{message['memory_mb']}m"
                        await _docker_manager.update_resources(
                            session.container_id,
                            mem_limit=mem,
                            cpu_count=message.get("cpu", 1.0),
                        )
                        await ws_send({
                            "type": "session_status",
                            "container_status": "running",
                            "resources_updated": True,
                        })
        except WebSocketDisconnect:
            pass

    # Send initial status
    await ws_send({
        "type": "session_status",
        "container_status": "running",
        "session_id": session_id,
    })

    # Replay lịch sử chat khi (re)connect. Ưu tiên in-memory; nếu rỗng (vd backend
    # vừa restart + rehydrate từ container còn sống) thì đọc từ persistence để
    # không mất context khi user reload/nối lại tab.
    replay_messages = session.messages
    if not replay_messages:
        try:
            from app.core.persistence import load_session_messages
            replay_messages = await load_session_messages(session_id)
            # Nạp lại vào session in-memory để AGENT (không chỉ frontend) có context.
            # Nếu chỉ replay cho UI mà bỏ trống session.messages, agent sẽ hỏi
            # "tiếp tục cái gì" khi user gõ 'Tiếp tục'.
            if replay_messages:
                session.messages = list(replay_messages)
        except Exception:
            replay_messages = []
    if replay_messages:
        await ws_send({
            "type": "history_replay",
            "messages": replay_messages[-50:],
        })

    sender_task = asyncio.create_task(sender_loop())
    ping_task = asyncio.create_task(ping_loop())

    try:
        await receiver_loop()
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "recoverable": False,
            })
        except Exception:
            pass
    finally:
        await cancel_agent()
        ping_task.cancel()
        sender_task.cancel()
        await asyncio.gather(sender_task, ping_task, return_exceptions=True)
