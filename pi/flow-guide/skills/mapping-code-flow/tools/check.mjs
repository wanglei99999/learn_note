import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.DOMParser = dom.window.DOMParser;
const md = readFileSync(process.argv[2], "utf8");
const blocks = [...md.matchAll(/```mermaid\n([\s\S]*?)```/g)].map((m) => m[1]);
const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false });
for (const [i, code] of blocks.entries()) {
  try {
    const r = await mermaid.parse(code);
    console.log(`block ${i}: OK`, r?.diagramType ?? "");
  } catch (e) {
    console.log(`block ${i}: ERROR\n`, e.message ?? e);
  }
}
