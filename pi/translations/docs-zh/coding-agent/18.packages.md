> **译文** | 原文：[`packages/coding-agent/docs/packages.md`](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/packages.md) · 版本：v0.80.10（`eb8dd587`）· 译于 2026-08-02

> pi 可以帮你创建 pi 包。让它帮你把 extension、skill、提示词模板或主题打包即可。

# Pi 包

Pi 包（pi package）将 extension、skill、提示词模板和主题打包在一起，方便你通过 npm 或 git 分享。包可以在 `package.json` 的 `pi` 键下声明资源，也可以使用约定目录。

## 目录

- [安装与管理](#安装与管理)
- [包来源](#包来源)
- [创建 pi 包](#创建-pi-包)
- [包结构](#包结构)
- [依赖](#依赖)
- [包过滤](#包过滤)
- [启用与禁用资源](#启用与禁用资源)
- [作用域与去重](#作用域与去重)

## 安装与管理

> **安全提示：** Pi 包以完整系统权限运行。extension 会执行任意代码，skill 可以指示模型执行包括运行可执行文件在内的任何操作。安装第三方包之前请先审查其源码。

```bash
pi install npm:@foo/bar@1.0.0
pi install git:github.com/user/repo@v1
pi install https://github.com/user/repo  # 原始 URL 也可以
pi install /absolute/path/to/package
pi install ./relative/path/to/package

pi remove npm:@foo/bar
pi list                     # 显示设置中已安装的包
pi update                   # 仅更新 pi
pi update --all             # 更新 pi、更新包，并校正固定的 git ref
pi update --extensions      # 仅更新包并校正固定的 git ref
pi update --models          # 仅刷新模型目录
pi update --self            # 仅更新 pi
pi update --self --force    # 即使已是最新也重新安装 pi
pi update npm:@foo/bar      # 更新单个包
pi update --extension npm:@foo/bar
```

这些命令管理 pi 包，`pi update` 还可以更新 pi CLI 本身的安装。要卸载 pi 本身，参见[快速上手](quickstart.md#卸载)。

默认情况下，`install` 和 `remove` 写入用户设置（`~/.pi/agent/settings.json`）。使用 `-l` 可改为写入项目设置（`.pi/settings.json`）。项目设置可以与团队共享；在项目获得信任后，pi 会在启动时自动安装缺失的包。

若想在不安装的情况下试用某个包，使用 `--extension` 或 `-e`。这会将包安装到临时目录，仅在当前运行中生效：

```bash
pi -e npm:@foo/bar
pi -e git:github.com/user/repo
```

## 包来源

在设置和 `pi install` 中，pi 接受三种来源类型。

### npm

```
npm:@scope/pkg@1.2.3
npm:pkg
```

- 带版本号的来源会被固定，包更新（`pi update --extensions`、`pi update --all`）会跳过它们。
- 用户级安装位于 `~/.pi/agent/npm/`。
- 项目级安装位于 `.pi/npm/`。
- 在 `settings.json` 中设置 `npmCommand`，可将 npm 包的查询与安装操作固定到特定的包装命令，如 `mise` 或 `asdf`。

示例：

```json
{
  "npmCommand": ["mise", "exec", "node@20", "--", "npm"]
}
```

### git

```
git:github.com/user/repo@v1
git:git@github.com:user/repo@v1
https://github.com/user/repo@v1
ssh://git@github.com/user/repo@v1
```

- 不带 `git:` 前缀时，只接受协议 URL（`https://`、`http://`、`ssh://`、`git://`）。
- 带 `git:` 前缀时，接受简写格式，包括 `github.com/user/repo` 和 `git@github.com:user/repo`。
- HTTPS 和 SSH URL 都受支持。
- SSH URL 会自动使用你配置的 SSH 密钥（遵循 `~/.ssh/config`）。
- 对于非交互式运行（例如 CI），可以设置 `GIT_TERMINAL_PROMPT=0` 禁用凭据提示，并设置 `GIT_SSH_COMMAND`（例如 `ssh -o BatchMode=yes -o ConnectTimeout=5`）以快速失败。
- ref 是固定的标签或提交。`pi update --extensions` 和 `pi update --all` 不会将其移动到更新的 ref，但会把已有克隆校正到配置的 ref。
- 使用 `pi install git:host/user/repo@new-ref` 可更新设置并将现有包移动到新的固定 ref。
- 克隆到 `~/.pi/agent/git/<host>/<path>`（全局）或 `.pi/git/<host>/<path>`（项目）。
- 当校正操作改变了检出内容时，pi 会重置并清理克隆，然后在存在 `package.json` 时运行 `npm install`。

**SSH 示例：**
```bash
# git@host:path 简写（需要 git: 前缀）
pi install git:git@github.com:user/repo

# ssh:// 协议格式
pi install ssh://git@github.com/user/repo

# 带版本 ref
pi install git:git@github.com:user/repo@v1.0.0
```

### 本地路径

```
/absolute/path/to/package
./relative/path/to/package
```

本地路径指向磁盘上的文件或目录，添加到设置时不会复制。相对路径基于其所在的设置文件解析。如果路径是文件，则作为单个 extension 加载；如果是目录，pi 按包规则加载资源。

## 创建 pi 包

在 `package.json` 中添加 `pi` 清单，或使用约定目录。加上 `pi-package` 关键字以便被发现。

```json
{
  "name": "my-package",
  "keywords": ["pi-package"],
  "pi": {
    "extensions": ["./extensions"],
    "skills": ["./skills"],
    "prompts": ["./prompts"],
    "themes": ["./themes"]
  }
}
```

路径相对于包根目录。数组支持 glob 模式和 `!exclusions` 排除写法。

### 展示页元数据

[包展示页](https://pi.dev/packages)会展示带有 `pi-package` 标签的包。添加 `video` 或 `image` 字段可以显示预览：

```json
{
  "name": "my-package",
  "keywords": ["pi-package"],
  "pi": {
    "extensions": ["./extensions"],
    "video": "https://example.com/demo.mp4",
    "image": "https://example.com/screenshot.png"
  }
}
```

- **video**：仅支持 MP4。在桌面端悬停时自动播放，点击打开全屏播放器。
- **image**：PNG、JPEG、GIF 或 WebP。显示为静态预览。

两者都设置时，video 优先。

## 包结构

### 约定目录

如果没有 `pi` 清单，pi 会从以下目录自动发现资源：

- `extensions/` 加载 `.ts` 和 `.js` 文件
- `skills/` 递归查找 `SKILL.md` 文件夹，并把顶层的 `.md` 文件作为 skill 加载
- `prompts/` 加载 `.md` 文件
- `themes/` 加载 `.json` 文件

## 依赖

第三方运行时依赖应放在 `package.json` 的 `dependencies` 中。不注册 extension、skill、提示词模板或主题的依赖也应放在 `dependencies` 中。当 pi 从 npm 或 git 安装包时会运行 `npm install`，因此这些依赖会被自动安装。

Pi 为 extension 和 skill 内置了核心包。如果你导入了其中任何一个，请将它们列在 `peerDependencies` 中并使用 `"*"` 版本范围，且不要打包它们：`@earendil-works/pi-ai`、`@earendil-works/pi-agent-core`、`@earendil-works/pi-coding-agent`、`@earendil-works/pi-tui`、`typebox`。

其它 pi 包必须打包进你的 tarball。将它们添加到 `dependencies` 和 `bundledDependencies`，然后通过 `node_modules/` 路径引用其资源。Pi 以独立的模块根目录加载各个包，因此不同的安装不会冲突或共享模块。

示例：

```json
{
  "dependencies": {
    "shitty-extensions": "^1.0.1"
  },
  "bundledDependencies": ["shitty-extensions"],
  "pi": {
    "extensions": ["extensions", "node_modules/shitty-extensions/extensions"],
    "skills": ["skills", "node_modules/shitty-extensions/skills"]
  }
}
```

## 包过滤

在设置中使用对象形式过滤包加载的内容：

```json
{
  "packages": [
    "npm:simple-pkg",
    {
      "source": "npm:my-package",
      "extensions": ["extensions/*.ts", "!extensions/legacy.ts"],
      "skills": [],
      "prompts": ["prompts/review.md"],
      "themes": ["+themes/legacy.json"]
    }
  ]
}
```

`+path` 和 `-path` 是相对于包根目录的精确路径。

- 省略某个键则加载该类型的全部资源。
- 使用 `[]` 则不加载该类型的任何资源。
- `!pattern` 排除匹配项。
- `+path` 强制包含某个精确路径。
- `-path` 强制排除某个精确路径。
- 过滤器叠加在清单之上，只会在已允许的范围内进一步收窄。

## 启用与禁用资源

使用 `pi config` 启用或禁用来自已安装包和本地目录的 extension、skill、提示词模板和主题。`pi config` 默认从全局设置（`~/.pi/agent/settings.json`）开始；按 Tab 在全局和项目本地模式之间切换。使用 `pi config -l` 则从项目覆盖设置（`.pi/settings.json`）开始，继承的全局资源会以暗色显示。

## 作用域与去重

包可以同时出现在全局设置和项目设置中。如果同一个包在两处都出现，以项目条目为准；除非项目条目设置了 `autoload: false`，此时它会作为增量叠加在全局条目之上。包的身份由以下规则确定：

- npm：包名
- git：去掉 ref 的仓库 URL
- local：解析后的绝对路径
