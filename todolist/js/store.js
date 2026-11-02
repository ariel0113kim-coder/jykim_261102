/* 상태와 상태 변경 함수 — 모든 변경은 commit()을 거쳐 저장 후 화면에 알린다 */
(function (app) {
  'use strict';

  const MAX_LEN = 100;
  const KEEP_DAYS = 30;
  const PRIORITIES = ['high', 'normal', 'low'];
  const RANK = { high: 0, normal: 1, low: 2 };
  const FILTERS = ['all', 'active', 'done'];
  const THEMES = ['system', 'light', 'dark'];

  /** 로컬 시간 기준 'YYYY-MM-DD' */
  function dateKey(d = new Date()) {
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function newId() {
    if (window.crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  const state = {
    todos: [],
    settings: { theme: 'system', filter: 'all' },
    today: dateKey(),
    editingId: null,
    lastRemoved: null,
    carryDismissed: false,
    saveStatus: 'ok',
  };

  const listeners = [];

  function subscribe(fn) {
    listeners.push(fn);
  }

  function commit() {
    state.saveStatus = app.storage.save({ version: 1, todos: state.todos, settings: state.settings });
    listeners.forEach(fn => fn(state));
  }

  function cleanText(text) {
    return String(text).trim().slice(0, MAX_LEN);
  }

  function sanitize(t) {
    if (!t || typeof t.text !== 'string' || typeof t.date !== 'string') return null;
    const text = cleanText(t.text);
    if (!text) return null;
    return {
      id: String(t.id || newId()),
      text,
      done: Boolean(t.done),
      priority: PRIORITIES.includes(t.priority) ? t.priority : 'normal',
      date: t.date,
      order: Number.isFinite(t.order) ? t.order : 0,
      createdAt: Number(t.createdAt) || Date.now(),
      doneAt: t.done ? Number(t.doneAt) || Date.now() : null,
    };
  }

  function init(saved) {
    if (saved) {
      state.todos = saved.todos.map(sanitize).filter(Boolean);
      const s = saved.settings || {};
      if (THEMES.includes(s.theme)) state.settings.theme = s.theme;
      if (FILTERS.includes(s.filter)) state.settings.filter = s.filter;
    }
    // 30일이 지난 완료 항목은 저장 공간을 위해 정리한다
    const limit = new Date();
    limit.setDate(limit.getDate() - KEEP_DAYS);
    const limitKey = dateKey(limit);
    state.todos = state.todos.filter(t => !(t.done && t.date < limitKey));
    commit();
  }

  const find = id => state.todos.find(t => t.id === id);
  const todayTodos = () => state.todos.filter(t => t.date === state.today);
  const byDisplayOrder = (a, b) => RANK[a.priority] - RANK[b.priority] || a.order - b.order;

  function addTodo(text, priority) {
    const clean = cleanText(text);
    if (!clean) return null;
    const orders = todayTodos().map(t => t.order);
    const todo = {
      id: newId(),
      text: clean,
      done: false,
      priority: PRIORITIES.includes(priority) ? priority : 'normal',
      date: state.today,
      order: orders.length ? Math.min(...orders) - 1 : 0,
      createdAt: Date.now(),
      doneAt: null,
    };
    state.todos.push(todo);
    commit();
    return todo;
  }

  function toggleTodo(id) {
    const t = find(id);
    if (!t) return;
    t.done = !t.done;
    t.doneAt = t.done ? Date.now() : null;
    commit();
  }

  function startEdit(id) {
    if (!find(id)) return;
    state.editingId = id;
    commit();
  }

  function cancelEdit() {
    if (state.editingId === null) return;
    state.editingId = null;
    commit();
  }

  /** 빈 값으로 저장하면 원래 글을 그대로 둔다 */
  function editTodo(id, text) {
    const t = find(id);
    const clean = cleanText(text);
    if (t && clean) t.text = clean;
    state.editingId = null;
    commit();
  }

  function removeTodo(id) {
    const i = state.todos.findIndex(t => t.id === id);
    if (i < 0) return null;
    const [todo] = state.todos.splice(i, 1);
    state.lastRemoved = { todo, index: i };
    if (state.editingId === id) state.editingId = null;
    commit();
    return todo;
  }

  function undoRemove() {
    const r = state.lastRemoved;
    if (!r) return;
    state.todos.splice(Math.min(r.index, state.todos.length), 0, r.todo);
    state.lastRemoved = null;
    commit();
  }

  function clearDone() {
    const before = state.todos.length;
    state.todos = state.todos.filter(t => !(t.date === state.today && t.done));
    const removed = before - state.todos.length;
    if (removed) commit();
    return removed;
  }

  function setFilter(filter) {
    if (!FILTERS.includes(filter)) return;
    state.settings.filter = filter;
    commit();
  }

  function cycleTheme() {
    const i = THEMES.indexOf(state.settings.theme);
    state.settings.theme = THEMES[(i + 1) % THEMES.length];
    commit();
  }

  function pendingCarryOver() {
    return state.todos.filter(t => t.date < state.today && !t.done);
  }

  /** 지난 날짜의 미완료 항목을 오늘 목록 아래쪽으로 옮긴다 */
  function carryOver() {
    const items = pendingCarryOver().sort((a, b) => a.date.localeCompare(b.date) || a.order - b.order);
    if (!items.length) return 0;
    let next = Math.max(0, ...todayTodos().map(t => t.order)) + 1;
    items.forEach(t => {
      t.date = state.today;
      t.order = next++;
    });
    commit();
    return items.length;
  }

  function dismissCarry() {
    state.carryDismissed = true;
    commit();
  }

  /** 같은 우선순위 안에서만 순서를 바꾼다 (우선순위 정렬이 먼저이므로) */
  function moveTodo(id, targetId, after) {
    const list = todayTodos().sort(byDisplayOrder);
    const moving = list.find(t => t.id === id);
    const target = list.find(t => t.id === targetId);
    if (!moving || !target || moving === target || moving.priority !== target.priority) return;
    list.splice(list.indexOf(moving), 1);
    list.splice(list.indexOf(target) + (after ? 1 : 0), 0, moving);
    list.forEach((t, i) => { t.order = i; });
    commit();
  }

  /** 자정이 지났으면 오늘 날짜를 바꾼다 */
  function refreshDate() {
    const now = dateKey();
    if (now === state.today) return false;
    state.today = now;
    state.editingId = null;
    state.carryDismissed = false;
    commit();
    return true;
  }

  function getVisibleTodos() {
    const f = state.settings.filter;
    return todayTodos()
      .filter(t => f === 'all' || (f === 'done') === t.done)
      .sort(byDisplayOrder);
  }

  function getProgress() {
    const list = todayTodos();
    const done = list.filter(t => t.done).length;
    return {
      done,
      total: list.length,
      percent: list.length ? Math.round((done / list.length) * 100) : 0,
    };
  }

  app.store = {
    state,
    dateKey,
    subscribe,
    init,
    addTodo,
    toggleTodo,
    startEdit,
    cancelEdit,
    editTodo,
    removeTodo,
    undoRemove,
    clearDone,
    setFilter,
    cycleTheme,
    pendingCarryOver,
    carryOver,
    dismissCarry,
    moveTodo,
    refreshDate,
    getVisibleTodos,
    getProgress,
  };
})(window.TodayTodo = window.TodayTodo || {});
