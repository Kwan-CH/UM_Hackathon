import dateparser
from datetime import timedelta


def parse_time(user_time_str, timezone="Asia/Kuala_Lumpur"):
    if not user_time_str:
        return None

    return dateparser.parse(
        user_time_str,
        settings={
            "TIMEZONE": timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future"
        }
    )

def parse_time_with_inference(time_str, reference=None, timezone="Asia/Kuala_Lumpur"):
    if not time_str:
        return None
    
    settings = {
        "TIMEZONE": timezone,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future"
    }

    if reference:
        settings["RELATIVE_BASE"] = reference

    return dateparser.parse(time_str, settings=settings)

def infer_expiry(pickup_time, expiry_time=None, default_hours=2):
    if expiry_time:
        if pickup_time and expiry_time < pickup_time:
            return pickup_time + timedelta(hours=default_hours)
        return expiry_time

    if pickup_time:
        return pickup_time + timedelta(hours=default_hours)

    return None