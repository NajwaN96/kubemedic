import { FormEvent, useEffect, useState } from "react";
import {
  ApiStatus,
  Task,
  createTask,
  deleteTask,
  getApiStatus,
  getTasks,
  updateTask,
} from "./api";
import { Locale, detectLocale, dictionaries, presentError, translate } from "./i18n";

export function App() {
  const [locale, setLocale] = useState<Locale>(() => detectLocale());
  const [tasks, setTasks] = useState<Task[]>([]);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("loading");
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Task | null>(null);
  const [notice, setNotice] = useState("");

  const tr = (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dictionaries[locale].dir;
    try {
      localStorage.setItem("taskflow.lang", locale);
    } catch {
      /* private mode */
    }
  }, [locale]);

  useEffect(() => {
    if (!pendingDelete) return;
    const node = document.getElementById("delete-cancel");
    node?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && busyId == null) setPendingDelete(null);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [pendingDelete, busyId]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 3200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function refreshTasks() {
    try {
      const next = await getTasks();
      setTasks(next);
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "");
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function refreshStatus() {
      const next = await getApiStatus();
      if (!cancelled) setApiStatus(next);
    }

    void refreshStatus();
    void refreshTasks();
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, 8000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [locale]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle || saving) return;
    setSaving(true);
    setFormError(null);
    try {
      await createTask({ title: nextTitle, description: description.trim() });
      setTitle("");
      setDescription("");
      setNotice(tr("notice.added"));
      await refreshTasks();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "");
    } finally {
      setSaving(false);
    }
  }

  async function onComplete(task: Task) {
    setBusyId(task.id);
    setLoadError(null);
    try {
      await updateTask(task.id, { status: "completed" });
      setNotice(tr("notice.completed"));
      await refreshTasks();
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "");
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(task: Task) {
    setBusyId(task.id);
    setLoadError(null);
    try {
      await deleteTask(task.id);
      setPendingDelete(null);
      setNotice(tr("notice.deleted"));
      await refreshTasks();
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "");
    } finally {
      setBusyId(null);
    }
  }

  const pendingCount = tasks.filter((task) => task.status === "pending").length;
  const completedCount = tasks.length - pendingCount;

  return (
    <>
      <a className="skip" href="#main">
        {tr("skip")}
      </a>
      <header className="topbar">
        <div>
          <p className="eyebrow">{tr("eyebrow")}</p>
          <h1>{tr("title")}</h1>
          <p className="subtitle">{tr("subtitle")}</p>
        </div>
        <div className="top-tools">
          <div className="lang" role="group" aria-label={tr("language")}>
            {(["ar", "en"] as Locale[]).map((code) => (
              <button
                key={code}
                type="button"
                className="lang-button"
                lang={code}
                aria-pressed={locale === code}
                onClick={() => setLocale(code)}
              >
                {dictionaries[code].label}
              </button>
            ))}
          </div>
          <p className={`status-pill ${apiStatus}`} role="status">
            {tr(`status.${apiStatus}`)}
          </p>
        </div>
      </header>

      <main className="page" id="main">
        {apiStatus === "not_ready" && (
          <p className="banner warn" role="status">
            {tr("banner.notReady")}
          </p>
        )}
        {apiStatus === "unavailable" && (
          <p className="banner bad" role="alert">
            {tr("banner.unavailable")}
          </p>
        )}

        <section className="panel" aria-labelledby="add-task-heading">
          <div className="panel-heading">
            <h2 id="add-task-heading">{tr("form.add")}</h2>
          </div>
          <form onSubmit={onSubmit}>
            <label htmlFor="title">{tr("form.title")}</label>
            <input
              id="title"
              name="title"
              maxLength={200}
              value={title}
              placeholder={tr("form.titlePlaceholder")}
              onChange={(event) => setTitle(event.target.value)}
              required
            />
            <label htmlFor="description">{tr("form.description")}</label>
            <textarea
              id="description"
              name="description"
              maxLength={2000}
              rows={3}
              value={description}
              placeholder={tr("form.descriptionPlaceholder")}
              onChange={(event) => setDescription(event.target.value)}
            />
            {formError && (
              <p className="form-error" role="alert">
                {presentError(locale, new Error(formError), "errors.add")}
              </p>
            )}
            <button className="primary" type="submit" disabled={saving || title.trim().length === 0}>
              {saving ? tr("form.adding") : tr("form.add")}
            </button>
          </form>
        </section>

        <section className="panel" aria-labelledby="task-list-heading">
          <div className="panel-heading">
            <h2 id="task-list-heading">{tr("list.title")}</h2>
            <p className="count">
              {tr("list.count", { pending: pendingCount, completed: completedCount })}
            </p>
          </div>

          {loadError && (
            <p className="banner bad" role="alert">
              {presentError(locale, new Error(loadError), "errors.load")}
            </p>
          )}

          {!loaded && (
            <p className="empty" role="status">
              {tr("list.loading")}
            </p>
          )}

          {loaded && !loadError && tasks.length === 0 && (
            <div className="empty-state">
              <p className="empty-title">{tr("list.empty")}</p>
              <p className="empty">{tr("list.emptyBody")}</p>
            </div>
          )}

          <ul className="task-list">
            {tasks.map((task) => (
              <li key={task.id} className={`task ${task.status}`}>
                <div className="task-main">
                  <div className="task-title-row">
                    <h3>{task.title}</h3>
                    <span className={`badge ${task.status}`}>
                      {task.status === "completed" ? tr("list.completed") : tr("list.pending")}
                    </span>
                  </div>
                  {task.description ? <p className="description">{task.description}</p> : null}
                  <p className="meta">
                    <span>{tr("list.created")}</span>
                    <time dateTime={task.created_at}>{formatCreated(task.created_at, locale)}</time>
                  </p>
                </div>
                <div className="actions">
                  {task.status !== "completed" && (
                    <button
                      type="button"
                      className="primary"
                      disabled={busyId === task.id}
                      onClick={() => void onComplete(task)}
                    >
                      {busyId === task.id ? tr("actions.working") : tr("actions.complete")}
                    </button>
                  )}
                  <button
                    type="button"
                    className="danger"
                    disabled={busyId === task.id}
                    onClick={() => setPendingDelete(task)}
                  >
                    {tr("actions.delete")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </main>

      {pendingDelete && (
        <div className="modal-backdrop" onClick={() => busyId == null && setPendingDelete(null)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="delete-title">{tr("dialog.title")}</h2>
            <p>{tr("dialog.body", { title: pendingDelete.title })}</p>
            <div className="dialog-actions">
              <button id="delete-cancel" type="button" className="ghost" onClick={() => setPendingDelete(null)} disabled={busyId != null}>
                {tr("actions.cancel")}
              </button>
              <button
                type="button"
                className="danger"
                disabled={busyId != null}
                onClick={() => void onDelete(pendingDelete)}
              >
                {busyId != null ? tr("actions.working") : tr("dialog.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}

      {notice && (
        <p className="toast" role="status">
          {notice}
        </p>
      )}
    </>
  );
}

function formatCreated(value: string, locale: Locale): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}
