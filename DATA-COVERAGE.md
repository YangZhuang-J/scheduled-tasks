# 数据覆盖清单（价格 + 估值）

> 实测日期 2026-11。核心结论：**绕过 akshare 的硬编码，直接调乐咕乐股(legulegu)底层 API，可覆盖 56 个指数**（含行业/红利/港股恒生 + 标普500席勒PE）。

## 关键发现

- akshare 的 `stock_index_pe_lg` 内部 `symbol_map` **只硬编码了 12 个指数**，但底层 API 是
  `GET https://legulegu.com/api/stockdata/index-basic-pe?token=..&indexCode=<任意代码>`，`indexCode` 是自由参数。
- 直接传任意 `indexCode` 即可查到 akshare 未封装的指数（创业板指/科创50/中证A50/A500/行业/红利等）。
- 底层 API 返回的字段比 akshare 封装**更多**：除 PE 外还有 `totalMv`(总市值)、`ttmPeQuantile`/`lyrPeQuantile` 等历史分位数。
- **标普500** 另有独立端点 `sp500-shiller-pe`（席勒PE/CAPE，1871~今，月度）。
- **纳指100** 仍无免费 PE 源（legulegu 无对应页面）。

## 代码后缀规则（重要，错一个就返回"无数据"）

- 上交所指数：`.SH`（如 000300.SH 沪深300）
- 深交所指数：`.SZ`（如 399006.SZ 创业板指）
- 中证指数：`.CSI`（如 000922.CSI 中证红利、930050.CSI 中证A50）
- 全收益指数：小写 `h` 开头（如 h21081.CSI 中证半导全收益）
- 港股：`HSI`（恒生指数）

## 完整指数清单（56 个，见 `legulegu_index_map.csv`）

- **宽基**：上证50、沪深300、中证500、中证1000、中证100、中证800、上证180、上证380、深证100、创业板指、创业板50、科创50、中证A50、中证A500、恒生指数(HSI, 1973~今)
- **红利/策略**：上证红利、深证红利、中证红利、中证红利低波/质量/潜力、中证消费红利、中证国企红利、自由现金流
- **行业**：医药(全指医药/中证医药/国证医药/CS医药TI/CS创新药)、消费(中证消费/全指消费/CS消费50/消费龙头/中证白酒)、金融(300金融/中证金融/全指金融/中证银行)、资源(内地资源/A股资源/大宗商品/国证钢铁/煤炭指数/中证煤炭)、科技(中证科技/中证TMT/全指信息/中证半导全收益)、装备(精工制造/中证高装/CS高端装备)

> 注意：证券、军工、新能源等部分行业**不在** legulegu 清单里，需另找源。

## 价格数据（无短板）

- A股指数日线：`ak.stock_zh_index_daily(symbol="sh000905")` 等（新浪，几乎全部）
- 美股指数日线：`ak.index_us_stock_sina(symbol=".NDX"/".INX")`
- 申万行业日线：`ak.index_hist_sw`

## 可复用代码

- `step0-backtest-validate/legulegu_api.py`：`get_pe()` / `get_pb()` / `get_sp500_shiller()` / `resolve()` / `list_indices()`
- `step0-backtest-validate/legulegu_index_map.csv`：56 个指数的 code↔中文名映射
