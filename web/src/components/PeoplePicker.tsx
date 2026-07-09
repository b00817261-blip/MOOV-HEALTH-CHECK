import { useState } from "react";
import { Person } from "../data";
import { Avatar } from "./bits";

// A scroll-and-click list of registered people, with a filter box.
// Used to pick a group lead or add members — "slide down and click their name".
export function PeoplePicker({
  people,
  selectedId,
  onPick,
  exclude = [],
  placeholder = "Search registered people…",
}: {
  people: Person[];
  selectedId?: string;
  onPick: (id: string) => void;
  exclude?: string[];
  placeholder?: string;
}) {
  const [q, setQ] = useState("");
  const list = people
    .filter((p) => p.registered && !exclude.includes(p.id))
    .filter((p) => p.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="picker">
      <input
        className="search"
        type="text"
        placeholder={placeholder}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="list">
        {list.length === 0 && <div className="empty" style={{ padding: 20 }}>No matches.</div>}
        {list.map((p) => (
          <div
            key={p.id}
            className={`opt ${selectedId === p.id ? "sel" : ""}`}
            onClick={() => onPick(p.id)}
          >
            <Avatar name={p.name} />
            <span>{p.name}</span>
            {selectedId === p.id && <span style={{ marginLeft: "auto", color: "var(--accent)" }}>✓</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
