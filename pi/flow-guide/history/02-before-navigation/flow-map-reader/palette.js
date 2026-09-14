// Keep the source diagram untouched; apply display categories at render time.
export function colorizeGraph(code) {
  const colors = {
    hook: 'fill:#fff7df,stroke:#aa842e,color:#654e19',
    data: 'fill:#edf3ff,stroke:#7092c3,color:#2e486f',
    store: 'fill:#edf6eb,stroke:#6a966b,color:#315637',
    compact: 'fill:#fbeef0,stroke:#b9808c,color:#77414e',
    world: 'fill:#f3effc,stroke:#9680b8,color:#5c477a',
  };
  return code.replace(/classDef (hook|data|store|compact|world) [^\n]+/g,
    (_, kind) => `classDef ${kind} ${colors[kind]}`)
    .replace('class JSONL0,JSONL1,STATE,STATE2,API store', 'class JSONL0,JSONL1,STATE,STATE2 store')
    .replace('class CKA,NEXT,POSTN,CDO compact', 'class CKA,NEXT,CDO compact')
    .replace('class RUNT world', 'class RUNT,API world');
}
