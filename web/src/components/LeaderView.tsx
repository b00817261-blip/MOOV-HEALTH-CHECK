import { useState } from "react";
import { AskWhy, REASON_CHOICES, State, Task } from "../data";
import { actions, personName } from "../store";
import { DueTag } from "./bits";

// The group leader's view. They see the boss's "why hasn't this been done?"
// questions as notifications and answer with a multiple-choice reason and/or
// their own words. They can also proactively log what got in the way on any
// overdue task in their group.
export function LeaderView({ state }: { state: State }) {
  const leadId = state.currentLeaderId;
  const group = state.groups.find((g) => g.leadId === leadId);

  if (!group) {
    return (
      <div className="wrap">
        <div className="page-title">Group leader</div>
        <div className="card"><div className="empty">This person doesn’t lead a group yet. Pick a lead in the top bar.</div></div>
      </div>
    );
  }

  const myTaskIds = new Set(state.tasks.filter((t) => t.groupId === group.id).map((t) => t.id));
  const pending = state.asks.filter((a) => myTaskIds.has(a.taskId) && !a.answeredAt);
  const answered = state.asks.filter((a) => myTaskIds.has(a.taskId) && a.answeredAt);
  const overdue = state.tasks.filter((t) => t.groupId === group.id && !t.done && t.dueOffset < 0);

  return (
    <div className="wrap">
      <div className="page-title">
        {group.name}
        {pending.length > 0 && <span className="tag">{pending.length} new</span>}
      </div>
      <div className="page-sub">Group leader · {personName(state, leadId)}</div>

      <div className="section">
        <h2>Questions from {state.bossName}</h2>
        {pending.length === 0 && (
          <div className="card"><div className="empty">No open questions. You’re all caught up.</div></div>
        )}
        {pending.map((a) => {
          const task = state.tasks.find((t) => t.id === a.taskId)!;
          return <AnswerCard key={a.id} ask={a} task={task} />;
        })}
      </div>

      {overdue.length > 0 && (
        <div className="section">
          <h2>Your overdue tasks</h2>
          {overdue.map((t) => {
            const a = answered.find((x) => x.taskId === t.id) || pending.find((x) => x.taskId === t.id);
            const days = Math.abs(t.dueOffset);
            return (
              <div className="card" key={t.id}>
                <div className="overdue-line">
                  <div className="body">
                    <div className="t">{t.title}</div>
                    <div className="meta">
                      {personName(state, t.assigneeId)} · <span className="days">{days} day{days > 1 ? "s" : ""} overdue</span>
                    </div>
                    {a?.answeredAt && (
                      <div className="reason">
                        <div className="lbl">You told {state.bossName}</div>
                        {a.answerChoice && <div>{a.answerChoice}</div>}
                        {a.answerNote && <div style={{ color: "var(--muted)" }}>“{a.answerNote}”</div>}
                      </div>
                    )}
                  </div>
                  <DueTag offset={t.dueOffset} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {answered.length > 0 && (
        <div className="section">
          <h2>Answered</h2>
          {answered.map((a) => {
            const task = state.tasks.find((t) => t.id === a.taskId)!;
            return (
              <div className="card" key={a.id}>
                <div className="overdue-line">
                  <div className="body">
                    <div className="t">{task.title}</div>
                    <div className="reason" style={{ marginTop: 6 }}>
                      {a.answerChoice && <div>{a.answerChoice}</div>}
                      {a.answerNote && <div style={{ color: "var(--muted)" }}>“{a.answerNote}”</div>}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AnswerCard({ ask, task }: { ask: AskWhy; task: Task }) {
  const [choice, setChoice] = useState("");
  const [note, setNote] = useState("");
  const canSend = choice || note.trim();

  return (
    <div className="notif">
      <div className="head">🔔 {ask.fromName} asks why this hasn’t been done</div>
      <div className="task">“{task.title}” · asked at {ask.askedAt}</div>

      <div className="choices">
        {REASON_CHOICES.map((c) => (
          <button
            key={c}
            className={`choice ${choice === c ? "sel" : ""}`}
            onClick={() => setChoice(choice === c ? "" : c)}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="field">
        <textarea
          placeholder="Add anything that got in the way (optional)…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      <button
        className="btn primary"
        disabled={!canSend}
        onClick={() => actions.answerAsk(ask.id, choice, note.trim())}
      >
        Send reply to {ask.fromName}
      </button>
    </div>
  );
}
