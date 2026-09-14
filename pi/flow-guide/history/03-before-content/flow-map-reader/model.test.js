import assert from 'node:assert/strict';
import test from 'node:test';
import { CODE, TOUR, CARDS } from './data.js';
import { parseGraph, collectView, tracePath, readLocation } from './model.js';

test('full-map links retain their target step and reject invalid indices', () => {
  assert.deepEqual(readLocation('#view=full&step=10', 21, new Set()), { view: 'full', step: 9, node: null });
  for (const hash of ['#view=full', '#view=full&step=-1', '#view=full&step=22', '#view=full&step=1.5']) {
    assert.deepEqual(readLocation(hash, 21, new Set()), { view: 'full', step: 0, node: null });
  }
});

test('retains chained edges, labels and nested cluster members', () => {
  const graph = parseGraph(CODE);
  assert.equal(graph.nodes.size, Object.keys(CARDS.nodes).length);
  for (const id of Object.keys(CARDS.nodes)) assert.ok(graph.nodes.has(id), id);
  assert.ok(graph.edges.some(e => e.from === 'LOAD' && e.to === 'BSC'));
  assert.ok(graph.edges.some(e => e.from === 'BUSY' && e.to === 'Q' && e.label === '是'));
  assert.ok(graph.edges.some(e => e.from === 'NEXT' && e.to === 'INJ'));
  assert.deepEqual([...collectView(graph, ['BODY'])], ['BT', 'BS', 'BM']);
  assert.ok(collectView(graph, ['AI']).has('BT'));
});

test('all guide steps resolve to nodes and retain explicit state references', () => {
  const graph = parseGraph(CODE);
  for (const station of TOUR.stations) {
    for (const shot of station.shots || [station]) {
      assert.ok(collectView(graph, shot.view).size > 0, station.label);
    }
  }
  assert.deepEqual([...collectView(graph, ['STATE', 'SNAP', 'S2'])], ['STATE', 'SNAP', 'S2']);
});

test('path traversal excludes loop back edges without losing the tool result path', () => {
  const graph = parseGraph(CODE);
  const downstream = tracePath(graph, 'TR', true, new Set(TOUR.loopBack));
  assert.ok(downstream.has('NEXT'));
  assert.ok(downstream.has('CDO'));
  assert.ok(!downstream.has('INJ'));
  assert.ok(!downstream.has('TR'));
});

test('invalid deep links recover to overview; valid node links retain their step', () => {
  assert.deepEqual(readLocation('#step=9&node=BP', 21, new Set(['BP'])), { view: 'reader', step: 8, node: 'BP' });
  for (const hash of ['#step=-1', '#step=99', '#step=abc', '#step=1.5']) {
    assert.deepEqual(readLocation(hash, 21, new Set()), { view: 'overview', step: 0, node: null });
  }
  assert.deepEqual(readLocation('#step=2&node=missing', 21, new Set()), { view: 'reader', step: 1, node: null });
});
