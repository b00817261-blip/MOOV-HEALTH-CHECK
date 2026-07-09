import { State, Task } from "../data";
import { actions, groupById, personName } from "../store";
import { DueTag, SourceBadge } from "./bits";

// The employee's own task list. Due dates are shown in plain language
// ("Tomorrow · Jul 10", "Overdue · Jul 7") instead of a bare date.
export function MyTasks({ state }: { state: State }) {
  const me = state.currentEmployeeId;
  const mine = state.tasks.filter((t) => t.assigneeId === me);
  const open = mine
    .filter((t) => !t.done)
    .sort((a, b) => a.dueOffset - b.dueOffset);
  const done = mine.filter((t) => t.done);
  const group = mine[0] ? groupById(state, mine[0].groupId) : undefined;

  return (
    <div className="wrap">
      <div className="page-title">My tasks</div>
      <div className="page-sub">
        {personName(state, me)}
        {group ? ` · ${group.name}` : ""}
      </div>

      <div className="section">
        <h2>To do</h2>
        {open.length === 0 && <div className="card"><div className="empty">All clear — nothing on your plate.</div></div>}
        {open.length > 0 && (
          <div className="card">
            {open.map((t) => (
              <TodoRow key={t.id} task={t} />
            ))}
          </div>
        )}
      </div>

      {done.length > 0 && (
        <div className="section">
          <h2>Done today</h2>
          <div className="card">
            {done.map((t) => (
              <div className="row done" key={t.id}>
                <span className="check">✓</span>
                <div className="title"><div className="t">{t.title}</div></div>
                <div className="side">
                  {t.source && <SourceBadge source={t.source} />}
                  <button className="ghost" onClick={() => actions.reopen(t.id)}>Undo</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TodoRow({ task }: { task: Task }) {
  return (
    <div className="row">
      <div className="title">
        <div className="t">{task.title}</div>
      </div>
      <div className="side">
        <DueTag offset={task.dueOffset} />
        <button className="btn primary" style={{ marginTop: 4 }} onClick={() => actions.markDone(task.id, "Smart MOOV")}>
          Mark done
        </button>
      </div>
    </div>
  );
}
