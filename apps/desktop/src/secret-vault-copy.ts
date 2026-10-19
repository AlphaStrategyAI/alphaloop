/** User-facing secret-vault copy. Listed for i18n; English is not shown yet. */

export const secretVaultCopy = {
  open: "密钥",
  title: "密钥",
  close: "关闭",
  alias: "别名",
  secret: "密钥",
  passphrase: "口令",
  passphraseHint: "每次启动都要再输入这个口令。",
  save: "保存",
  remove: "删除",
  unlock: "解锁",
  set: "已设置",
  unset: "未设置",
  locked: "口令文件已在，需要解锁。",
  needsChoice:
    "这台电脑没有系统钥匙串（Secret Service）。请选择一种存放方式。密钥不会被写成明文文件。",
  memory: "仅本次会话",
  passphraseFile: "口令加密的本机文件",
  preview: "查看失败说明",
  keyring: "存在系统钥匙串里。",
  memoryNote: "只留在这次会话的内存里，退出即失。",
  saved: "已保存。界面不保留明文。",
} as const;
