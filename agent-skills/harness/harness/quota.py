"""Wait for the reset time that the QUOTA line of a run names."""
import re
import sys
import time
from datetime import datetime, timedelta, timezone

_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\s*(UTC|Z)?\.?$", re.I)
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})\s*([AP]M)\s*(UTC)?\.?$", re.I)
# A clock time with no date that passed less than this long ago is taken as reached, not as tomorrow's.
_REACHED_WITHIN = timedelta(hours=6)


def parse_reset(text, now):
    """Return the aware datetime the text names, or None when it is not a form read without guessing.

    Reads `YYYY-MM-DD HH:MM[:SS]` and `H:MM AM|PM`, each with an optional `UTC` and a final dot, and an
    optional `resets at ` before them. Without `UTC` the time is in the zone of `now`, which is the local one. The result may be in the past.
    """
    text = text.strip()
    if text.lower().startswith("resets at "):
        text = text[len("resets at "):].strip()
    local = now.tzinfo
    try:
        match = _DATE.match(text)
        if match:
            year, month, day, hour, minute, second, utc = match.groups()
            return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second or 0),
                            tzinfo=timezone.utc if utc else local)
        match = _CLOCK.match(text)
        if match:
            hour, minute, half, utc = match.groups()
            if not 1 <= int(hour) <= 12:
                return None
            hour = int(hour) % 12 + (12 if half.upper() == "PM" else 0)
            zone = timezone.utc if utc else local
            moment = now.astimezone(zone).replace(hour=hour, minute=int(minute), second=0, microsecond=0)
            if moment <= now and now - moment > _REACHED_WITHIN:
                moment += timedelta(days=1)
            return moment
    except ValueError:
        return None
    return None


def wait_for_reset(text, margin, now=None, sleep=time.sleep, clock=time.time):
    """Sleep until the named time plus `margin` seconds. Return 0, or 2 when the text is not understood."""
    start = now or datetime.now().astimezone()
    moment = parse_reset(text, start)
    if moment is None:
        print("quota-wait: cannot read a time from {0!r}; work it out by hand and wake once, "
              "at that time plus {1} seconds".format(text, margin), file=sys.stderr)
        return 2
    target = moment.timestamp() + margin
    print("quota-wait: waiting until {0}".format(
        datetime.fromtimestamp(target).astimezone().strftime("%Y-%m-%d %H:%M:%S")), file=sys.stderr)
    # Re-check the wall clock every pass so a sleeping laptop does not oversleep or undersleep.
    while True:
        remaining = target - clock()
        if remaining <= 0:
            return 0
        sleep(min(remaining, 30))
