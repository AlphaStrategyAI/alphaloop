import lockedGlossary from "./locked-glossary.json";
import {buildUiMessages} from "./uiMessages";

type GlossaryKey = keyof typeof lockedGlossary;

function glossaryMessages(lang: "zh" | "en"): {[K in GlossaryKey]: string} {
  const out = {} as {[K in GlossaryKey]: string};
  for (const key of Object.keys(lockedGlossary) as GlossaryKey[]) {
    out[key] = lockedGlossary[key][lang];
  }
  return out;
}

function messages(lang: "zh" | "en") {
  const zh = lang === "zh";
  const copy = (zhText: string, enText: string, _final = false) => (zh ? zhText : enText);
  return {
    nav: {
      research: copy("研究", "Research"),
      methods: copy("方法库", "Methods"),
      glossary: copy("术语", "Glossary"),
      settings: copy("设置", "Settings"),
    },
    ui: buildUiMessages(copy),
    host: {
      running: copy("运行中", "Running"),
    },
    research: {
      quoteProgress: copy("正在取行情 {{done}}/{{total}}", "Loading prices {{done}}/{{total}}"),
    },
    confirm: {
      construction: {
        usEquityCap: copy("单票 ≤5%、成本 5 bp（保守产品假设）", "≤5% per name, cost 5 bp"),
        usEquityCost: copy("成本 5 bp（保守产品假设）", "Cost 5 bp"),
        cnEquityCap: copy("单票 ≤5%、成本 20 bp（保守产品假设）", "≤5% per name, cost 20 bp"),
        cnEquityCost: copy("成本 20 bp（保守产品假设）", "Cost 20 bp"),
        usFund: copy(
          "基金腿不受单票 5% 上限约束、成本 1 bp（保守产品假设）",
          "Fund sleeve: no 5% cap, cost 1 bp",
        ),
        cnFund: copy(
          "基金腿不受单票 5% 上限约束、成本 5 bp（保守产品假设）",
          "Fund sleeve: no 5% cap, cost 5 bp",
        ),
      },
    },
    settings: {
      kicker: copy("SETTINGS", "SETTINGS", true),
      routeLabel: copy("#/settings", "#/settings", true),
      tabs: {
        data: copy("数据源", "Data sources"),
        llm: copy("大模型", "LLM"),
        general: copy("通用", "General"),
      },
      general: {
        title: copy("界面语言", "Interface language"),
        immediate: copy(
          "立即生效，不用重启。当前页面、打开的弹窗和正在进行的研究界面都会即时重绘。",
          "Takes effect immediately, without a restart. The current page, open dialogs, and the in-progress research screen all redraw at once.",
        ),
        followSystem: copy(
          "跟随系统（当前：{{languageName}}）",
          "Follow system (now: {{languageName}})",
        ),
        followHint: copy("首次启动默认选中", "Selected by default on first launch"),
        defaultBadge: copy("默认", "Default"),
        optionZh: copy("中文", "中文", true),
        optionEn: copy("English", "English", true),
        ruleSystem: copy(
          "跟随系统时，系统语言是 zh-* 用中文，其他用英文。",
          "While following the system, zh-* uses Chinese. Anything else uses English.",
        ),
        ruleManual: copy(
          "选了「中文」或「English」后以该选择为准，随时可以再选回「跟随系统」。取不到系统语言时用英文。运行中系统语言变了，到下次启动才生效。",
          "After you choose 中文 or English, that choice wins. You can switch back to Follow system at any time. If the system language cannot be read, English is used. A system-language change during a session waits until the next launch.",
        ),
        stored: copy(
          "存在本机偏好 · 不写进研究记录 · 不改变判定、门禁和版本",
          "Stored in local preferences · not written into the research record · does not change decisions, gates, or versions",
        ),
      },
      about: {
        title: copy("关于", "About"),
        version: copy("版本 {{version}}", "Version {{version}}"),
        commit: copy("提交 {{sha}}", "Commit {{sha}}"),
      },
      scope: {
        title: copy("切换范围", "What switches"),
        switchesLabel: copy("会切换", "Switches"),
        keepsLabel: copy("保持原样", "Stays as written"),
        switchUi: copy("界面、弹窗、空状态和确认卡", "Interface, dialogs, empty states, and the confirmation card"),
        switchPages: copy("结论页、设置页和术语表", "Conclusion, settings, and the glossary"),
        switchNames: copy("方法库和策略族的名称与说明", "Method library and strategy-family names and descriptions"),
        switchErrors: copy(
          "错误提示（技术详情保留原文）",
          "Error messages (Technical details stay verbatim)",
        ),
        switchExport: copy(
          "导出包里给人看的文字（按导出时的语言，写进包的元数据）",
          "Words people read in an export (the language at export time, recorded in package metadata)",
        ),
        switchLlm: copy("新生成的大模型内容", "Newly generated model text"),
        keepNotes: copy("你写的论点和备注", "Theses and notes you wrote"),
        keepSaved: copy(
          "已保存的研究记录、模型摘要和评审意见",
          "Saved research records, model summaries, and review comments",
        ),
        keepLiterature: copy("文献标题和摘要", "Literature titles and abstracts"),
        keepNames: copy(
          "股票名称：始终显示代码，名称用数据源给的原名",
          "Security names: the code is always shown; the name stays as the data source wrote it",
        ),
        keepLegacy: copy(
          "旧记录没有语言字段时，显示「{{languageNotRecorded}}」",
          "Older records with no language field show “{{languageNotRecorded}}”",
        ),
        footnote: copy(
          "已保存的模型文字标出生成时的语言，不自动翻译。日期都写 {{datePattern}}，带时间写 {{dateTimePattern}}。",
          "Saved model text is labeled with the language it was generated in, and is not translated automatically. Dates are {{datePattern}}. With a time, {{dateTimePattern}}.",
        ),
      },
      later: {
        body: copy(
          "本地文件导入将在 M2 提供。",
          "Local file import arrives in M2.",
          true,
        ),
      },
    },
    format: {
      datePattern: copy("YYYY-MM-DD", "YYYY-MM-DD", true),
      dateTimePattern: copy("YYYY-MM-DD HH:mm±HH:mm", "YYYY-MM-DD HH:mm±HH:mm", true),
    },
    errors: {
      unmapped: {
        summary: copy(
          "出现了一个还没有单独说明的错误。研究和数据没有因此被改写。",
          "Something went wrong, and this error does not have its own explanation yet. The research and its data were not changed by this message.",
        ),
        next: copy(
          "可以再试一次。如果还出现，展开技术详情，把原文交给开发者。",
          "Try again. If it happens again, open Technical details and send the original text to the developers.",
        ),
      },
      codes: {
        DATA_SYMBOLS_EMPTY: copy(
          "未选择任何标的，无法加载行情。请在确认开跑前锁定具体代码。",
          "No symbols are selected, so prices cannot be loaded. Lock specific symbols before confirming the run.",
        ),
        DATA_EMPTY_PRICES: copy(
          "数据源未返回行情，请检查标的和网络。",
          "The data source returned no prices. Check the symbols and the network.",
        ),
        DATA_SOURCE_UNAVAILABLE: copy(
          "行情数据源暂时不可用，请稍后重试",
          "Market data is temporarily unavailable. Try again in a moment.",
        ),
        RUNNING_CANNOT_MODIFY: copy(
          "研究仍在运行中，请先暂停再确认修改。",
          "The research is still running. Pause it before confirming a change.",
        ),
        internal_error: copy(
          "服务器内部错误，请稍后重试。",
          "Internal error. Try again in a moment.",
        ),
        contact_email_missing: copy(
          "未配置联系邮箱，本次不查询 {{sources}}。",
          "No contact email is configured, so this run does not query {{sources}}.",
        ),
        MARKET_DATA_TIMEOUT: copy(
          "行情还没取完：{{symbol_count}} 只在限定时间内没有完成。请稍后重试。（MARKET_DATA_TIMEOUT）",
          "Timed out before {{symbol_count, plural, one {# name} other {# names}}} finished. Try again.",
        ),
        MARKET_DATA_RATE_LIMITED: copy(
          "行情源限流（HTTP 429），多次退避后仍失败。请稍后重试。（MARKET_DATA_RATE_LIMITED）",
          "Rate limited (HTTP 429) after retries. Try again.",
        ),
        MARKET_DATA_FETCH_FAILED: copy(
          "行情没有取到：{{symbol}}。（MARKET_DATA_FETCH_FAILED）",
          "No prices for {{symbol}}.",
        ),
        MARKET_DATA_SHELL_TIMEOUT: copy(
          "行情请求在壳层等待时超时，引擎还没返回。请稍后重试。（MARKET_DATA_TIMEOUT）",
          "Quote request timed out in the shell. Try again.",
        ),
        SYMBOL_UNRESOLVED: copy(
          "无法确认「{{token}}」属于哪个交易所。请选择交易所，或输入带后缀的完整代码。",
          "Can't tell which exchange “{{token}}” trades on. Pick an exchange or enter the full code with its suffix.",
        ),
        SYMBOL_NO_DATA: copy(
          "所选数据源没有 {{symbol}} 的行情，无法开跑。请改代码或换数据源。",
          "The selected data source has no data for {{symbol}}, so the run can't start. Change the symbol or the data source.",
        ),
        SYMBOL_ETF_UNSUPPORTED: copy(
          "所选数据源暂不支持 A 股 ETF 行情（{{symbol}}），无法开跑。",
          "The selected data source doesn't support China A-share ETF prices yet ({{symbol}}), so the run can't start.",
        ),
        SYMBOL_EDIT_NOT_DRAFT: copy(
          "只有草稿上的确认卡可以改标的。",
          "Only a draft's confirm card can change the symbol.",
        ),
        SYMBOL_ASK_PENDING: copy(
          "先确认上面的代码再开跑。",
          "Confirm the symbols above before running.",
          true,
        ),
        SYMBOL_AMOUNT_LIKE: copy(
          "「{{token}}」看起来像金额，也可能是代码 {{symbol}}。要把它当作标的吗？",
          '"{{token}}" looks like an amount, but it could also be the symbol {{symbol}}. Use it as a symbol?',
          true,
        ),
        SYMBOL_MIXED_MARKETS: copy(
          "一次研究只能用同一个市场的标的，这里既有 A 股（{{cn_symbols}}），也有美股（{{us_symbols}}）。请删掉其中一边。",
          "A study can only use symbols from one market, but this has both China A-shares ({{cn_symbols}}) and US stocks ({{us_symbols}}). Remove one side.",
          true,
        ),
        SYMBOL_MARKET_MISMATCH: copy(
          "描述里的市场是{{market}}，但 {{symbols}} 不属于这个市场。请删掉这些代码，或改成对应的市场。",
          "The description says {{marketEn}}, but {{symbols}} {{nIsnt}} in that market. Remove {{nIt}} or change the market.",
          true,
        ),
        SYMBOL_SOURCE_MISMATCH: copy(
          "所选数据源 {{source}} 不提供{{market}}行情，和这些标的对不上，无法开跑。请换一个{{market}}数据源。",
          "The selected data source, {{sourceEn}}, doesn't cover {{marketEn}}, so it doesn't match these symbols and the run can't start. Pick a {{marketEn}} data source.",
          true,
        ),
        MARKET_CHOICE_PENDING: copy(
          "描述里没有写市场。这次研究用哪个市场的默认池？",
          "The description doesn't name a market. Which market's default pool should this study use?",
          true,
        ),
        DATA_SOURCE_UNBOUND: copy(
          "这项研究还没有可用的数据来源。",
          "This research does not have a data source yet.",
        ),
        UNLICENSED_SOURCE_UNACKNOWLEDGED: copy(
          "使用未经许可的数据前，请确认仅用于个人研究。",
          "Before using an unlicensed source, confirm it is for personal research only.",
        ),
      },
    },
    glossary: glossaryMessages(lang),
  };
}

export const zhCatalog = messages("zh");
export const enCatalog = messages("en");
export type MessageCatalog = typeof zhCatalog;

/** English leaves that are product-final or identical tokens, not placeholders. */
export const FINAL_MESSAGE_KEYS = [
  "ui.confirm.recognized",
  "ui.confirm.symbolAsk",
  "ui.confirm.useAsSymbol",
  "ui.confirm.justText",
  "ui.confirm.askBeforeRun",
  "ui.confirm.poolHint",
  "ui.confirm.poolHintOne",
  "ui.confirm.setAsSymbol",
  "ui.confirm.mixedMarkets",
  "ui.confirm.amountAsk",
  "ui.confirm.poolHintMany",
  "ui.confirm.poolHintManyOne",
  "ui.confirm.removeCn",
  "ui.confirm.removeUs",
  "ui.confirm.removeSymbol",
  "ui.confirm.symbolAskSame",
  "ui.confirm.financeAskSame",
  "ui.confirm.marketUs",
  "ui.confirm.marketCn",
  "ui.confirm.marketSwitched",
  "ui.confirm.marketChoice",
  "ui.confirm.marketChoiceCn",
  "ui.confirm.marketChoiceUs",
  "ui.confirm.marketMismatch",
  "ui.confirm.unrecognizedTicker",
  "ui.confirm.usedAsSymbol",
  "ui.confirm.treatedAsText",
  "ui.confirm.changeAnswer",
  "errors.codes.SYMBOL_AMOUNT_LIKE",
  "errors.codes.SYMBOL_ASK_PENDING",
  "errors.codes.SYMBOL_MIXED_MARKETS",
  "errors.codes.SYMBOL_MARKET_MISMATCH",
  "errors.codes.SYMBOL_SOURCE_MISMATCH",
  "errors.codes.MARKET_CHOICE_PENDING",
  "settings.later.body",
  "settings.kicker",
  "settings.routeLabel",
  "settings.general.optionZh",
  "settings.general.optionEn",
  "format.datePattern",
  "format.dateTimePattern",
  "ui.copy.cnLarge",
  "ui.copy.cnLargeNote",
  "ui.copy.survivorshipHint",
  "ui.confirm.poolNoteMembers",
  "ui.confirm.poolNoteIndexOnly",
  "ui.confirm.poolNoteEdgarUnconfirmed",
] as const;

export function isFinalMessageKey(key: string): boolean {
  if (key.startsWith("glossary.")) return true;
  return (FINAL_MESSAGE_KEYS as readonly string[]).includes(key);
}
