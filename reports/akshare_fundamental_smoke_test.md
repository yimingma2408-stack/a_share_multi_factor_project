# AKShare Fundamental Smoke Test

- Panel: `data/processed/fundamental_panel_akshare.parquet`
- Rows: 12150
- Tickers: 5
- Missing required columns: none
- Point-in-time violations: 0

## Factor Non-Missing Counts

| factor | non-missing rows |
| --- | ---: |
| bp | 0 |
| ep | 0 |
| sp | 0 |
| cfp | 0 |
| roe | 12107 |
| gross_profitability | 9720 |
| ocf_to_assets | 12107 |
| revenue_growth | 11811 |
| earnings_growth | 11811 |

## Result

| check | passed |
| --- | --- |
| panel_exists | True |
| core_columns_present | True |
| point_in_time_valid | True |
| all_factors_have_values | False |