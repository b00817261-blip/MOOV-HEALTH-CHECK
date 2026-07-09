import { State, Task, todayLongLabel } from "../data";
import { actions, openAskFor, personName } from "../store";
import { DueTag } from "./bits";

// The boss's end-of-day check. Summary at the top, then the overdue list at the
// bottom where the boss can "ask why it hasn't been done" — the question goes to
// that group's leader, and the leader's reason shows up here once they reply.
export function DailyStatus({ state }: { state: State }) {
  const doneToday = state.tasks.filter((t) => t.done && t.doneAt);
  const overdue = state.tasks.filter((t) => !t.done && t.dueOffset < 0);
  const open = state.tasks.filter((t) => !t.done && t.dueOffset >= 0);

  return (
    <div className="wrap">
      <div className="page-title">Daily status</div>
      <div className="page-sub">{todayLongLabel()} · end-of-day check for {state.bossName}</div>

      <div className="stat-row">
        <div className="stat green"><div className="n">{doneToday.length}</div><div className="l">Completed today</div></div>
        <div className="stat"><div className="n">{open.length}</div><div className="l">Still open (on time)</div></div>
        <div className="stat red"><div className="n">{overdue.length}</div><div className="l">Overdue</div></div>
      </div>

      <div className="section">
        <h2>Overdue — ask the group leader why</h2>
        {overdue.length === 0 && <div className="card"><div className="empty">Everything's on track. 🎉</div></div>}
        {overdue.map((t) => (
          <OverdueStatusRow key={t.id} state={state} task={t} />
        ))}
      </div>
    </div>
  );
}

function OverdueStatusRow({ state, task }: { state: State; task: Task }) {
  const group = state.groups.find((g) => g.id === task.groupId)!;
  const ask = openAskFor(state, task.id);
  const days = Math.abs(task.dueOffset);

  return (
    <div className="card">
      <div className="overdue-line">
        <div className="body">
          <div className="t">{task.title}</div>
          <div className="meta">
            {group.name} · lead {personName(state, group.leadId)} · assigned to {personName(state, task.assigneeId)}
          </div>
          <div style={{ marginTop: 4 }}>
            <span className="days">{days} day{days > 1 ? "s" : ""} overdue</span>{" "}
            <DueTag offset={task.dueOffset} />
          </div>

          {ask?.answeredAt ? (
            <div className="reason">
              <div className="lbl">{personName(state, group.leadId)} replied at {ask.answeredAt}</div>
              {ask.answerChoice && <div>{ask.answerChoice}</div>}
              {ask.answerNote && <div style={{ color: "var(--muted)" }}>“{ask.answerNote}”</div>}
            </div>
          ) : ask ? (
            <div className="awaiting" style={{ marginTop: 8 }}>
              ⏳ Asked at {ask.askedAt} — waiting on {personName(state, group.leadId)}…
            </div>
          ) : null}
        </div>

        {!ask && (
          <button className="btn ask" onClick={() => actions.askWhy(task.id, state.bossName)}>
            Ask why it hasn’t been done
          </button>
        )}
      </div>
    </div>
  );
}
