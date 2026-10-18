# alphaloop 应用图标 · 正式稿

## 交付物
- `icon-1024.png` — **主图标**（仓库内名），1024×1024，圆角方标（Night 底板），`generate_app_icon.py` / `tauri icon` 的输入
- `alphaloop-icon-1024-transparent.png` — 透明底变体（仅 α + cyan 弧 + 确认节点），可选
- `source-icon.svg` — 矢量源文件（可再编辑）

## 品牌色（与 Night UI 一致）
| token | hex | 用途 |
|---|---|---|
| void | `#07090C` | 图标底板 |
| ink | `#E8EEF5` | α |
| cyan | `#5EEAD4` | 确认节点 + 弧（唯一强调色） |
| line | `#1E2530` | 1px 内描边 |

## v2（放大 α，用户确认稿）
- **α** 宽约 **65%** 画布、高约 **62%**（v1 约 21%）；留白上下≈左右≈**12%**
- α 已转成**轮廓路径**（Noto Serif SemiBold），SVG **不依赖字体**
- 品牌色不变（见上表）
- **cyan 弧**保留；**确认节点**移到弧**右端**（避免像笑脸），不遮挡 α

## 构成
1. **圆角方标** `rx ≈ 224`（约 22%），铺满 1024
2. **α**：主图形，居中偏上（v2 为路径轮廓）
3. **cyan 确认节点**：弧右端，带柔光 — 与产品 Logo / 确认态同一语义
4. **cyan 弧**：α 下方一笔，呼应「确认 / 闭环」

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
# 从仓库根目录：
./scripts/regen-desktop-icons.sh
# 可选（需 Node + apps/desktop 下 @tauri-apps/cli）：
./scripts/regen-desktop-icons.sh --tauri
```
