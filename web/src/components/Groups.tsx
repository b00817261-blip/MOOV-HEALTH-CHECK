import { useState } from "react";
import { State } from "../data";
import { actions, personName } from "../store";
import { Avatar } from "./bits";
import { PeoplePicker } from "./PeoplePicker";

// Manage groups: see who's in each, and add a new group by naming it and
// picking a lead + members from the list of registered people. A person must
// be registered to appear in the picker — you find them by scrolling and
// clicking their name.
export function Groups({ state }: { state: State }) {
  const [adding, setAdding] = useState(false);

  return (
    <div className="wrap">
      <div className="page-title">Groups</div>
      <div className="page-sub">Every group here shows up on the daily sheet.</div>

      <div className="section">
        <h2>{state.groups.length} groups</h2>
        {state.groups.map((g) => (
          <div className="card" key={g.id}>
            <div className="group-head">
              <span className="name">{g.name}</span>
              <span className="lead">· lead {personName(state, g.leadId)}</span>
              <span className="count-pill">{g.memberIds.length} member{g.memberIds.length === 1 ? "" : "s"}</span>
            </div>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <span className="chip"><Avatar name={personName(state, g.leadId)} /> {personName(state, g.leadId)} · lead</span>
              {g.memberIds.map((id) => (
                <span className="chip" key={id}><Avatar name={personName(state, id)} /> {personName(state, id)}</span>
              ))}
              <AddMember state={state} groupId={g.id} exclude={[g.leadId, ...g.memberIds]} />
            </div>
          </div>
        ))}
      </div>

      <div className="section">
        {adding ? (
          <NewGroupForm state={state} onDone={() => setAdding(false)} />
        ) : (
          <button className="btn primary" onClick={() => setAdding(true)}>+ Add a group</button>
        )}
      </div>
    </div>
  );
}

function NewGroupForm({ state, onDone }: { state: State; onDone: () => void }) {
  const [name, setName] = useState("");
  const [leadId, setLeadId] = useState<string>();
  const [members, setMembers] = useState<string[]>([]);

  const canSave = name.trim() && leadId;

  function toggleMember(id: string) {
    setMembers((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id]));
  }

  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="field">
        <label>Group name</label>
        <input type="text" placeholder="e.g. Manchester Hub" value={name} onChange={(e) => setName(e.target.value)} />
      </div>

      <div className="field">
        <label>Group lead <span className="hint">— pick a registered person</span></label>
        <PeoplePicker
          people={state.people}
          selectedId={leadId}
          onPick={(id) => setLeadId(id)}
          exclude={members}
          placeholder="Search for the lead…"
        />
      </div>

      <div className="field">
        <label>Members <span className="hint">— optional, add as many as you like</span></label>
        <PeoplePicker
          people={state.people}
          onPick={toggleMember}
          exclude={leadId ? [leadId] : []}
          placeholder="Search to add members…"
        />
        {members.length > 0 && (
          <div className="chips">
            {members.map((id) => (
              <span className="chip" key={id}>
                {personName(state, id)}
                <button onClick={() => toggleMember(id)}>×</button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button
          className="btn primary"
          disabled={!canSave}
          onClick={() => {
            actions.addGroup(name.trim(), leadId!, members);
            onDone();
          }}
        >
          Create group
        </button>
        <button className="ghost" onClick={onDone}>Cancel</button>
      </div>
    </div>
  );
}

function AddMember({ state, groupId, exclude }: { state: State; groupId: string; exclude: string[] }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return <button className="ghost" onClick={() => setOpen(true)}>+ add member</button>;
  }
  return (
    <div style={{ width: "100%", marginTop: 8 }}>
      <PeoplePicker
        people={state.people}
        exclude={exclude}
        onPick={(id) => {
          actions.addMember(groupId, id);
          setOpen(false);
        }}
        placeholder="Search to add a member…"
      />
      <button className="ghost" style={{ marginTop: 6 }} onClick={() => setOpen(false)}>Close</button>
    </div>
  );
}
