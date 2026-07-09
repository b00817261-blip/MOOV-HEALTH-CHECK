import { State, Task, todayLongLabel } from "../data";
import { openAskFor, personName } from "../store";
import { DueTag, SourceBadge } from "./bits";

// The manager's simple daily sheet:
//   1. What's been DONE today, grouped by group, with the little source badge.
//   2. What's OVERDUE, by group.
export function DailySheet({ state }: { state: State }) {
  const doneToday = state.tasks.filter((t) => t.done && t.doneAt);
  const overdue = state.tasks.filter((t) => !t.done && t.dueOffset < 0);

  return (
    <div className="wrap">
      <div className="page-title">Daily sheet</div>
      <div className="page-sub">{todayLongLabel()} · what got done today, by group</div>

      <div className="stat-row">
        <div className="stat green">
          <div className="n">{doneToday.length}</div>
          <div className="l">Done today</div>
        </div>
        <div className="stat red">
          <div className="n">{overdue.length}</div>
          <div className="l">Overdue</div>
        </div>
        <div className="stat">
          <div className="n">{state.groups.length}</div>
          <div className="l">Groups</div>
        </div>
      </div>

      <div className="section">
        <h2>Done today</h2>
        {doneToday.length === 0 && <div className="card"><div className="empty">Nothing marked done yet today.</div></div>}
        {state.groups.map((g) => {
          const rows = doneToday.filter((t) => t.groupId === g.id);
          if (rows.length === 0) return null;
          return (
            <div className="card" key={g.id}>
              <div className="group-head">
                <span className="name">{g.name}</span>
                <span className="lead">· lead {personName(state, g.leadId)}</span>
                <span className="count-pill">{rows.length} done</span>
              </div>
              {rows.map((t) => (
                <DoneRow key={t.id} state={state} task={t} />
              ))}
            </div>
          );
        })}
      </div>

      <div className="section">
        <h2>Overdue by group</h2>
        {overdue.length === 0 && <div className="card"><div className="empty">Nothing overdue — nice.</div></div>}
        {state.groups.map((g) => {
          const rows = overdue.filter((t) => t.groupId === g.id);
          if (rows.length === 0) return null;
          return (
            <div className="card" key={g.id}>
              <div className="group-head">
                <span className="name">{g.name}</span>
                <span className="lead">· lead {personName(state, g.leadId)}</span>
                <span className="count-pill">{rows.length} overdue</span>
              </div>
              {rows.map((t) => (
                <OverdueRow key={t.id} state={state} task={t} />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DoneRow({ state, task }: { state: State; task: Task }) {
  return (
    <div className="row done">
      <span className="check">✓</span>
      <div className="title">
        <div className="t">{task.title}</div>
        <div className="who">{personName(state, task.assigneeId)}</div>
      </div>
      <div className="side">
        {task.source && <SourceBadge source={task.source} />}
        <span className="time">{task.doneAt}</span>
      </div>
    </div>
  );
}

function OverdueRow({ state, task }: { state: State; task: Task }) {
  const ask = openAskFor(state, task.id);
  const days = Math.abs(task.dueOffset);
  return (
    <div className="overdue-line">
      <div className="body">
        <div className="t">{task.title}</div>
        <div className="meta">
          {personName(state, task.assigneeId)} · <span className="days">{days} day{days > 1 ? "s" : ""} overdue</span>
        </div>
        {ask?.answeredAt && (
          <div className="reason">
            <div className="lbl">Reason from {personName(state, state.groups.find((g) => g.id === task.groupId)!.leadId)}</div>
            {ask.answerChoice && <div>{ask.answerChoice}</div>}
            {ask.answerNote && <div style={{ color: "var(--muted)" }}>“{ask.answerNote}”</div>}
          </div>
        )}
        {ask && !ask.answeredAt && <div className="awaiting" style={{ marginTop: 6 }}>Asked · awaiting reply…</div>}
      </div>
      <DueTag offset={task.dueOffset} />
    </div>
  );
}
