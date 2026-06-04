import os
from datetime import datetime, timedelta

import pandas as pd
import requests

TURNOVERS_URL = "https://iss.moex.com/iss/engines/futures/turnovers.json"

def main():
    start_date = "2015-01-01"
    end_date = "2021-12-31"

    daily_df = collect_daily_turnovers(start_date, end_date)
    monthly_df = build_monthly_table(daily_df)
    quarterly_df = build_quarterly_table(daily_df)
    yearly_df = build_yearly_table(daily_df)

    save_outputs(start_date, end_date, daily_df, monthly_df, quarterly_df, yearly_df)
    print_quality_checks(daily_df, monthly_df, quarterly_df, yearly_df)

def generate_calendar_dates(start_date, end_date):
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    current_date = start_dt

    while current_date <= end_dt:
        yield current_date.isoformat()
        current_date += timedelta(days=1)

def get_futures_engine_turnovers_day(trade_date):
    params = {"date": trade_date}
    response = requests.get(TURNOVERS_URL, params=params)
    response.raise_for_status()
    data = response.json()

    columns = data["turnovers"]["columns"]
    rows = data["turnovers"]["data"]
    day_df = pd.DataFrame(rows, columns=columns)

    day_df = day_df[day_df["NAME"].isin(["forts", "options", "TOTALS"])].copy()

    keep_columns = [
        "NAME",
        "VALTODAY",
        "VALTODAY_USD",
        "NUMTRADES"
    ]
    day_df = day_df[keep_columns]

    day_df = day_df.rename(
        columns={
            "NAME": "instrument_type",
            "VALTODAY": "value_rub_mm",
            "VALTODAY_USD": "value_usd_mm",
            "NUMTRADES": "num_trades"
        }
    )

    day_df["instrument_type"] = day_df["instrument_type"].replace(
        {"forts": "futures", "TOTALS": "totals"}
    )
    day_df["date"] = trade_date
    numeric_columns = ["value_rub_mm", "value_usd_mm", "num_trades"]
    for column in numeric_columns:
        day_df[column] = pd.to_numeric(day_df[column], errors="coerce")

    day_df = day_df[["date", "instrument_type", "value_rub_mm", "value_usd_mm", "num_trades"]]
    return day_df


def collect_daily_turnovers(start_date, end_date):
    all_days = []
    errors_cnt = 0

    for trade_date in generate_calendar_dates(start_date, end_date):
        try:
            day_df = get_futures_engine_turnovers_day(trade_date)
            if not day_df.empty:
                all_days.append(day_df)
        except Exception as error:
            errors_cnt += 1
            if errors_cnt > 10:
                raise error
            print(f"Error on {trade_date}: {error}")
            continue

    if len(all_days) == 0:
        return pd.DataFrame(
            columns=[
                "date",
                "instrument_type",
                "value_rub_mm",
                "value_usd_mm",
                "num_trades",
                "year",
                "month",
                "quarter"
            ]
        )
    daily_df: pd.DataFrame = pd.concat(all_days, ignore_index=True)
    daily_df["date"] = pd.to_datetime(daily_df["date"], errors="coerce")
    daily_df["year"] = daily_df["date"].dt.year
    daily_df["month"] = daily_df["date"].dt.month
    daily_df["quarter"] = daily_df["date"].dt.quarter

    daily_df = daily_df[
        ["date", "instrument_type", "value_rub_mm", "value_usd_mm", "num_trades", "year", "month", "quarter"]
    ]
    return daily_df


def build_monthly_table(daily_df):
    monthly_df = (
        daily_df.groupby(["instrument_type", "year", "month"], as_index=False)[
            ["value_rub_mm", "value_usd_mm", "num_trades"]
        ]
        .sum()
    )
    monthly_df = monthly_df[
        ["instrument_type", "year", "month", "value_rub_mm", "value_usd_mm", "num_trades"]
    ]
    return monthly_df


def build_quarterly_table(daily_df):
    quarterly_df = (
        daily_df.groupby(["instrument_type", "year", "quarter"], as_index=False)[
            ["value_rub_mm", "value_usd_mm", "num_trades"]
        ]
        .sum()
    )
    quarterly_df = quarterly_df[
        ["instrument_type", "year", "quarter", "value_rub_mm", "value_usd_mm", "num_trades"]
    ]
    return quarterly_df


def build_yearly_table(daily_df):
    yearly_df = (
        daily_df.groupby(["instrument_type", "year"], as_index=False)[
            ["value_rub_mm", "value_usd_mm", "num_trades"]
        ]
        .sum()
    )
    yearly_df = yearly_df[
        ["instrument_type", "year", "value_rub_mm", "value_usd_mm", "num_trades"]
    ]
    return yearly_df


def save_outputs(start_date, end_date, daily_df, monthly_df, quarterly_df, yearly_df):
    os.makedirs("../data/daily", exist_ok=True)
    os.makedirs("../data/analytics", exist_ok=True)

    daily_df.to_csv(
        f"data/daily/entire_turnovers_{start_date}_{end_date}.csv",
        index=False,
        encoding="utf-8-sig"
    )
    daily_df[daily_df["instrument_type"] == "futures"].to_csv(
        f"data/daily/futures_turnovers_{start_date}_{end_date}.csv",
        index=False,
        encoding="utf-8-sig"
    )
    daily_df[daily_df["instrument_type"] == "options"].to_csv(
        f"data/daily/options_turnovers_{start_date}_{end_date}.csv",
        index=False,
        encoding="utf-8-sig"
    )
    daily_df[daily_df["instrument_type"] == "totals"].to_csv(
        f"data/daily/total_turnovers_{start_date}_{end_date}.csv",
        index=False,
        encoding="utf-8-sig"
    )

    monthly_df.to_csv(
        f"data/analytics/monthly_turnovers_{start_date}_{end_date}.csv",
        index=False,
        encoding="utf-8-sig"
    )

    quarterly_df.to_csv(
        f"data/analytics/quarterly_turnovers_{start_date}_{end_date}.csv",
        index=False,
        encoding="utf-8-sig"
    )

    yearly_df.to_csv(
        f"data/analytics/yearly_turnovers_{start_date}_{end_date}.csv",
        index=False,
        encoding="utf-8-sig"
    )


def print_quality_checks(daily_df, monthly_df, quarterly_df, yearly_df):
    print("daily_df.shape:", daily_df.shape)
    print("monthly_df.shape:", monthly_df.shape)
    print("quarterly_df.shape:", quarterly_df.shape)
    print("yearly_df.shape:", yearly_df.shape)

    if daily_df.empty:
        print("daily_df is empty")
        return

    dates = pd.to_datetime(daily_df["date"], errors="coerce")
    print("daily_df min date:", dates.min())
    print("daily_df max date:", dates.max())

if __name__ == "__main__":
    main()