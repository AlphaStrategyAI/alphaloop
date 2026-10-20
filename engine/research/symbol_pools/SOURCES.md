# 股票默认池 v2 来源说明

本目录里的 `us_equity_large_cap_v2.json` 和 `cn_equity_large_cap_v2.json` 只含证券代码。仅含代码，不含权重或指数数据。没有放进仓库的材料：中证指数公司的成份券原文件，以及 SPDR 的 SPY 持仓工作簿。

标普 500 和沪深 300 分别是 S&P Dow Jones Indices 和中证指数公司的指数，本产品与它们无关联。

v1 的两份 40 只名单不在这里改写。

## 美股 `us_equity_large_cap_v2`

- 来源：英文维基百科页面 “List of S&P 500 companies”。
- 页面：https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
- 钉住的修订：https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&oldid=1380159481
- 修订号：1380159481
- 修订时间：2026-10-14T03:35:16Z
- 抓取日期：2026-10-19
- 许可：CC BY-SA 4.0。名单取自维基百科贡献者编写的成分表。
- 维基文本 SHA-256：`78d66dbd7901dfc54347b4072bc47d0999202c78846a01bc2b360021dc143231`
- 选取：成分表 `id=constituents` 里的 `NyseSymbol`、`NasdaqSymbol`、`BZX link`。代码中的点改成连字符。按代码字母序。不按市值截断。503 只。名单日取下面核对所用持仓文件标明的 2026-10-16。

与 SPY 持仓的核对：

- 文件：State Street SPDR S&P 500 ETF Trust（SPY）日持仓，页面所标 As of 16-Oct-2026。
- URL：https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx
- 抓取日期：2026-10-19
- 文件 SHA-256：`01ebf197474145023e6761450a542260ec3986117d4e7b6732dfe5efc2b07ccb`
- 方法：保留代码匹配 `^[A-Z]{1,5}(\.[A-Z])?$` 的行，把点改成连字符，再与维基名单做集合比较。
- 结果：两边都是 503 只，对称差为空。不纳入的非股票行是美元现金（代码 `-`）和 TPG 的或有价值权（标识 `436CVR021`）。工作簿里的权重、股数和声明没有抄进池文件。

## A 股 `cn_equity_large_cap_v2`

- 来源：中证指数有限公司沪深 300（000300）成份券列表。
- URL：https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/000300cons.xls
- 抓取日期：2026-10-19
- 响应 Last-Modified：2026-10-19T11:04:35Z
- ETag：`C763967B5F9A95F6ABE04B860813013C`
- 文件 SHA-256：`25ef515205586babfbc590b1a21671582e75aec4da863cafa0c38e508bc5b8ec`
- 该 URL 会被指数公司按日覆盖，不是历史冻结链接。可复现的是本仓库里的代码清单和上面的 SHA-256。
- 选取：文件内日期列全部为 `20261019`，指数代码 `000300`，共 300 只。上海证券交易所记为 `.SH`，深圳证券交易所记为 `.SZ`。按代码字母序。不含权重。名单日 2026-10-19。
