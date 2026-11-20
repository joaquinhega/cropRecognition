from datetime import date

from cultivos.modules.campaigns import add_months, all_months, campaigns_until, is_complete

JULY = 7


def test_current_campaign_plus_three_previous_until_today():
    campaigns = campaigns_until(date(2026, 11, 19), JULY, 4)
    assert [campaign.label for campaign in campaigns] == ["2023/24", "2024/25", "2025/26", "2026/27"]
    assert campaigns[0].months[0].key == "2023-07"
    assert campaigns[2].months[-1].key == "2026-06"
    assert [month.key for month in campaigns[3].months] == ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
    assert len(all_months(campaigns)) == 41


def test_before_july_the_campaign_started_the_previous_year():
    campaigns = campaigns_until(date(2026, 3, 2), JULY, 1)
    assert campaigns[0].label == "2025/26"
    assert campaigns[0].end == date(2026, 6, 30)
    assert campaigns[0].months[-1].key == "2026-03"


def test_month_arithmetic_crosses_the_year():
    assert add_months(date(2025, 11, 20), 3) == date(2026, 2, 1)


def test_a_month_is_final_some_days_after_it_ends():
    september = campaigns_until(date(2026, 10, 15), JULY, 1)[0].months[2]
    assert september.end == date(2026, 9, 30)
    assert not is_complete(september, date(2026, 10, 5), late_days=5)
    assert is_complete(september, date(2026, 10, 6), late_days=5)
