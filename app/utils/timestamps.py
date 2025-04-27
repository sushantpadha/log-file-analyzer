# from flask import current_app

def seconds_from_timestamp(timestamp):
    """Return number of seconds elapsed between `timestamp` wrt 0001-01-01 00:00:00"""
    timestamp = format_timestamp(timestamp)

    def to_seconds(tstmp):
        if not tstmp:
            return 0

        d, t = tstmp.split()
        yr, mo, day = map(int, d.split("-"))
        hr, mn, sc = map(int, t.split(":"))

        days_in_month = [
            31,
            28 + (1 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 0),
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ]

        # 1) days from all years before this one (leaps = (N-1)//4 - (N-1)//100 + (N-1)//400)
        years_prior = yr - 1
        leaps_prior = years_prior // 4 - years_prior // 100 + years_prior // 400
        days_prior_years = years_prior * 365 + leaps_prior

        # 2) days from all months earlier in this year
        days_prior_months = sum(days_in_month[: mo - 1])

        # 3) days before the current day
        days_prior_days = day - 1

        total_days = days_prior_years + days_prior_months + days_prior_days

        # 4) convert to seconds
        total_seconds = total_days * 86400 + hr * 3600 + mn * 60 + sc

        return total_seconds

    return to_seconds(timestamp)


def timestamp_from_seconds(total_seconds, pos=None):
    """Convert seconds since 0001-01-01 00:00:00 to YYYY-mm-DD HH:MM:SS (`pos` arg is for usage with `matplotlib.ticker.FuncFormatter`)"""
    total_seconds = int(total_seconds)
    days = total_seconds // 86400
    rem = total_seconds % 86400
    hr = rem // 3600
    rem %= 3600
    mn = rem // 60
    sc = rem % 60

    # 2) convert total days into year / month / day
    # start from year 1 and add year lengths until remaining days is within the year
    year = 1
    while True:
        is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        days_in_year = 366 if is_leap else 365
        if days < days_in_year:
            break
        days -= days_in_year
        year += 1

    days_in_month = [
        31,
        28 + (1 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 0),
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    month = 1
    for dim in days_in_month:
        if days < dim:
            break
        days -= dim
        month += 1

    day = days + 1

    return f"{year:04d}-{month:02d}-{day:02d} {hr:02d}:{mn:02d}:{sc:02d}"


def format_timestamp(csvTimestamp):
    _, mo, dt, t, yr = csvTimestamp.split(" ")

    month_map = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    month = month_map[mo]

    return f"{yr}-{month}-{dt} {t}"


def validate_datetime_str(datetime):
    """Check if dates are in correct format: YYYY-mm-DD HH:MM:SS"""
    try:
        date, t = datetime.split()

        yr, mo, dy = date.split("-")
        yr, mo, dy = int(yr), int(mo), int(dy)

        if not (1 <= mo <= 12):
            return False

        days_in_month = [
            31,
            28 + (1 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 0),
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ]

        if not (1 <= dy <= days_in_month[mo - 1]):
            return False

        hr, mi, se = list(map(int, t.split(":")))

        if not (0 <= hr < 24 and 0 <= mi < 60 and 0 <= se < 60):
            return False

        return True

    except Exception:
        return False
