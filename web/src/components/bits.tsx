import { Source, dueLabel } from "../data";

export function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function Avatar({ name }: { name: string }) {
  return <span className="avatar">{initials(name)}</span>;
}

const SRC_CLASS: Record<Source, string> = {
  "Smart MOOV": "smart",
  Email: "email",
  WhatsApp: "whatsapp",
  Phone: "phone",
};

// The little "where was it submitted" badge on the side of a done task.
export function SourceBadge({ source }: { source: Source }) {
  return <span className={`badge ${SRC_CLASS[source]}`}>{source}</span>;
}

// Relative due label: "Tomorrow · Jul 10", "Overdue · Jul 7", etc.
export function DueTag({ offset }: { offset: number }) {
  const { text, tone } = dueLabel(offset);
  return <span className={`due ${tone}`}>{text}</span>;
}
