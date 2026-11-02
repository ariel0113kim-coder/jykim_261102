/* 화면 그리기 — 상태를 받아 DOM을 맞춘다. 사용자 글은 항상 textContent로 넣는다 */
(function (app) {
  'use strict';

  const $ = id => document.getElementById(id);
  const el = {
    date: $('today-date'),
    themeBtn: $('theme-btn'),
    notice: $('storage-notice'),
    banner: $('carry-banner'),
    bannerText: $('carry-text'),
    progressText: $('progress-text'),
    progressPercent: $('progress-percent'),
    progressBar: $('progress-bar'),
    progressFill: $('progress-fill'),
    filters: document.querySelectorAll('[data-filter]'),
    list: $('todo-list'),
    empty: $('empty-state'),
    clearBtn: $('clear-done'),
    template: $('todo-template'),
    toast: $('toast'),
    toastText: $('toast-text'),
    toastAction: $('toast-action'),
  };

  const PRIORITY_LABEL = { high: '높음', normal: '보통', low: '낮음' };
  const THEME_INFO = { system: ['🖥', '시스템'], light: ['☀', '라이트'], dark: ['🌙', '다크'] };
  const EMPTY_TEXT = {
    all: '오늘 할 일을 추가해 보세요',
    active: '남은 일이 없어요. 수고했어요!',
    done: '완료한 일이 아직 없어요',
  };
  const NOTICE_TEXT = {
    unavailable: '이 브라우저에서는 저장되지 않아요. 페이지를 닫으면 목록이 사라집니다.',
    quota: '저장 공간이 가득 찼어요. 완료된 항목을 지워 주세요.',
  };
  const dateFormat = new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'short',
  });

  function render(state) {
    const store = app.store;
    const focus = rememberFocus();

    applyTheme(state.settings.theme);

    const [y, m, d] = state.today.split('-').map(Number);
    el.date.textContent = dateFormat.format(new Date(y, m - 1, d));

    el.notice.hidden = state.saveStatus === 'ok';
    el.notice.textContent = NOTICE_TEXT[state.saveStatus] || '';

    const pending = store.pendingCarryOver().length;
    el.banner.hidden = pending === 0 || state.carryDismissed;
    el.bannerText.textContent = `지난날 못 끝낸 일이 ${pending}개 있어요`;

    const { done, total, percent } = store.getProgress();
    el.progressText.textContent = `완료 ${done} / 전체 ${total}`;
    el.progressPercent.textContent = `${percent}%`;
    el.progressFill.style.width = `${percent}%`;
    el.progressBar.setAttribute('aria-valuenow', String(percent));

    const counts = { all: total, active: total - done, done };
    el.filters.forEach(btn => {
      btn.setAttribute('aria-pressed', String(btn.dataset.filter === state.settings.filter));
      btn.querySelector('.count').textContent = counts[btn.dataset.filter];
    });

    const todos = store.getVisibleTodos();
    el.list.replaceChildren(...todos.map(t => renderItem(t, state.editingId === t.id)));
    el.empty.hidden = todos.length > 0;
    el.empty.textContent = EMPTY_TEXT[state.settings.filter];
    el.clearBtn.disabled = done === 0;

    const editInput = el.list.querySelector('.todo-edit:not([hidden])');
    if (editInput) {
      editInput.focus();
      editInput.select();
    } else {
      restoreFocus(focus);
    }
  }

  function renderItem(todo, editing) {
    const li = el.template.content.firstElementChild.cloneNode(true);
    li.dataset.id = todo.id;
    li.dataset.priority = todo.priority;
    li.classList.toggle('done', todo.done);

    const check = li.querySelector('.todo-check');
    check.checked = todo.done;
    check.setAttribute('aria-label', `${todo.text} 완료`);

    const dot = li.querySelector('.prio-dot');
    dot.setAttribute('aria-label', `우선순위 ${PRIORITY_LABEL[todo.priority]}`);
    dot.title = `우선순위 ${PRIORITY_LABEL[todo.priority]}`;

    const text = li.querySelector('.todo-text');
    text.textContent = todo.text;

    li.querySelector('[data-action="edit"]').setAttribute('aria-label', `${todo.text} 수정`);
    li.querySelector('[data-action="remove"]').setAttribute('aria-label', `${todo.text} 삭제`);

    if (editing) {
      const input = li.querySelector('.todo-edit');
      input.hidden = false;
      input.value = todo.text;
      input.setAttribute('aria-label', '할 일 수정');
      text.hidden = true;
      li.draggable = false;
    }
    return li;
  }

  /* 목록을 다시 그려도 키보드 사용자가 있던 자리를 잃지 않도록 포커스를 기억한다 */
  function rememberFocus() {
    const active = document.activeElement;
    if (!active || !el.list.contains(active)) return null;
    const li = active.closest('.todo');
    let selector = '.todo-check';
    if (active.dataset.action) selector = `[data-action="${active.dataset.action}"]`;
    else if (active.matches('.todo-edit')) selector = '[data-action="edit"]';
    return { id: li.dataset.id, selector, index: [...el.list.children].indexOf(li) };
  }

  function restoreFocus(focus) {
    if (!focus) return;
    const li = el.list.querySelector(`[data-id="${CSS.escape(focus.id)}"]`);
    if (li) {
      li.querySelector(focus.selector).focus();
      return;
    }
    // 항목이 사라졌으면 같은 자리(없으면 마지막) 항목으로, 목록이 비면 입력창으로
    const items = el.list.children;
    const next = items[Math.min(focus.index, items.length - 1)];
    (next ? next.querySelector('.todo-check') : $('new-todo')).focus();
  }

  function applyTheme(theme) {
    if (theme === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    const [icon, label] = THEME_INFO[theme];
    el.themeBtn.textContent = icon;
    el.themeBtn.setAttribute('aria-label', `테마: ${label} (눌러서 바꾸기)`);
    el.themeBtn.title = `테마: ${label}`;
  }

  let toastTimer = null;

  function showToast(message, actionLabel, onAction) {
    el.toastText.textContent = message;
    el.toastAction.hidden = !actionLabel;
    el.toastAction.textContent = actionLabel || '';
    el.toastAction.onclick = onAction
      ? () => { hideToast(); onAction(); }
      : null;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, 5000);
  }

  function hideToast() {
    el.toast.hidden = true;
    clearTimeout(toastTimer);
  }

  function shake(node) {
    node.classList.remove('shake');
    void node.offsetWidth; // 애니메이션을 다시 시작하기 위한 리플로우
    node.classList.add('shake');
  }

  function markEntering(id) {
    const li = el.list.querySelector(`[data-id="${CSS.escape(id)}"]`);
    if (li) li.classList.add('enter');
  }

  app.view = { render, showToast, hideToast, shake, markEntering };
})(window.TodayTodo = window.TodayTodo || {});
