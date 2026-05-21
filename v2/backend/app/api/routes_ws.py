import json
import asyncio

from fastapi import WebSocket, WebSocketDisconnect, Depends

from app.deps import get_session_manager
from app.core.session_manager import SessionManager


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

    try:
        # Send session status + chat history on connect
        await websocket.send_json({
            "type": "session_status",
            "container_status": "running",
            "session_id": session_id,
        })

        if session.messages:
            await websocket.send_json({
                "type": "history_replay",
                "messages": session.messages[-50:],
            })

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            await sm.touch(session_id)

            if msg_type == "user_message":
                from app.agent.loop import run_agent_loop
                await run_agent_loop(
                    session=session,
                    user_message=message["content"],
                    ws_send=websocket.send_json,
                )

            elif msg_type == "approval_response":
                from app.agent.loop import handle_approval
                await handle_approval(session_id, message)

            elif msg_type == "user_response":
                from app.agent.loop import handle_user_response
                await handle_user_response(session_id, message["content"])

            elif msg_type == "cancel":
                from app.agent.loop import handle_cancel
                await handle_cancel(session_id)

            elif msg_type == "resource_update":
                from app.core.docker_manager import DockerManager
                from app.deps import _docker_manager
                if session.container_id:
                    mem = f"{message['memory_mb']}m"
                    await _docker_manager.update_resources(
                        session.container_id,
                        mem_limit=mem,
                        cpu_count=message.get("cpu", 1.0),
                    )
                    await websocket.send_json({
                        "type": "session_status",
                        "container_status": "running",
                        "resources_updated": True,
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "recoverable": False,
            })
        except Exception:
            pass
