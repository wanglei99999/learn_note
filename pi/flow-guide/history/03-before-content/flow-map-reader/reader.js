import { CODE, TOUR, CARDS, ORIGINAL_PAGE } from './data.js';
import { parseGraph, collectView, tracePath, readLocation } from './model.js?v=navigation-1';
import { colorizeGraph } from './palette.js';

const $ = id => document.getElementById(id);
const graph = parseGraph(colorizeGraph(CODE));
const stations = TOUR.stations.map(station => ({ ...station, shots: station.shots || [{ title: '阶段流程', desc: station.desc, view: station.view }] }));
const steps = stations.flatMap((station, si) => station.shots.map((shot, ki) => ({ station, shot, si, ki, members: collectView(graph, shot.view) })));
const backEdges = new Set(TOUR.loopBack);
const kinds = { step: '处理步骤', hook: '扩展钩子', data: '数据形状', store: '状态 / 存储', compact: '压缩相关', world: '外部交互' };
const shortTitles = ['恢复会话', '装配工具与提示词', '接收输入', '处理 prompt', '建立上下文快照', '准备模型请求', '请求与响应', '判断与执行', '事件分发与持久化', '结束与恢复', '压缩上下文'];
const summaries = ['从会话树恢复历史，写入内存状态。', '加载扩展与项目资源，准备工具和系统提示词。', '处理界面命令，把文本交给 session。', '分流命令与插话，组装本轮消息。', '从 agent.state 复制循环需要的上下文。', '注入插话，转换消息，进入模型适配层。', '构造请求，解码响应流，拼成 assistant 消息。', '执行工具并继续，或结束本次循环。', '更新状态，通知扩展与界面，追加会话记录。', '处理重试、上下文溢出与排队消息。', '保留近期原文，以摘要替换较早的上下文。'];
let state = readLocation(location.hash, steps.length, graph.nodes);
let trace = false;
let lastStep = state.step;
let readerHash = state.view === 'reader' ? location.hash : '#step=1';
let readerPosition = null;
const viewScroll = new Map();
let fullReady = false;
let pendingFullStep = null;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}
function stepForNode(id) {
  if (steps[state.step]?.members.has(id)) return state.step;
  return Math.max(0, steps.findIndex(step => step.members.has(id)));
}
function nodeHref(id) { return `#step=${stepForNode(id) + 1}&node=${encodeURIComponent(id)}`; }
function nodeName(id) { return CARDS.nodes[id]?.title || graph.nodes.get(id)?.label.split('\n')[0] || id; }
function stageHref(si) { return `#step=${steps.findIndex(step => step.si === si) + 1}`; }
function stepName(step) { return step.station.shots.length > 1 ? `${step.station.label} · ${step.shot.title}` : step.station.label; }

function buildDirectory() {
  $('directory').innerHTML = stations.map((station, si) => {
    const section = si === 0 ? '准备 / SETUP' : si === 2 ? '运行 / RUNTIME' : si === 8 ? '状态 / STATE' : '';
    return `${section ? `<div class="directory-group">${section}</div>` : ''}<a class="directory-item" href="${stageHref(si)}" data-station="${si}"><span class="index">${String(si + 1).padStart(2, '0')}</span><span class="directory-name">${escapeHtml(shortTitles[si])}</span><small>${station.shots.length}</small></a>`;
  }).join('');
}

function buildOverview() {
  const card = si => `<article class="stage-card"><a class="stage-main" href="${stageHref(si)}"><div class="card-top"><span>${String(si + 1).padStart(2, '0')} / ${escapeHtml(stations[si].label)}</span><span>↗</span></div><h3>${shortTitles[si]}</h3><p>${summaries[si]}</p></a><div class="card-bottom"><a href="${stageHref(si)}">逐步阅读 · ${stations[si].shots.length} 步 →</a><a href="#view=full&step=${steps.findIndex(step => step.si === si) + 1}" aria-label="在大图中定位${shortTitles[si]}">大图定位 ↗</a></div></article>`;
  $('overview-map').innerHTML = `
    <section class="map-section"><h2 class="map-section-heading"><span class="section-number">A</span>启动准备 <small>恢复历史与装配资源，汇入 agent.state</small></h2><div class="card-row two">${[0, 1].map(card).join('')}</div></section>
    <div class="map-arrow">↓ 准备好上下文，等待输入</div>
    <section class="map-section"><h2 class="map-section-heading"><span class="section-number">B</span>一次输入的主路径 <small>输入 → 消息 → 快照 → 请求 → 结果</small></h2><div class="card-row">${[2, 3, 4, 5, 6, 7].map(card).join('')}</div><div class="branch-row"><a class="branch-link" href="${stageHref(7)}"><b>↶ 工具循环</b><span>有工具调用 → 执行工具 → 回到「准备模型请求」</span></a><a class="branch-link" href="#step=5"><b>↳ 插话队列</b><span>运行中的新输入排队，在轮与轮之间进入上下文</span></a></div></section>
    <section class="map-section"><h2 class="map-section-heading"><span class="section-number">C</span>事件、收尾与压缩 <small>事件贯穿循环；收尾与压缩按各自条件触发</small></h2><div class="card-row">${[8, 9, 10].map(card).join('')}</div><div class="map-arrow">会话落盘 → 下次启动恢复 · 内存状态 → 下次快照</div></section>`;
}

function renderBoundary(container, edges, forward) {
  if (!edges.length) { container.innerHTML = ''; return; }
  container.innerHTML = `<details class="boundary"><summary>${forward ? '流向后续步骤' : '来自其他步骤'} · ${edges.length} 条连接</summary>${edges.map(edge => {
    const id = forward ? edge.to : edge.from;
    return `<a href="${nodeHref(id)}"><small>${forward ? '→' : '←'} ${escapeHtml(stations[steps[stepForNode(id)].si].label)}</small><br>${escapeHtml(nodeName(id))}${edge.label ? ` · ${escapeHtml(edge.label)}` : ''}</a>`;
  }).join('')}</details>`;
}

function renderFlow(step) {
  const members = step.members;
  renderBoundary($('incoming'), graph.edges.filter(edge => !members.has(edge.from) && members.has(edge.to)), false);
  renderBoundary($('outgoing'), graph.edges.filter(edge => members.has(edge.from) && !members.has(edge.to)), true);
  const ids = [...members];
  $('node-flow').innerHTML = `<div class="node-chain">${ids.map((id, index) => {
    const node = graph.nodes.get(id), lines = node.label.split('\n');
    const nextId = ids[index + 1];
    const direct = graph.edges.find(edge => edge.from === id && edge.to === nextId);
    const branches = graph.edges.filter(edge => edge.from === id && members.has(edge.to) && edge.to !== nextId);
    return `<button class="node-card ${node.kind}${state.node === id ? ' selected' : ''}" data-node="${id}" aria-pressed="${state.node === id}"><span class="node-kind"><span>${kinds[node.kind]}</span><span>${id}</span></span><strong>${escapeHtml(lines[0])}</strong>${lines.length > 1 ? `<span class="node-sub">${escapeHtml(lines.slice(1).join('\n'))}</span>` : ''}</button>${branches.map(edge => `<a class="local-branch" href="${nodeHref(edge.to)}">↳ ${escapeHtml(edge.label || '流向')} ${escapeHtml(nodeName(edge.to))}</a>`).join('')}${nextId ? `<div class="flow-connector${direct ? '' : ' independent'}">${direct ? `<span class="arrow">↓</span>${escapeHtml(direct.label)}` : '· 同一步骤的另一节点 ·'}</div>` : ''}`;
  }).join('')}</div>`;
}

function renderConnections(id) {
  const up = graph.edges.filter(edge => edge.to === id), down = graph.edges.filter(edge => edge.from === id);
  const list = (edges, forward) => edges.length ? edges.map(edge => {
    const other = forward ? edge.to : edge.from;
    return `<a href="${nodeHref(other)}">${forward ? '→' : '←'} ${escapeHtml(nodeName(other))}${edge.label ? `<small>${escapeHtml(edge.label)}</small>` : ''}</a>`;
  }).join('') : '<p class="trace-note">没有连接</p>';
  let html = `<section class="connections"><h3>上游 · ${up.length}</h3>${list(up, false)}<h3>下游 · ${down.length}</h3>${list(down, true)}<button class="trace-toggle" id="trace-toggle" aria-pressed="${trace}">${trace ? '收起整条路径' : '追踪整条路径'}</button>`;
  if (trace) {
    for (const forward of [false, true]) {
      const reached = tracePath(graph, id, forward, backEdges);
      html += `<details open><summary>${forward ? '全部下游' : '全部上游'} · ${reached.size} 个节点</summary>${[...reached].map(other => `<a href="${nodeHref(other)}">${escapeHtml(nodeName(other))}</a>`).join('')}</details>`;
    }
    html += '<p class="trace-note">沿箭头追踪；工具循环回到 ④ 的回边不重复展开。</p>';
  }
  return html + '</section>';
}

function renderDetail(step) {
  const node = state.node && CARDS.nodes[state.node];
  $('detail-kicker').textContent = node ? 'NODE / 节点详解' : 'READ / 步骤说明';
  $('detail-title').textContent = node ? node.title : stepName(step);
  $('detail-back').hidden = !node;
  $('detail-content').innerHTML = node ? node.html + renderConnections(state.node) : `<p class="step-lead">${escapeHtml(step.shot.desc || step.station.desc)}</p>` + (CARDS.steps[stepName(step)] || CARDS.steps[step.station.label] || '');
  $('detail-content').scrollTop = 0;
}

function renderReader(previousState) {
  const step = steps[state.step];
  $('step-meta').textContent = `STAGE ${String(step.si + 1).padStart(2, '0')} / ${stations.length} · ${step.station.label}`;
  $('step-title').textContent = shortTitles[step.si];
  $('step-count').textContent = `${state.step + 1} / ${steps.length}`;
  $('previous').disabled = state.step === 0;
  $('next').disabled = state.step === steps.length - 1;
  $('shot-tabs').innerHTML = step.station.shots.map((shot, ki) => `<a href="#step=${steps.findIndex(item => item.si === step.si && item.ki === ki) + 1}" class="${ki === step.ki ? 'active' : ''}" ${ki === step.ki ? 'aria-current="step"' : ''}>${String(ki + 1).padStart(2, '0')}　${escapeHtml(shot.title)}</a>`).join('');
  $('step-summary').textContent = `${step.members.size} 个节点 · 沿箭头阅读，点击连接可跨步骤跳转。`;
  const scroll = $('flow-scroll').scrollTop;
  renderFlow(step);
  renderDetail(step);
  $('flow-scroll').scrollTop = previousState?.step === state.step ? scroll : 0;
  lastStep = state.step;
  readerHash = `#step=${lastStep + 1}${state.node ? `&node=${encodeURIComponent(state.node)}` : ''}`;
  $('reader-tab').href = readerHash;
  $('full-reader-back').href = readerHash;
  $('step-full').href = `#view=full&step=${state.step + 1}`;
}

function render(previousState) {
  document.body.classList.toggle('full-mode', state.view === 'full');
  for (const view of ['overview', 'reader', 'full']) $(view + '-view').hidden = state.view !== view;
  document.querySelectorAll('[data-view]').forEach(link => {
    const active = link.dataset.view === state.view;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  document.querySelectorAll('[data-station]').forEach(link => {
    const active = state.view === 'reader' && Number(link.dataset.station) === steps[state.step].si;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'step'); else link.removeAttribute('aria-current');
  });
  if (state.view === 'reader') renderReader(previousState);
  if (state.view === 'full') {
    const explicit = new URLSearchParams(location.hash.slice(1)).has('step');
    pendingFullStep = explicit ? state.step : null;
    if (!$('full-frame').getAttribute('src')) {
      if (pendingFullStep === null) pendingFullStep = lastStep;
      $('full-frame').src = './pi-flow-map.full.html?v=navigation-1';
    } else if (fullReady) syncFull();
  }
  document.title = state.view === 'reader' ? `${stepName(steps[state.step])} · pi 流程导览` : 'pi · 从输入到回答';
}

function syncFull() {
  if (pendingFullStep !== null) {
    $('full-frame').contentWindow.postMessage({ type: 'pi-flow:go', step: pendingFullStep }, location.origin);
    pendingFullStep = null;
  } else $('full-frame').contentWindow.postMessage({ type: 'pi-flow:resume' }, location.origin);
}
addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== $('full-frame').contentWindow) return;
  if (event.data?.type === 'pi-flow:ready') {
    fullReady = true;
    if (state.view === 'full') syncFull();
  }
});

function navigate(hash) {
  if (location.hash === hash) return;
  location.hash = hash;
}
function showNode(id) {
  if (!graph.nodes.has(id)) return;
  navigate(nodeHref(id));
}
function moveStep(delta) {
  const index = state.view === 'reader' ? Math.max(0, Math.min(steps.length - 1, state.step + delta)) : lastStep;
  navigate(`#step=${index + 1}`);
}
function closeSearch() { $('search-results').hidden = true; }

$('search').addEventListener('input', () => {
  const query = $('search').value.trim().toLocaleLowerCase();
  if (!query) return closeSearch();
  const stageMatches = stations.flatMap((station, si) => `${station.label} ${shortTitles[si]} ${station.desc}`.toLocaleLowerCase().includes(query) ? [{ href: stageHref(si), title: shortTitles[si], subtitle: `阶段 · ${station.shots.length} 步` }] : []);
  const nodeMatches = [...graph.nodes.values()].filter(node => `${node.id} ${node.label} ${nodeName(node.id)}`.toLocaleLowerCase().includes(query)).map(node => ({ href: nodeHref(node.id), title: nodeName(node.id), subtitle: `节点 · ${stations[steps[stepForNode(node.id)].si].label}` }));
  const matches = [...stageMatches, ...nodeMatches];
  $('search-results').innerHTML = matches.length ? `<div class="search-note">${matches.length} 个结果</div>${matches.map(match => `<a href="${match.href}">${escapeHtml(match.title)}<small>${escapeHtml(match.subtitle)}</small></a>`).join('')}` : '<div class="search-note">没有找到匹配项。试试函数名或事件名。</div>';
  $('search-results').hidden = false;
});
$('search').addEventListener('keydown', event => {
  if (event.key === 'ArrowDown') { event.preventDefault(); $('search-results').querySelector('a')?.focus(); }
  if (event.key === 'Enter') {
    const result = $('search-results').querySelector('a');
    if (result && !$('search-results').hidden) { navigate(result.getAttribute('href')); closeSearch(); $('search').blur(); }
  }
});
document.addEventListener('click', event => {
  if (!event.target.closest('.search-wrap')) closeSearch();
  const button = event.target.closest('[data-node]');
  if (button) showNode(button.dataset.node);
  const card = event.target.closest('a[data-card]');
  if (card) { event.preventDefault(); showNode(card.dataset.card); }
  if (event.target.closest('#search-results a')) closeSearch();
  if (event.target.closest('#trace-toggle')) {
    trace = !trace;
    const content = $('detail-content'), scroll = content.scrollTop;
    renderDetail(steps[state.step]);
    content.scrollTop = scroll;
  }
});
$('previous').onclick = () => moveStep(-1);
$('next').onclick = () => moveStep(1);
$('step-detail').onclick = $('detail-back').onclick = () => navigate(`#step=${state.step + 1}`);
$('original-link').href = `./${ORIGINAL_PAGE}`;
$('help-button').onclick = () => { $('help-dialog').showModal(); $('help-button').setAttribute('aria-expanded', 'true'); };
$('help-close').onclick = () => $('help-dialog').close();
$('help-dialog').addEventListener('close', () => $('help-button').setAttribute('aria-expanded', 'false'));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    closeSearch();
    if (event.target === $('search')) $('search').blur();
    else if (!$('help-dialog').open && state.node) navigate(`#step=${state.step + 1}`);
    return;
  }
  if (event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input,textarea,select') || $('help-dialog').open) return;
  if (event.key === '/') { event.preventDefault(); $('search').focus(); }
  else if ((event.key === 'ArrowLeft' || event.key === 'ArrowRight') && state.view !== 'full') { event.preventDefault(); moveStep(event.key === 'ArrowRight' ? 1 : -1); }
  else if (event.key === '?') $('help-button').click();
});
addEventListener('hashchange', () => {
  const previous = state;
  viewScroll.set(previous.view, window.scrollY);
  if (previous.view === 'reader') readerPosition = { hash: readerHash, flow: $('flow-scroll').scrollTop, detail: $('detail-content').scrollTop };
  state = readLocation(location.hash, steps.length, graph.nodes);
  if (state.node && !steps[state.step].members.has(state.node)) {
    state.step = Math.max(0, steps.findIndex(step => step.members.has(state.node)));
    history.replaceState(null, '', `#step=${state.step + 1}&node=${encodeURIComponent(state.node)}`);
  }
  render(previous);
  if (previous.view !== state.view) {
    window.scrollTo(0, viewScroll.get(state.view) || 0);
    if (state.view === 'reader' && readerPosition?.hash === readerHash) {
      $('flow-scroll').scrollTo({ top: readerPosition.flow, behavior: 'instant' });
      $('detail-content').scrollTop = readerPosition.detail;
    }
  } else if (state.node && innerWidth <= 900) document.querySelector('.detail-panel').scrollIntoView({ block: 'start' });
});
buildDirectory();
buildOverview();
if (state.node && !steps[state.step].members.has(state.node)) state.step = stepForNode(state.node);
render();
