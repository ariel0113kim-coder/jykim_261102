/* localStorage 읽기/쓰기 — 저장소를 못 쓰는 환경에서도 앱은 계속 동작해야 한다 */
(function (app) {
  'use strict';

  const KEY = 'today-todo:v1';
  const BACKUP_KEY = 'today-todo:backup';

  function load() {
    let raw;
    try {
      raw = localStorage.getItem(KEY);
    } catch (err) {
      return null;
    }
    if (!raw) return null;

    try {
      const data = JSON.parse(raw);
      if (!data || data.version !== 1 || !Array.isArray(data.todos)) {
        throw new Error('알 수 없는 저장 형식');
      }
      return data;
    } catch (err) {
      console.warn('저장된 데이터가 손상되어 빈 목록으로 시작합니다.', err);
      try {
        localStorage.setItem(BACKUP_KEY, raw);
      } catch (e) { /* 백업도 못 하면 그냥 넘어간다 */ }
      return null;
    }
  }

  /** @returns {'ok' | 'quota' | 'unavailable'} */
  function save(data) {
    try {
      localStorage.setItem(KEY, JSON.stringify(data));
      return 'ok';
    } catch (err) {
      const quota = err && (err.name === 'QuotaExceededError' || err.code === 22);
      return quota ? 'quota' : 'unavailable';
    }
  }

  app.storage = { load, save };
})(window.TodayTodo = window.TodayTodo || {});
