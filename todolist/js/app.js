/* 시작점 — 이벤트를 store 함수에 연결한다 */
(function (app) {
  'use strict';

  const { store, view, storage } = app;

  const form = document.getElementById('add-form');
  const input = document.getElementById('new-todo');
  const prioritySelect = document.getElementById('new-priority');
  const hint = document.getElementById('add-hint');
  const list = document.getElementById('todo-list');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  const idOf = node => node.closest('.todo').dataset.id;
  const itemEl = id => list.querySelector(`[data-id="${CSS.escape(id)}"]`);
  const short = text => (text.length > 20 ? text.slice(0, 20) + '…' : text);

  store.subscribe(view.render);
  store.init(storage.load());

  /* ---------- 추가 ---------- */
  form.addEventListener('submit', e => {
    e.preventDefault();
    if (!input.value.trim()) {
      hint.textContent = '할 일을 입력해 주세요';
      view.shake(input);
      input.focus();
      return;
    }
    // '완료' 탭에서는 새 항목이 안 보이므로 전체 탭으로 돌아간다
    if (store.state.settings.filter === 'done') store.setFilter('all');
    const todo = store.addTodo(input.value, prioritySelect.value);
    if (todo) view.markEntering(todo.id);
    input.value = '';
    hint.textContent = '';
    input.focus();
  });

  input.addEventListener('input', () => { hint.textContent = ''; });

  /* ---------- 목록 (이벤트 위임) ---------- */
  list.addEventListener('change', e => {
    if (e.target.matches('.todo-check')) store.toggleTodo(idOf(e.target));
  });

  list.addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const id = idOf(btn);
    if (btn.dataset.action === 'edit') store.startEdit(id);
    else if (btn.dataset.action === 'remove') removeWithFade(id);
  });

  list.addEventListener('dblclick', e => {
    if (e.target.matches('.todo-text')) store.startEdit(idOf(e.target));
  });

  list.addEventListener('keydown', e => {
    if (!e.target.matches('.todo-edit')) return;
    if (e.isComposing || e.keyCode === 229) return; // 한글 조합 중 Enter 중복 방지
    if (e.key === 'Enter') {
      e.preventDefault();
      store.editTodo(idOf(e.target), e.target.value);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      store.cancelEdit();
    }
  });

  // 수정 중에 다른 곳을 누르면 저장한다 (Enter/Esc로 이미 끝났으면 무시)
  list.addEventListener('focusout', e => {
    if (!e.target.matches('.todo-edit')) return;
    const id = idOf(e.target);
    if (store.state.editingId === id) store.editTodo(id, e.target.value);
  });

  function removeWithFade(id) {
    const finish = () => {
      const todo = store.removeTodo(id);
      if (todo) view.showToast(`"${short(todo.text)}" 삭제했어요`, '되돌리기', store.undoRemove);
    };
    const li = itemEl(id);
    if (!li || reduceMotion.matches) {
      finish();
      return;
    }
    li.classList.add('leaving');
    setTimeout(finish, 150);
  }

  /* ---------- 끌어서 순서 바꾸기 (같은 우선순위끼리) ---------- */
  let dragId = null;

  function clearDropMarks() {
    list.querySelectorAll('.drop-before, .drop-after')
      .forEach(li => li.classList.remove('drop-before', 'drop-after'));
  }

  list.addEventListener('dragstart', e => {
    const li = e.target.closest('.todo');
    if (!li) return;
    dragId = li.dataset.id;
    li.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', dragId);
  });

  list.addEventListener('dragover', e => {
    const li = e.target.closest('.todo');
    clearDropMarks();
    if (!li || !dragId || li.dataset.id === dragId) return;
    const source = itemEl(dragId);
    if (!source || source.dataset.priority !== li.dataset.priority) return;
    e.preventDefault();
    const rect = li.getBoundingClientRect();
    li.classList.add(e.clientY > rect.top + rect.height / 2 ? 'drop-after' : 'drop-before');
  });

  list.addEventListener('drop', e => {
    const li = e.target.closest('.todo');
    if (!li || !dragId) return;
    e.preventDefault();
    const after = li.classList.contains('drop-after');
    clearDropMarks();
    store.moveTodo(dragId, li.dataset.id, after);
  });

  list.addEventListener('dragend', () => {
    dragId = null;
    clearDropMarks();
    const dragging = list.querySelector('.dragging');
    if (dragging) dragging.classList.remove('dragging');
  });

  /* ---------- 필터, 테마, 일괄 삭제, 이월 ---------- */
  document.querySelectorAll('[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => store.setFilter(btn.dataset.filter));
  });

  document.getElementById('theme-btn').addEventListener('click', store.cycleTheme);

  document.getElementById('clear-done').addEventListener('click', () => {
    const { done } = store.getProgress();
    if (!done || !confirm(`완료된 항목 ${done}개를 지울까요?`)) return;
    const removed = store.clearDone();
    view.showToast(`완료된 항목 ${removed}개를 지웠어요`);
  });

  document.getElementById('carry-accept').addEventListener('click', () => {
    const moved = store.carryOver();
    if (moved) view.showToast(`${moved}개를 오늘로 가져왔어요`);
  });

  document.getElementById('carry-dismiss').addEventListener('click', store.dismissCarry);

  /* ---------- 단축키: / 또는 N 으로 입력창 ---------- */
  document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t.matches('input, textarea, select') || t.isContentEditable) return;
    if (e.key === '/' || e.code === 'KeyN') {
      e.preventDefault();
      input.focus();
    }
  });

  /* ---------- 자정이 지나면 날짜 갱신 ---------- */
  setInterval(store.refreshDate, 60 * 1000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) store.refreshDate();
  });
})(window.TodayTodo = window.TodayTodo || {});
