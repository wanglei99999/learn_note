// 给 markdown 里的源码引用生成固定到某个提交的链接，并把每条引用指向的那一行打印出来，供逐条核对。
//
// 用法：node link-refs.mjs <input.md> --repo <源码仓库目录> [--base <链接前缀>] [--remote <远程名>] [--write]
//
// 正文里这样写引用：[agent.ts:437]、[ai/types.ts:428]、[examples/sandbox/index.ts]
//   - 冒号后面是行号，可以不写（链接到整个文件）
//   - 文件名写成"能唯一定位的最短路径后缀"；有重名时脚本会列出候选，把路径写长一点就行
//   - 路径和仓库对不上、或者想用短名字时，在 md 里加一段别名：
//     <!-- sources {"examples/": "packages/app/examples/", "types.ts": "packages/core/src/types.ts"} -->
//     以 / 结尾的是目录前缀；不以 / 结尾的是整个文件名，必须完全相等
// 链接前缀默认由 --repo 的当前提交和远程地址推出来（GitHub / GitLab），也可以用 --base 直接给。
// 不加 --write 只打印核对结果；加了才把链接定义写回 md 末尾（只替换源码引用的定义，其他链接不动）。
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const args = process.argv.slice(2);
const opt = (name) => {
	const i = args.indexOf(name);
	return i >= 0 ? args[i + 1] : undefined;
};
const input = args[0];
const repo = opt("--repo");
if (!input || !repo) {
	console.error("用法：node link-refs.mjs <input.md> --repo <源码仓库目录> [--base <链接前缀>] [--remote <远程名>] [--write]");
	process.exit(1);
}
const write = args.includes("--write");
const git = (...a) => execFileSync("git", ["-C", repo, ...a], { encoding: "utf8" }).trim();

// ---------- 链接前缀 ----------
function detectBase() {
	const sha = git("rev-parse", "HEAD");
	const remotes = git("remote").split("\n").filter(Boolean);
	const remote = opt("--remote") ?? ["upstream", "origin"].find((r) => remotes.includes(r)) ?? remotes[0];
	if (!remote) throw new Error("仓库没有远程，请用 --base 指定链接前缀");
	const url = git("remote", "get-url", remote)
		.replace(/^git@([^:]+):/, "https://$1/")
		.replace(/\.git$/, "");
	const containing = git("branch", "-r", "--contains", sha);
	if (!containing.split("\n").some((b) => b.trim().startsWith(`${remote}/`))) {
		console.warn(`!! 提交 ${sha.slice(0, 9)} 不在 ${remote} 的任何分支上，发布出去链接会打不开；换 --remote 或先推送`);
	}
	console.log(`链接前缀：${remote} @ ${sha.slice(0, 9)}`);
	return `${url}${url.includes("gitlab") ? "/-/blob/" : "/blob/"}${sha}/`;
}
const base = opt("--base") ?? detectBase();

// ---------- 仓库文件列表 ----------
function listFiles() {
	try {
		return git("ls-files").split("\n").filter(Boolean);
	} catch {
		const out = [];
		const walk = (dir) => {
			for (const name of readdirSync(dir)) {
				if (name === "node_modules" || name.startsWith(".")) continue;
				const full = join(dir, name);
				if (statSync(full).isDirectory()) walk(full);
				else out.push(relative(repo, full).replace(/\\/g, "/"));
			}
		};
		walk(repo);
		return out;
	}
}
const files = listFiles();

// ---------- 找出正文里的引用（跳过代码块和链接定义行） ----------
const md = readFileSync(input, "utf8").replace(/\r\n/g, "\n");
const aliases = JSON.parse(md.match(/<!--\s*sources\s*([\s\S]*?)-->/)?.[1] ?? "{}");
const REF = /^[\w@.\-/]+\.[A-Za-z0-9]+(?::\d+)?$/;
const labels = [];
let inFence = false;
for (const line of md.split("\n")) {
	if (line.startsWith("```")) inFence = !inFence;
	if (inFence || /^\[[^\]]+\]:\s/.test(line)) continue;
	for (const m of line.matchAll(/\[([^[\]\n]+?)\](?![(:])/g)) {
		if (REF.test(m[1]) && !labels.includes(m[1])) labels.push(m[1]);
	}
}

// ---------- 解析、核对 ----------
function resolve(label) {
	const [path, lineText] = label.split(/:(?=\d+$)/);
	// 多个别名都能匹配时取最长的前缀；整名别名（"types.ts"）必须完全相等，免得匹配到 types.tsx
	const alias = Object.keys(aliases)
		.filter((key) => (key.endsWith("/") ? path.startsWith(key) : path === key))
		.sort((a, b) => b.length - a.length)[0];
	const candidates = alias
		? files.filter((f) => f === aliases[alias] + path.slice(alias.length))
		: files.filter((f) => f === path || f.endsWith(`/${path}`));
	return { candidates, line: lineText ? Number(lineText) : undefined };
}

const defs = [];
const problems = [];
for (const label of labels) {
	const { candidates, line } = resolve(label);
	if (candidates.length === 0) {
		problems.push(`找不到文件：[${label}]`);
		continue;
	}
	if (candidates.length > 1) {
		problems.push(`[${label}] 对应多个文件，把路径写长一点：${candidates.slice(0, 5).join("，")}`);
		continue;
	}
	const file = candidates[0];
	if (line === undefined) {
		defs.push(`[${label}]: ${base}${file}`);
		console.log(`${label.padEnd(34)} | （整个文件）`);
		continue;
	}
	const lines = readFileSync(join(repo, file), "utf8").split("\n");
	if (line < 1 || line > lines.length) {
		problems.push(`[${label}] 行号超出文件长度（${lines.length} 行）`);
		continue;
	}
	defs.push(`[${label}]: ${base}${file}#L${line}`);
	const text = lines[line - 1].trim();
	console.log(`${label.padEnd(34)} | ${text ? text.slice(0, 110) : "（空行）"}`);
}

console.log(`\n共 ${labels.length} 个引用，解析成功 ${defs.length} 个`);
for (const p of problems) console.log(`!! ${p}`);
console.log("逐条看上面打印的代码行：空行、单独的括号、和正文说法对不上的，都要改行号。");

if (write) {
	// 去掉旧的源码引用定义，保留别的链接定义，再把新的接在文末
	const kept = md
		.split("\n")
		.filter((line) => {
			const m = line.match(/^\[([^\]]+)\]:\s/);
			return !(m && REF.test(m[1]));
		})
		.join("\n")
		.replace(/\s+$/, "");
	writeFileSync(input, `${kept}\n\n${defs.join("\n")}\n`, "utf8");
	console.log(`已写入 ${defs.length} 条链接定义到 ${input}`);
}
