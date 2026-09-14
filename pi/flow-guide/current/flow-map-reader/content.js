import { CODE as BASE_CODE, TOUR as BASE_TOUR, CARDS as BASE_CARDS, ORIGINAL_PAGE as BASE_ORIGINAL_PAGE } from './data.js';

export const ORIGINAL_PAGE = `../history/01-claude/${BASE_ORIGINAL_PAGE}`;
export const CONTENT_BACKUP = '../history/03-before-content/pi-flow-map.html';
export const SOURCE_REVISION = '6160683a4a8012f0d1cd30c145df18b4ca6f5176';
const root = `https://github.com/earendil-works/pi/blob/${SOURCE_REVISION}/packages/`;
const ref = (path, line, label = path.split('/').pop()) => `<a href="${root}${path}#L${line}" target="_blank" rel="noopener">${label}:${line}</a>`;
const loop = line => ref('agent/src/agent-loop.ts', line);
const session = line => ref('coding-agent/src/core/agent-session.ts', line);
const manager = line => ref('coding-agent/src/core/session-manager.ts', line);

export const TOPICS = [
  {
    id: 'messages', title: '同一段对话，三种数据表示',
    lead: '会话文件保存历史，AgentMessage 承载运行时上下文，Message 是交给模型适配层的消息。三者不是同一份数组。',
    html: `<table><thead><tr><th>层次</th><th>内容与用途</th></tr></thead><tbody>
      <tr><td>SessionEntry / JSONL</td><td>除消息外，还包含压缩、分支摘要、模型与思考等级变化等条目。消息条目把实际消息放在 <code>message</code> 字段里，<code>id / parentId</code> 记录树关系。</td></tr>
      <tr><td>AgentMessage[]</td><td>当前分支用于运行的消息。除 user、assistant、toolResult 外，编码助手还支持 custom、bashExecution、compactionSummary、branchSummary。</td></tr>
      <tr><td>Message[] → 提供商请求体</td><td><code>convertToLlm</code> 先转换消息角色；随后具体模型适配器再构造自己的请求格式。systemPrompt 和 tools 在 Context 中单独传递。</td></tr>
    </tbody></table>
    <p>恢复路径：会话树 → 选定叶节点所在分支 → 应用最近一次压缩边界 → 运行时消息。请求路径：上下文转换 → convertToLlm → 提供商请求体。</p>
    <p>并非所有条目都进入模型上下文：普通 <code>custom</code> 状态条目会被跳过，<code>custom_message</code> 才转换成消息；<code>display: false</code> 控制显示，不等于不发给模型。<code>bashExecution.excludeFromContext</code> 为 true 时才在转换中排除该 bash 记录。</p>
    <p>源码：${manager(382)}、${manager(418)}、${ref('coding-agent/src/core/messages.ts',148)}、${loop(286)}。</p>`,
    nodes: ['JSONL0','BSC','S1','CONV','S2','STATE','STATE2'], steps: ['⓪ 启动','④ 发请求前'],
  },
  {
    id: 'snapshot', title: '快照复制数组，不深拷贝消息',
    lead: 'messages.slice() 和 tools.slice() 创建新数组，内部的消息对象、工具对象仍可能共享引用。',
    html: `<p>把新消息 push 到快照数组，不会自动给 state.messages 增加元素；但修改共享消息对象的字段，另一处引用也能看到。不能把“快照”理解成完全隔离的数据副本。</p>
    <p>循环通过事件让 Agent 更新状态；下一轮开始前，prepareNextTurn 可以更换上下文和配置。编码助手在这里检查阈值压缩，并刷新 systemPrompt、tools 和 model。</p>
    <p>源码：${ref('agent/src/agent.ts',437)}、${ref('agent/src/agent.ts',544)}、${session(541)}、${loop(175)}。</p>`,
    nodes: ['SNAP','NEXT'], steps: ['③ 快照','⑥ 这一轮的结局 · 进下一轮'],
  },
  {
    id: 'input', title: '输入何时进入模型，何时先返回',
    lead: '输入经过命令、扩展和队列分流；调用 prompt 不保证立即发出模型请求。',
    html: `<table><thead><tr><th>条件</th><th>结果</th></tr></thead><tbody>
    <tr><td>扩展命令已处理</td><td>执行 handler 后返回；prompt 主路径不继续发请求。handler 本身仍可通过其他 API 触发模型交互。</td></tr>
    <tr><td>input 事件已处理输入</td><td>当前提交返回；否则使用扩展转换后的文本和图片继续展开 skill / 模板。</td></tr>
    <tr><td>当前正在运行</td><td>按 streamingBehavior 放入 steer 或 followUp 队列；未指定行为则报错。</td></tr>
    <tr><td>可以发起新一轮</td><td>检查模型与认证、检查压缩，再组装 user、nextTurn 和扩展消息。</td></tr>
    </tbody></table>
    <p><b>steer</b> 在循环开始与轮间检查，供下一次模型响应使用，并不是强制终止正在执行的工具。<b>followUp</b> 等到没有更多工具调用或 steer 消息时才被取出。</p>
    <p>源码：${session(1179)}、${loop(167)}、${loop(191)}、${loop(257)}。</p>`,
    nodes: ['CMD','HCMD','HIN','BUSY','Q','INJ','FU'], steps: ['② prompt · 分流','② prompt · 忙不忙'],
  },
  {
    id: 'branches', title: '一轮结束后的判断顺序',
    lead: '先处理 error / aborted，再看工具调用；轮后停止钩子、steer 和 followUp 也参与决定是否继续。',
    html: `<ol>
    <li><code>stopReason</code> 为 error 或 aborted：发 turn_end、agent_end，直接退出本次核心循环。</li>
    <li>消息包含 toolCall：若 stopReason 为 length，所有调用都不执行，生成错误 ToolResultMessage；其他情况进入工具执行。</li>
    <li>写入工具结果并发 turn_end；若 shouldStopAfterTurn 返回 true，则直接结束。</li>
    <li>还有需要继续的工具批次或 steer 消息，进入下一轮准备；否则检查 followUp。没有后续消息才结束。</li>
    </ol>
    <p>一批工具结果全部带 <code>terminate: true</code> 时，不再仅因该批工具而继续；后续队列仍可能让循环继续。单个工具失败通常作为 <code>isError: true</code> 的结果交还模型，不等同于整个 Agent 抛错退出。</p>
    <p>大图展示主路径，不能把“有工具调用”理解为一定执行，也不能把“无工具调用”限定为只有纯文本。</p>
    <p>源码：${loop(215)}、${loop(227)}、${loop(252)}、${loop(589)}、${loop(605)}。</p>`,
    nodes: ['OUT','EXEC','TR','HTC','AEND'], steps: ['⑥ 这一轮的结局 · 三种结局','⑥ 这一轮的结局 · 执行工具'],
  },
  {
    id: 'persistence', title: '收到事件、写入状态与写入磁盘',
    lead: '流式显示、内存更新、会话条目追加和真正写文件，是不同的时刻。',
    html: `<p><code>message_update</code> 更新流式内容；<code>message_end</code> 将消息加入 Agent 状态。Session 层先处理扩展，再通知监听者，最后把 user / assistant / toolResult 追加成 message 条目；custom 使用 custom_message 条目。</p>
    <p>appendMessage 为条目分配 id，令 parentId 指向当前 leafId，再推进 leafId。普通消息的流式增量不会逐段写成会话记录；最终 error / aborted 消息仍可能包含已生成的部分内容。</p>
    <p>新会话首次刷盘通常要等 assistant 条目出现。若关闭持久化或没有 sessionFile，_persist 直接返回；如果文件已经刷出，后续条目可以继续追加。因此“还没有 assistant 就一定不存在文件”不适用于所有状态。</p>
    <p>源码：${ref('agent/src/agent.ts',544)}、${session(643)}、${manager(1029)}、${manager(1071)}。</p>`,
    nodes: ['ME','PUSH','SUBS','APP','LAZY','JSONL1'], steps: ['⑦ 事件分发 · 界面和落盘','⑦ 事件分发 · 落到哪'],
  },
  {
    id: 'recovery', title: 'agent_end 之后，为什么还会继续',
    lead: 'agent_end 表示本次核心循环不再发事件；会话层仍会检查重试、压缩与新入队消息。',
    html: `<table><thead><tr><th>检查顺序</th><th>条件与动作</th></tr></thead><tbody>
    <tr><td>可重试错误</td><td>开启重试且未耗尽预算时，按 baseDelayMs × 2^(attempt−1) 等待；从运行时数组移除失败的末尾 assistant，然后 continue。历史记录保留。</td></tr>
    <tr><td>上下文溢出 / 可恢复的 length</td><td>满足同模型等检查时进入压缩恢复。失败或截断响应最多尝试一次压缩后重试；已经成功完成的 stop 响应只压缩，不重放回答。</td></tr>
    <tr><td>超过上下文阈值</td><td>压缩以减少后续上下文，不因此重放已完成的回答。</td></tr>
    <tr><td>agent_end 处理期间又有消息入队</td><td>会话层可以再次 continue。</td></tr>
    </tbody></table>
    <p>重试等待可取消；上下文溢出不走普通错误重试。核心 Agent 还要等待 agent_end 监听者完成并清理运行状态，才算空闲。</p>
    <p>源码：${session(1105)}、${session(2155)}、${session(2878)}、${session(2926)}、${ref('agent/src/agent.ts',532)}。</p>`,
    nodes: ['POSTN'], steps: ['⑧ 收尾'],
  },
  {
    id: 'compaction', title: '压缩减少上下文，不删除历史',
    lead: 'compaction 条目保存摘要与 firstKeptEntryId；恢复上下文时使用摘要、保留段以及压缩之后的新记录。',
    html: `<p><code>firstKeptEntryId</code> 是本次压缩中开始保留原文的条目。选定分支上最近一次 compaction 之前被总结的条目，会被排除出当前上下文；它们仍在会话历史里。</p>
    <p>A 位于新 prompt 前，B 位于下一次响应前，C 位于本次 run 后。B 按上下文估算检查阈值；A / C 还可能处理符合条件的溢出。阈值判断是严格的 <code>contextTokens &gt; contextWindow − reserveTokens</code>，不是固定百分比。</p>
    <p>扩展可取消或提供自定义压缩结果。成功后追加 compaction 条目，再从会话树重建 state.messages；压缩不是对 JSONL 文件做压缩编码，也不是删除旧行。</p>
    <p>源码：${manager(418)}、${manager(1111)}、${session(541)}、${session(2155)}、${session(2381)}、${ref('coding-agent/src/core/compaction/compaction.ts',235)}。</p>`,
    nodes: ['CKA','HCOMP','CDO'], steps: ['压缩'],
  },
  {
    id: 'provider', title: '请求示例的适用范围',
    lead: '图中 tools / system / messages、cache_control 和 SSE 细节采用 Anthropic Messages 适配器示例。',
    html: `<p>通用循环将 <code>Context</code> 交给 streamFunction；具体请求体、缓存标记和响应协议由模型适配器决定。不能把这部分图示当成所有提供商的统一 HTTP 格式。</p>
    <p>读图时先认清公共数据边界，再查看当前模型对应的适配器。图中的 LLM API 是外部服务，不是会话数据库。</p>
    <p>源码：${loop(286)}、${ref('ai/src/api/anthropic-messages.ts',1020)}。</p>`,
    nodes: ['API','BP','BT','BS','BM','SSE','LLMCALL'], steps: ['⑤ 请求与响应 · 拼请求','⑤ 请求与响应 · 收回来'],
  },
];

function note(topic) {
  return `<section class="source-note"><h4>${topic.title}</h4><p>${topic.lead}</p>${topic.html}<p><a href="./content-guide.html#${topic.id}" target="_blank" rel="noopener">打开完整阅读说明 ↗</a></p></section>`;
}

export const CARDS = {
  nodes: Object.fromEntries(Object.entries(BASE_CARDS.nodes).map(([id, card]) => [id, { ...card }])),
  steps: { ...BASE_CARDS.steps },
};
for (const topic of TOPICS) {
  for (const id of topic.nodes) CARDS.nodes[id].html = note(topic) + CARDS.nodes[id].html;
  for (const key of topic.steps) CARDS.steps[key] = note(topic) + CARDS.steps[key];
}
// Replace overbroad explanations with the checked explanation, keeping node-level code examples available.
for (const key of ['③ 快照','⑥ 这一轮的结局 · 三种结局','⑦ 事件分发 · 界面和落盘','⑦ 事件分发 · 落到哪','⑧ 收尾']) {
  CARDS.steps[key] = note(TOPICS.find(topic => topic.steps.includes(key)));
}
for (const id of ['SNAP','S2','LAZY','SUBS','OUT','POSTN']) {
  CARDS.nodes[id].html = note(TOPICS.find(topic => topic.nodes.includes(id)));
}
CARDS.nodes.SUBS.title = 'message_end 追加会话条目';

const descriptions = {
  '③ 快照': '为循环复制 messages 和 tools 数组；数组内的对象仍共享引用。状态通过事件更新，轮间可以刷新上下文与配置。',
  '⑥ 这一轮的结局 · 三种结局': '先判断 error / aborted，再看 toolCall；length 截断的调用不执行。轮后停止钩子、工具批次与消息队列共同决定是否继续。',
  '⑦ 事件分发 · 界面和落盘': '界面用 message_update 显示流式内容；message_end 将消息追加为会话条目。真正写文件还取决于持久化设置与首次刷盘状态。',
  '⑦ 事件分发 · 落到哪': '状态先在内存更新，会话条目由 SessionManager 管理。新会话通常等首条 assistant 后首次写文件；已刷盘会话继续追加。',
  '⑧ 收尾': '本次核心循环结束后，Session 依次检查普通错误重试、压缩恢复和新入队消息。成功响应不会仅因超过上下文阈值而重放。',
};
export const TOUR = { ...BASE_TOUR, stations: BASE_TOUR.stations.map(station => ({
  ...station,
  desc: descriptions[station.label] || station.desc,
  ...(station.shots ? { shots: station.shots.map(shot => ({ ...shot, desc: descriptions[`${station.label} · ${shot.title}`] || shot.desc })) } : {}),
})) };

export const CODE = BASE_CODE
  .replace('循环只碰这份副本', '数组独立；内部对象仍共享引用')
  .replace('命令 handler :1188<br/>直接执行，不进 LLM', '命令 handler :1188<br/>执行后返回；handler 可另行调用模型')
  .replace('有 toolCall"', '有 toolCall（length 时返回错误结果）"')
  .replace('OUT -->|"纯文本"| FU', 'OUT -->|"无 toolCall"| FU')
  .replace('这一轮的结局"}', '这一轮的结局<br/>详解包含 length / 停止钩子 / terminate 条件"}')
  .replace('只在 message_end · agent-session.ts:673', 'message_end 追加条目 · agent-session.ts:673')
  .replace('懒刷盘：还没出现 assistant 就先不建文件', '新会话通常等 assistant 首次刷盘<br/>已刷盘会话继续追加；可关闭持久化')
  .replace('溢出 → 压缩后重试这一轮；阈值 → 只压缩', '失败溢出 / 可恢复 length：压缩后最多重试一次<br/>成功响应超限 / 阈值：只压缩，不重放回答');
