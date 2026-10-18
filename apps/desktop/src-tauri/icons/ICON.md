# alphaloop 应用图标 · 正式稿

## 交付物
- `alphaloop-icon-1024.png` — **主图标**，1024×1024，圆角方标（Night 底板），给 `tauri icon` 用
- `alphaloop-icon-1024-transparent.png` — 透明底变体（仅 α + cyan 节点 + 弧），可选
- `source-icon.svg` — 矢量源文件（可再编辑）

## 品牌色（与 Night UI 一致）
| token | hex | 用途 |
|---|---|---|
| void | `#07090C` | 图标底板 |
| ink | `#E8EEF5` | α |
| cyan | `#5EEAD4` | 确认节点 + 弧（唯一强调色） |
| line | `#1E2530` | 1px 内描边 |

## 构成
1. **圆角方标** `rx ≈ 224`（约 22%），铺满 1024
2. **α**：Noto Serif Medium，主图形，居中偏上
3. **cyan 确认节点**：α 下方微偏右，带柔光 — 与产品 Logo / 确认态同一语义
4. **cyan 弧**：节点下方一笔，呼应「确认 / 闭环」

## 留白 / 安全区
- 图形内容落在约 **12% 内边距** 内（相对 1024 ≈ 120px）
- macOS 会再套 Continuous Corner；方标已预留圆角，勿再额外缩进
- 小尺寸（16/32）仍应能辨认：α 剪影 + cyan 点

## 禁止
- 勿加行情箭头、蜡烛图、交易符号
- 勿用第二强调色（run/ok 等状态色不进图标）
- 勿把 α 换成字母 A

## 使用
```bash
# 在 apps/desktop 下，把主 PNG 交给 tauri：
npx tauri icon path/to/alphaloop-icon-1024.png
```
建议同时把 `source-icon.svg` 覆盖到 `apps/desktop/src-tauri/icons/source-icon.svg` 作为源。
