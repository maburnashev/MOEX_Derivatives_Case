import time
import requests
import pandas as pd
from io import StringIO
import os

def main():
    os.makedirs("../data/clients", exist_ok=True)
    active_clients_df = collect_active_clients()
    active_clients_df.to_csv("../data/clients/active_clients.csv", index=False)

def parse_int(value):
    # превращает строки вида '12 438' или '12\xa0438' в int
    if pd.isna(value):
        return 0

    value = str(value)
    value = value.replace("\xa0", "")
    value = value.replace(" ", "")
    value = value.replace("\n", "")
    value = value.strip()

    return int(value)


def get_active_clients_for_month(year, month):
    # скачивает страницу рейтинга Мосбиржи за конкретный месяц и год
    # возвращает сумму активных клиентов по топ-25 брокерам
    url = "https://www.moex.com/ru/markets/money/members-rating.aspx"

    params = {
        "rid": 110,
        "month": month,
        "year": year
    }

    headers = {
        "User-Agent": "Mozilla/5.0" # чтобы имитировать обычный запрос браузера
    }

    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()

    html = response.text

    tables = pd.read_html(StringIO(html))

    target_table = None

    for table in tables:
        columns = [str(col).lower() for col in table.columns]

        has_clients_column = any("число" in col and "клиент" in col for col in columns)
        has_company_column = any("наименование" in col or "компани" in col for col in columns)

        if has_clients_column and has_company_column:
            target_table = table
            break

    if target_table is None:
        raise ValueError(f"Не найдена таблица с активными клиентами за {year}-{month:02d}")

    client_column = None

    for col in target_table.columns:
        col_lower = str(col).lower()
        if "число" in col_lower and "клиент" in col_lower:
            client_column = col
            break

    if client_column is None:
        raise ValueError(f"Не найдена колонка с числом клиентов за {year}-{month:02d}")

    active_clients = target_table[client_column].apply(parse_int).sum()

    return active_clients


def collect_active_clients():
    rows = []
    failed_months = []
    for year in range(2015, 2022):
        for month in range(1, 13):
            print(f"Loading {year}-{month:02d}...")

            try:
                active_clients = get_active_clients_for_month(year, month)
            except Exception as e:
                print(e)
                failed_months.append(f"{year}-{month:02d}")
                continue

            quarter = (month - 1) // 3 + 1

            rows.append({
                "year": year,
                "quarter": quarter,
                "month": month,
                "active_clients": active_clients
            })


    df = pd.DataFrame(rows)

    df = df.sort_values(["year", "month"]).reset_index(drop=True)
    df["delta_active_clients"] = df["active_clients"].diff().fillna(0).astype(int)
    df["active_clients"] = df["active_clients"].astype(int)
    for period in failed_months:
        year = period[:4]
        month = period[5:7]
        df[(df["year"] == year) & (df["month"] == month)]["active_clients"] = 0
        df[(df["year"] == year) & (df["month"] == month)]["delta_active_clients"] = 0
    return df

if __name__ == "__main__":
    main()
