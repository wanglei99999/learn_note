> **译文** | 原文：[`packages/coding-agent/docs/shell-aliases.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/shell-aliases.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-07-31

# Shell 别名

pi 以非交互模式运行 bash（`bash -c`），这种模式默认不会展开别名（alias）。

要启用你的 shell 别名，在 `~/.pi/agent/settings.json` 中添加：

```json
{
  "shellCommandPrefix": "shopt -s expand_aliases\neval \"$(grep '^alias ' ~/.zshrc)\""
}
```

按你的 shell 配置调整路径（`~/.zshrc`、`~/.bashrc` 等）。
