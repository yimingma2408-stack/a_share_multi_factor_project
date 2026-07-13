#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import time
import random

import pandas as pd
import efinance as ef


# =========================================================
# Paths
# =========================================================

PROJECT_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
DATA_DIR = PROJECT_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# Global settings
# =========================================================

START_DATE = "20200101"
END_DATE = "20241231"

# efinance:
# fqt = 0: 不复权
# fqt = 1: 前复权
# fqt = 2: 后复权
ADJUST = "qfq"

STANDARD_COLS = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "pct_change",
    "turnover",
]


def adjust_to_fqt(adjust: str) -> int:
    """
    Convert adjustment name to efinance fqt parameter.
    """
    adjust = adjust.lower()

    if adjust in ["none", "raw", "bfq", ""]:
        return 0
    if adjust in ["qfq", "forward"]:
        return 1
    if adjust in ["hfq", "backward"]:
        return 2

    raise ValueError(f"Unknown adjust type: {adjust}")


def download_one_stock_efinance(
    stock_code: str,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    adjust: str = ADJUST,
    max_retries: int = 3,
    sleep_seconds: float = 3.0,
) -> pd.DataFrame:
    """
    Download daily A-share data for one stock from efinance.

    Parameters
    ----------
    stock_code:
        Stock code, e.g. "000001", "600519".
    start_date:
        Start date in YYYYMMDD format.
    end_date:
        End date in YYYYMMDD format.
    adjust:
        "qfq", "hfq", or "none".

    Returns
    -------
    pd.DataFrame
        Standardized stock data with columns:
        date, ticker, open, high, low, close, volume, amount, pct_change, turnover.
    """
    stock_code = str(stock_code).zfill(6)
    fqt = adjust_to_fqt(adjust)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[{stock_code}] efinance attempt {attempt}/{max_retries}...")

            df = ef.stock.get_quote_history(
                stock_codes=stock_code,
                beg=start_date,
                end=end_date,
                klt=101,
                fqt=fqt,
            )

            print(f"[{stock_code}] Raw shape: {df.shape}")
            print(f"[{stock_code}] Raw columns: {list(df.columns)}")

            if df.empty:
                print(f"[{stock_code}] Empty data returned.")
                time.sleep(sleep_seconds + random.random())
                continue

            rename_dict = {
                "日期": "date",
                "股票代码": "ticker",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "涨跌幅": "pct_change",
                "换手率": "turnover",
            }

            df = df.rename(columns=rename_dict)

            if "ticker" not in df.columns:
                df["ticker"] = stock_code

            missing_cols = [col for col in STANDARD_COLS if col not in df.columns]
            if missing_cols:
                raise ValueError(
                    f"[{stock_code}] Missing columns after renaming: {missing_cols}. "
                    f"Current columns: {list(df.columns)}"
                )

            df = df[STANDARD_COLS].copy()

            df["date"] = pd.to_datetime(df["date"])
            df["ticker"] = df["ticker"].astype(str).str.zfill(6)

            numeric_cols = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "pct_change",
                "turnover",
            ]

            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

            return df

        except Exception as exc:
            print(f"[{stock_code}] Error: {exc}")
            time.sleep(sleep_seconds + random.random())

    print(f"[{stock_code}] Failed after {max_retries} attempts.")
    return pd.DataFrame(columns=STANDARD_COLS)


def load_or_download_one_stock_efinance(
    stock_code: str,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    adjust: str = ADJUST,
    force_download: bool = False,
) -> pd.DataFrame:
    """
    Load from local CSV if available; otherwise download from efinance.
    """
    stock_code = str(stock_code).zfill(6)
    output_file = DATA_DIR / f"{stock_code}_daily_{adjust}_efinance.csv"

    if output_file.exists() and not force_download:
        print(f"[{stock_code}] Local file exists. Loading from local CSV.")

        try:
            df = pd.read_csv(output_file)
            df["date"] = pd.to_datetime(df["date"])
            df["ticker"] = df["ticker"].astype(str).str.zfill(6)

            missing_cols = [col for col in STANDARD_COLS if col not in df.columns]
            if not missing_cols and not df.empty:
                return df[STANDARD_COLS].copy()

            print(f"[{stock_code}] Local file invalid. Re-downloading.")

        except Exception as exc:
            print(f"[{stock_code}] Failed to read local file: {exc}. Re-downloading.")

    df = download_one_stock_efinance(
        stock_code=stock_code,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )

    if not df.empty:
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"[{stock_code}] Saved to {output_file}")

    return df


def download_stock_panel_efinance(
    symbols: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    adjust: str = ADJUST,
    force_download: bool = False,
    sleep_seconds: float = 2.0,
) -> pd.DataFrame:
    """
    Download or load a panel of A-share stocks.
    """
    data_list = []

    for symbol in symbols:
        symbol = str(symbol).zfill(6)

        print("=" * 80)
        print(f"Processing {symbol}")

        df = load_or_download_one_stock_efinance(
            stock_code=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            force_download=force_download,
        )

        if df.empty:
            print(f"[{symbol}] Skipped because data is empty.")
            continue

        data_list.append(df)
        time.sleep(sleep_seconds + random.random())

    if not data_list:
        raise RuntimeError(
            "No valid stock data was downloaded or loaded. "
            "Please test one stock first, for example 600519 or 000001."
        )

    panel = pd.concat(data_list, ignore_index=True)
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    panel_file = DATA_DIR / f"stocks_panel_daily_{adjust}_efinance.csv"
    panel.to_csv(panel_file, index=False, encoding="utf-8-sig")

    print("=" * 80)
    print("Panel data saved to:", panel_file)

    print("\nPanel head:")
    print(panel.head())

    print("\nPanel summary:")
    summary = (
        panel.groupby("ticker")["date"]
        .agg(
            count="count",
            min_date="min",
            max_date="max",
        )
    )
    print(summary)

    return panel


def main() -> None:
    symbols = [
        # 金融
        "000001",  # 平安银行
        "600000",  # 浦发银行
        "600036",  # 招商银行
        "601318",  # 中国平安
        "600030",  # 中信证券

        # 消费
        "600519",  # 贵州茅台
        "000858",  # 五粮液
        "000333",  # 美的集团
        "000651",  # 格力电器
        "600887",  # 伊利股份

        # 医药
        "600276",  # 恒瑞医药
        "300760",  # 迈瑞医疗
        "000538",  # 云南白药

        # 科技与电子
        "002415",  # 海康威视
        "000725",  # 京东方A
        "002475",  # 立讯精密
        "603501",  # 韦尔股份
        "000063",  # 中兴通讯

        # 新能源与汽车
        "300750",  # 宁德时代
        "002594",  # 比亚迪
        "601012",  # 隆基绿能
        "600438",  # 通威股份

        # 工业与材料
        "601668",  # 中国建筑
        "600309",  # 万华化学
        "600031",  # 三一重工
        "601899",  # 紫金矿业

        # 能源与公用事业
        "601088",  # 中国神华
        "600028",  # 中国石化
        "601857",  # 中国石油
        "600900",  # 长江电力
    ]

    panel = download_stock_panel_efinance(
        symbols=symbols,
        start_date="20200101",
        end_date="20241231",
        adjust="qfq",
        force_download=False,
        sleep_seconds=2.0,
    )

    print("\nDownload completed.")
    print("Panel shape:", panel.shape)


if __name__ == "__main__":
    main()