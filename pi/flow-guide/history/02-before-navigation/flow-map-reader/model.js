// Parse the finite Mermaid notation used by this document, without rendering it.
export function parseGraph(code) {
  const nodes = new Map(), edges = [], groups = new Map(), stack = [];
  for (const line of code.split('\n')) {
    const group = line.match(/^\s*subgraph\s+(\w+)/);
    if (group) { groups.set(group[1], new Set()); stack.push(group[1]); continue; }
    if (line.trim() === 'end') { stack.pop(); continue; }
    const node = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*[\[({/]+"([^"]*)"/);
    if (node) {
      nodes.set(node[1], { id: node[1], label: node[2].replace(/<br\s*\/?\s*>/g, '\n'), kind: 'step' });
      for (const id of stack) groups.get(id).add(node[1]);
    }
    const edgePattern = /\b([A-Z][A-Z0-9_]*)\s*(-->|-\.->)\s*(?:\|"([^"]*)"\|\s*)?([A-Z][A-Z0-9_]*)/g;
    let edge;
    while ((edge = edgePattern.exec(line))) {
      edges.push({ from: edge[1], to: edge[4], label: (edge[3] || '').replace(/<br\s*\/?\s*>/g, ' '), dashed: edge[2] === '-.->' });
      edgePattern.lastIndex = edge.index + edge[0].lastIndexOf(edge[4]);
    }
    const category = line.match(/^\s*class\s+([\w,]+)\s+(\w+)/);
    if (category) for (const id of category[1].split(',')) if (nodes.has(id)) nodes.get(id).kind = category[2];
  }
  return { nodes, edges, groups };
}

export function collectView(graph, view = []) {
  const ids = new Set();
  for (const id of view) {
    if (graph.nodes.has(id)) ids.add(id);
    for (const member of graph.groups.get(id) || []) ids.add(member);
  }
  return ids;
}

export function tracePath(graph, start, forward, loopBack) {
  const seen = new Set([start]), queue = [start];
  for (let i = 0; i < queue.length; i++) {
    for (const edge of graph.edges) {
      if (loopBack.has(`${edge.from}>${edge.to}`) || (forward ? edge.from : edge.to) !== queue[i]) continue;
      const next = forward ? edge.to : edge.from;
      if (!seen.has(next)) { seen.add(next); queue.push(next); }
    }
  }
  seen.delete(start);
  return seen;
}

export function readLocation(hash, count, nodeIds) {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const step = Number(params.get('step'));
  if (params.get('view') === 'full') return { view: 'full', step: 0, node: null };
  if (!Number.isInteger(step) || step < 1 || step > count) return { view: 'overview', step: 0, node: null };
  return { view: 'reader', step: step - 1, node: nodeIds.has(params.get('node')) ? params.get('node') : null };
}
