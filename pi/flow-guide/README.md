# Pi 流程导读

**平时只打开 [index.html](index.html)：[浏览器统一入口](http://localhost:8000/flow-guide/)。**

入口页只有一个主要操作：“打开最新版”。完整大图与配套说明都从最新版页面内进入。

```text
flow-guide/
├── index.html     从这里打开
├── current/       当前最新版：页面、内容、脚本、样式
├── history/       所有旧版快照，有独立的历史版本目录页
├── skills/        两个制作技能
├── source/        原始 Markdown、旧生成工具与搬移校验记录
└── README.md      本说明
```

## 历史版本

只在需要比较时打开 [历史版本目录](history/index.html)。

| 目录 | 版本 |
|---|---|
| history/01-claude/ | Claude 原版总流程图 |
| history/02-before-navigation/ | 页面与配色已改进、导航联动前的快照 |
| history/03-before-content/ | 导航联动已完成、源码内容补充前的快照 |

备份中的校验文件保留创建时的路径；文件搬移不代表快照内容更新。source/relocation-checksums.json 为上一次搬移的历史记录，不是当前目录清单。

## 制作技能

- [mapping-code-flow](skills/mapping-code-flow/SKILL.md)：原方法，包含 Markdown 模板与图形生成工具。
- [building-source-flow-atlas](skills/building-source-flow-atlas/SKILL.md)：新增方法型技能，覆盖内容去重、源码核验、多视图交互、备份和维护。

两个技能均为项目内资料，未安装到全局技能目录。

## 维护提示

current/ 下的主页面为 pi-flow-map.html；pi-flow-map.full.html 是其嵌入大图，content-guide.html 是配套说明，不是三个不同版本。

当前页面共同读取 current/flow-map-reader/content.js，基础内容在 data.js。source/pi-flow-map.md 与 source/tools/flow-map/ 属于原始制作流程；不要用旧生成器覆盖当前增强页面。

源码基准为提交 6160683a4a8012f0d1cd30c145df18b4ca6f5176。新增说明已核验，旧内容尚未完成全量重新审计。图形库仍需联网加载。

其他学习笔记见 [上级目录](../README.md)。
