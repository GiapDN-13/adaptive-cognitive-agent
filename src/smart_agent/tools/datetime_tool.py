from datetime import datetime, timezone, timedelta


def get_datetime(timezone_offset: int = 7) -> str:
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)
    return (
        f"Current date/time: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"(UTC{'+' if timezone_offset >= 0 else ''}{timezone_offset})\n"
        f"Day of week: {now.strftime('%A')}\n"
        f"ISO format: {now.isoformat()}"
    )
