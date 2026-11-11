from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class DateRangeResult:
    period: str
    start_date_ist: date
    end_date_ist: date
    start_utc: datetime
    end_utc_exclusive: datetime
    timezone: str = "Asia/Kolkata"


def resolve_date_range(
    period: Optional[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    reference_now_utc: Optional[datetime] = None,
) -> DateRangeResult:
    """Resolve relative or explicit calendar periods in Asia/Kolkata to half-open UTC intervals [start, end)."""
    now_utc = reference_now_utc or datetime.now(timezone.utc)
    ist_today = now_utc.astimezone(IST).date()

    resolved_period = period or ("custom" if (start_date and end_date) else "last_30_days")

    if resolved_period == "last_month":
        first_of_this_month = ist_today.replace(day=1)
        end_d = first_of_this_month - timedelta(days=1)
        start_d = end_d.replace(day=1)
    elif resolved_period == "this_month":
        start_d = ist_today.replace(day=1)
        end_d = ist_today
    elif resolved_period == "today":
        start_d = ist_today
        end_d = ist_today
    elif resolved_period == "yesterday":
        start_d = ist_today - timedelta(days=1)
        end_d = start_d
    elif resolved_period == "last_7_days":
        start_d = ist_today - timedelta(days=6)
        end_d = ist_today
    elif resolved_period == "last_30_days":
        start_d = ist_today - timedelta(days=29)
        end_d = ist_today
    elif resolved_period == "last_90_days":
        start_d = ist_today - timedelta(days=89)
        end_d = ist_today
    elif resolved_period == "custom":
        if start_date is None or end_date is None:
            raise ValueError("Both start_date and end_date are required for custom date ranges")
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        start_d = start_date
        end_d = end_date
    else:
        raise ValueError(f"Unsupported date period: {resolved_period}")

    start_ist_dt = datetime.combine(start_d, time.min, tzinfo=IST)
    end_ist_exclusive_dt = datetime.combine(end_d + timedelta(days=1), time.min, tzinfo=IST)

    return DateRangeResult(
        period=resolved_period,
        start_date_ist=start_d,
        end_date_ist=end_d,
        start_utc=start_ist_dt.astimezone(timezone.utc),
        end_utc_exclusive=end_ist_exclusive_dt.astimezone(timezone.utc),
    )


def resolve_expiry_window(
    days: int = 30,
    reference_now_utc: Optional[datetime] = None,
) -> tuple[date, date]:
    """Return inclusive [today_ist, today_ist + days] expiry window in Asia/Kolkata."""
    now_utc = reference_now_utc or datetime.now(timezone.utc)
    ist_today = now_utc.astimezone(IST).date()
    return ist_today, ist_today + timedelta(days=days)

