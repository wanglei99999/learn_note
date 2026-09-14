// 从 markdown 里取出第一个 mermaid 块、<!-- tour ... --> 导览配置和"## 各步详解"一节，套进 viewer-template.html，
// 生成一个可导览、可点节点、带阶段条和详情卡的独立查看页。
// 用法：node make-viewer.mjs <input.md> <output.html> [标题]
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import hljs from "highlight.js";
import { Marked } from "marked";

const [, , input, output, title = "流程图"] = process.argv;
const md = readFileSync(input, "utf8").replace(/\r\n/g, "\n");

const code = md.match(/```mermaid\n([\s\S]*?)```/)?.[1];
if (!code) {
	console.error("没找到 mermaid 块");
	process.exit(1);
}
const tourText = md.match(/<!--\s*tour\s*([\s\S]*?)-->/)?.[1];
// 两种格式：站点数组，或 { loopBack, stations }；每站可以用 view 一步看完，也可以用 shots 拆成几步
const tour = tourText ? JSON.parse(tourText) : [];
const stations = Array.isArray(tour) ? tour : (tour.stations ?? []);
const stepKeys = stations.flatMap((st) =>
	st.shots?.length > 1 ? [st.label, ...st.shots.map((sh) => `${st.label} · ${sh.title}`)] : [st.label],
);
const stepCount = stations.reduce((n, st) => n + (st.shots?.length || 1), 0);

// ---------- 各步详解 ----------
// "## 各步详解" 下每个 "### 标题" 是一张详情卡，标题要和导览里的站名（或"站名 · 步骤名"）一致。
// 全文的链接定义（[agent.ts:437]: https://…）拼到每张卡后面，正文里就能直接写 [agent.ts:437]。
const KINDS = {
	关键源码: "code",
	数据实例: "data",
	设计理由: "why",
	容易误解: "pitfall",
	代价: "cost",
	谁在读写: "rw",
	扩展能做什么: "ext",
	通用模式: "pattern",
};
const marked = new Marked({
	renderer: {
		code({ text, lang }) {
			const language = lang && hljs.getLanguage(lang) ? lang : "plaintext";
			return `<pre><code class="hljs language-${language}">${hljs.highlight(text, { language }).value}</code></pre>\n`;
		},
		link({ href, title: linkTitle, tokens }) {
			const text = this.parser.parseInline(tokens);
			// [文字](#node:ID) 是卡片之间的跳转：查看页里点了打开那个节点的卡
			const nodeRef = href.match(/^#node:([A-Za-z_]\w*)$/);
			if (nodeRef) return `<a href="#" class="xref" data-card="${nodeRef[1]}">${text}</a>`;
			const t = linkTitle ? ` title="${escHtml(linkTitle)}"` : "";
			return `<a href="${escHtml(href)}"${t} target="_blank" rel="noopener">${text}</a>`;
		},
	},
});
const LINK_DEF = /^\[[^\]\n]+\]:[ \t]+\S+.*$/gm;
const linkDefs = (md.match(LINK_DEF) ?? []).join("\n");
// 一节里按 "### 标题" 切成若干张卡，返回 [标题, 渲染好的 HTML]。
// 按行扫描并跳过代码块：代码块里的 "## Goal" 之类不能当成标题。
function cardsIn(sectionTitle) {
	const cards = [];
	let inSection = false;
	let inFence = false;
	let current = null;
	for (const line of md.split("\n")) {
		if (line.startsWith("```")) inFence = !inFence;
		if (!inFence && /^## /.test(line)) {
			inSection = line === `## ${sectionTitle}`;
			current = null;
			continue;
		}
		if (!inSection) continue;
		if (!inFence && line.startsWith("### ")) {
			current = { head: line.slice(4).trim(), lines: [] };
			cards.push(current);
		} else if (current) {
			current.lines.push(line);
		}
	}
	return cards.map(({ head, lines }) => {
		const body = lines.join("\n").replace(LINK_DEF, "");
		const html = marked
			.parse(`${body}\n\n${linkDefs}\n`)
			.replace(/<h4>(.*?)<\/h4>/g, (_, t) => `<h4 class="k-${KINDS[t.trim()] ?? "other"}">${t}</h4>`);
		return [head, html];
	});
}
// 步骤卡：标题是站名，或"站名 · 步骤名"
const steps = {};
for (const [key, html] of cardsIn("各步详解")) {
	if (!stepKeys.includes(key)) console.warn(`步骤卡"${key}"对不上导览里的任何一步`);
	steps[key] = html;
}
// 节点卡：标题是"节点 id：显示名"，id 要在 mermaid 里存在
const graphIds = new Set([...code.matchAll(/^\s*(?:subgraph\s+)?([A-Za-z_]\w*)\s*[[({>]/gm)].map((m) => m[1]));
const nodes = {};
for (const [head, html] of cardsIn("节点详解")) {
	const m = head.match(/^([A-Za-z_]\w*)\s*[:：]\s*(.+)$/);
	if (!m) {
		console.warn(`节点卡标题"${head}"应写成"节点id：名字"`);
		continue;
	}
	if (!graphIds.has(m[1])) console.warn(`节点卡"${head}"的 id 在图里找不到`);
	nodes[m[1]] = { title: m[2], html };
}
const details = { steps, nodes };

// 嵌进 <script> 的 JSON：把 < 转义，避免 </script> 之类提前闭合
function toLiteral(value) {
	return JSON.stringify(value).replace(/</g, "\\u003c");
}
function escHtml(s) {
	return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

const here = dirname(fileURLToPath(import.meta.url));
const template = readFileSync(join(here, "viewer-template.html"), "utf8");
const html = template
	.replaceAll("__TITLE__", escHtml(title))
	.replace("__CODE__", () => toLiteral(code))
	.replace("__TOUR__", () => toLiteral(tour))
	.replace("__DETAILS__", () => toLiteral(details));

writeFileSync(output, html, "utf8");
console.log(
	`已生成 ${output}（导览 ${stations.length} 站 ${stepCount} 步；步骤卡 ${Object.keys(steps).length} 张，节点卡 ${Object.keys(nodes).length} 张）`,
);
