import { Role, State } from "../data";
import { actions } from "../store";

// Role switcher so you can see all three sides of the loop in one demo:
// the manager/boss, a group leader, and an employee.
const ROLES: { key: Role; label: string }[] = [
  { key: "manager", label: "Manager" },
  { key: "leader", label: "Group leader" },
  { key: "employee", label: "Employee" },
];

export function TopBar({
  state,
  managerTab,
  setManagerTab,
  pendingForLeader,
}: {
  state: State;
  managerTab: string;
  setManagerTab: (t: string) => void;
  pendingForLeader: number;
}) {
  return (
    <div className="topbar">
      <div className="brand">MOOV<span className="dot">.</span></div>

      <div className="rolepick">
        {ROLES.map((r) => (
          <button
            key={r.key}
            className={state.role === r.key ? "active" : ""}
            onClick={() => actions.setRole(r.key)}
          >
            {r.label}
            {r.key === "leader" && pendingForLeader > 0 && <span className="tag">{pendingForLeader}</span>}
          </button>
        ))}
      </div>

      {state.role === "manager" && (
        <div className="rolepick">
          {[
            { k: "sheet", l: "Daily sheet" },
            { k: "status", l: "Daily status" },
            { k: "groups", l: "Groups" },
          ].map((t) => (
            <button key={t.k} className={managerTab === t.k ? "active" : ""} onClick={() => setManagerTab(t.k)}>
              {t.l}
            </button>
          ))}
        </div>
      )}

      <span className="spacer" />

      {state.role === "leader" && (
        <span className="whoami">
          Acting as
          <select value={state.currentLeaderId} onChange={(e) => actions.setCurrentLeader(e.target.value)}>
            {state.groups.map((g) => (
              <option key={g.leadId} value={g.leadId}>
                {state.people.find((p) => p.id === g.leadId)?.name} · {g.name}
              </option>
            ))}
          </select>
        </span>
      )}

      {state.role === "employee" && (
        <span className="whoami">
          Acting as
          <select value={state.currentEmployeeId} onChange={(e) => actions.setCurrentEmployee(e.target.value)}>
            {[...new Set(state.tasks.map((t) => t.assigneeId))].map((id) => (
              <option key={id} value={id}>
                {state.people.find((p) => p.id === id)?.name}
              </option>
            ))}
          </select>
        </span>
      )}

      <button className="ghost" onClick={() => { if (confirm("Reset the demo data?")) actions.resetDemo(); }}>
        Reset demo
      </button>
    </div>
  );
}
