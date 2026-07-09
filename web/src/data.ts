// Domain types + seed data for the MOOV daily-operations prototype.
// This is a front-end demo: everything lives in the browser (localStorage),
// so there is no server or login to run. Swap this file for real API calls
// when you wire it to a backend.

export type Role = "manager" | "leader" | "employee";

// Where a task update came in from — shown as the little badge on the side.
export type Source = "Smart MOOV" | "Email" | "WhatsApp" | "Phone";

export const SOURCES: Source[] = ["Smart MOOV", "Email", "WhatsApp", "Phone"];

export interface Person {
  id: string;
  name: string;
  // Everyone here has "registered" — that's what makes them pickable as a
  // group lead or member. `unassigned` people are registered but not yet in a
  // group (they show up in the add-group / add-member picker).
  registered: boolean;
}

export interface Group {
  id: string;
  name: string;
  leadId: string; // Person.id
  memberIds: string[]; // Person.id[]
}

export interface Task {
  id: string;
  title: string;
  groupId: string;
  assigneeId: string;
  // Due date as an offset in days from "today". We store an offset (not a
  // fixed date) so the demo always looks live no matter which day it's opened.
  dueOffset: number;
  done: boolean;
  doneAt?: string; // "HH:MM" when marked done today
  source?: Source; // where the completion was submitted from
}

// A "why hasn't this been done?" question the boss sends to a group leader.
export interface AskWhy {
  id: string;
  taskId: string;
  fromName: string; // the boss asking (e.g. "Derek")
  askedAt: string; // "HH:MM"
  // The leader's reply (undefined until they answer).
  answerChoice?: string;
  answerNote?: string;
  answeredAt?: string;
}

export interface State {
  people: Person[];
  groups: Group[];
  tasks: Task[];
  asks: AskWhy[];
  role: Role;
  // Which "current user" each role acts as (fixed for the demo).
  currentEmployeeId: string;
  currentLeaderId: string;
  bossName: string;
}

// Canned multiple-choice reasons a leader can pick when answering "why".
export const REASON_CHOICES = [
  "Waiting on parts / a vendor",
  "Short-staffed today",
  "Blocked by another team",
  "Took longer than expected",
  "Will be finished today",
  "Wrong info / needs clarification",
];

// ---------------------------------------------------------------------------
// Seed
// ---------------------------------------------------------------------------

const P = (id: string, name: string, registered = true): Person => ({
  id,
  name,
  registered,
});

const people: Person[] = [
  // Group leads (also the hub managers from the roster)
  P("aoife", "Aoife Byrne"),
  P("lukas", "Lukas Weber"),
  P("diego", "Diego Ramirez"),
  P("priya", "Priya Nair"),
  // Members
  P("sam", "Sam Okafor"),
  P("mei", "Mei Lin"),
  P("tomas", "Tomas Novak"),
  P("hana", "Hana Ito"),
  P("omar", "Omar Haddad"),
  P("ruby", "Ruby Nguyen"),
  P("felix", "Felix Braun"),
  P("nadia", "Nadia Petrova"),
  // Registered but not yet in any group — these appear in the picker so you
  // can "slide down and click on their name" to add them.
  P("jordan", "Jordan Lee"),
  P("camila", "Camila Souza"),
  P("wei", "Wei Chen"),
  P("sara", "Sara Al-Farsi"),
  P("kenji", "Kenji Sato"),
];

const groups: Group[] = [
  { id: "lon", name: "London Hub", leadId: "aoife", memberIds: ["sam", "mei"] },
  { id: "ber", name: "Berlin Hub", leadId: "lukas", memberIds: ["tomas", "felix"] },
  { id: "nyc", name: "New York Hub", leadId: "diego", memberIds: ["omar", "ruby"] },
  { id: "syd", name: "Sydney Hub", leadId: "priya", memberIds: ["hana", "nadia"] },
];

// dueOffset: negative = overdue, 0 = today, 1 = tomorrow, etc.
const tasks: Task[] = [
  // London — done today
  t("lon", "sam", "Clear weekend dispatch backlog", 0, "Smart MOOV", "08:12"),
  t("lon", "mei", "Onboard two new drivers", 0, "Email", "09:40"),
  t("lon", "sam", "Re-route zone 2 for roadworks", 1, undefined, undefined),
  // London — overdue
  t("lon", "mei", "Renew 3 vehicle inspections", -2, undefined, undefined),

  // Berlin — done today
  t("ber", "tomas", "Swap winter tyres on 6 vans", 0, "WhatsApp", "07:55"),
  t("ber", "felix", "Reconcile fuel-card receipts", 0, "Smart MOOV", "10:20"),
  t("ber", "tomas", "Depot safety walk-through", 2, undefined, undefined),
  // Berlin — overdue
  t("ber", "felix", "Replace broken loading-bay light", -1, undefined, undefined),
  t("ber", "tomas", "File June mileage report", -3, undefined, undefined),

  // New York — done today
  t("nyc", "omar", "Cover morning shift gap", 0, "Phone", "06:30"),
  t("nyc", "ruby", "Update customer ETAs for storm delays", 0, "Smart MOOV", "11:05"),
  t("nyc", "omar", "Audit returned parcels", 3, undefined, undefined),
  // New York — overdue
  t("nyc", "ruby", "Close out 4 damage claims", -4, undefined, undefined),

  // Sydney — done today
  t("syd", "hana", "Confirm weekend on-call roster", 0, "Email", "23:10"),
  t("syd", "nadia", "Restock 2 depots with packaging", 1, undefined, undefined),
  // Sydney — overdue
  t("syd", "hana", "Fix scanner sync at Parramatta", -1, undefined, undefined),
];

function t(
  groupId: string,
  assigneeId: string,
  title: string,
  dueOffset: number,
  source: Source | undefined,
  doneAt: string | undefined
): Task {
  return {
    id: `${groupId}-${assigneeId}-${title.slice(0, 8)}-${dueOffset}`
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, ""),
    title,
    groupId,
    assigneeId,
    dueOffset,
    done: Boolean(doneAt),
    doneAt,
    source,
  };
}

export function seedState(): State {
  return {
    people,
    groups,
    tasks,
    asks: [],
    role: "manager",
    currentEmployeeId: "sam", // the employee "you" act as in the demo
    currentLeaderId: "aoife", // the leader "you" act as in the demo
    bossName: "Derek",
  };
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

export function todayStart(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export function dueDate(offset: number): Date {
  const d = todayStart();
  d.setDate(d.getDate() + offset);
  return d;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function shortDate(d: Date): string {
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

// The human-friendly due label the employee asked for:
//   "Tomorrow · Jul 10", "Today · Jul 9", "Overdue · Jul 7", "In 3 days · Jul 12"
export function dueLabel(offset: number): { text: string; tone: "overdue" | "today" | "soon" | "later" } {
  const date = shortDate(dueDate(offset));
  if (offset < 0) {
    return { text: `Overdue · ${date}`, tone: "overdue" };
  }
  if (offset === 0) return { text: `Today · ${date}`, tone: "today" };
  if (offset === 1) return { text: `Tomorrow · ${date}`, tone: "soon" };
  return { text: `In ${offset} days · ${date}`, tone: "later" };
}

export function nowHM(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function todayLongLabel(): string {
  const d = new Date();
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  return `${days[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
}
