"""Agricultural campaigns: twelve months from a first month (July for vines in Mendoza) to the month before it."""

from dataclasses import dataclass, field
from datetime import date, timedelta

MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class Month:
    key: str
    campaign: str
    start: date
    end: date


@dataclass(frozen=True)
class Campaign:
    label: str
    start: date
    end: date
    months: list[Month] = field(default_factory=list)


def add_months(day: date, count: int) -> date:
    """First day of the month `count` months after the month of `day`."""
    index = day.year * MONTHS_PER_YEAR + day.month - 1 + count
    return date(index // MONTHS_PER_YEAR, index % MONTHS_PER_YEAR + 1, 1)


def month_end(start: date) -> date:
    return add_months(start, 1) - timedelta(days=1)


def campaign_label(start_year: int) -> str:
    return f"{start_year}/{(start_year + 1) % 100:02d}"


def campaign_start_year(day: date, first_month: int) -> int:
    return day.year if day.month >= first_month else day.year - 1


def campaigns_until(today: date, first_month: int, count: int) -> list[Campaign]:
    """The campaign in progress plus the `count - 1` before it, oldest first. Months stop at today's month."""
    current = campaign_start_year(today, first_month)
    result = []
    for start_year in range(current - count + 1, current + 1):
        start = date(start_year, first_month, 1)
        label = campaign_label(start_year)
        months = []
        for offset in range(MONTHS_PER_YEAR):
            month_start = add_months(start, offset)
            if month_start > today:
                break
            months.append(Month(f"{month_start:%Y-%m}", label, month_start, month_end(month_start)))
        result.append(Campaign(label, start, month_end(add_months(start, MONTHS_PER_YEAR - 1)), months))
    return result


def all_months(campaigns: list[Campaign]) -> list[Month]:
    return [month for campaign in campaigns for month in campaign.months]


def is_complete(month: Month, processed_on: date, late_days: int) -> bool:
    """A month is final once it ended and the sources had `late_days` to publish its last scenes."""
    return processed_on > month.end + timedelta(days=late_days)
