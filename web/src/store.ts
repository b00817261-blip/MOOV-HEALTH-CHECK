// A tiny external store so state (tasks, groups, "why" questions and answers)
// survives switching between the Manager / Group leader / Employee views and a
// page refresh. Persisted to localStorage — no backend needed for the demo.

import { useSyncExternalStore } from "react";
import {
  AskWhy,
  Group,
  Person,
  Role,
  Source,
  State,
  nowHM,
  seedState,
} from "./data";

const KEY = "moov-daily-v1";

function load(): State {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as State;
  } catch {
    /* ignore malformed storage */
  }
  return seedState();
}

let state: State = load();
const listeners = new Set<() => void>();

function persist() {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* storage may be full/blocked — the UI still works in-memory */
  }
}

function set(next: State) {
  state = next;
  persist();
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useStore(): State {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export const actions = {
  setRole(role: Role) {
    set({ ...state, role });
  },

  setCurrentEmployee(id: string) {
    set({ ...state, currentEmployeeId: id });
  },

  setCurrentLeader(id: string) {
    set({ ...state, currentLeaderId: id });
  },

  markDone(taskId: string, source: Source) {
    set({
      ...state,
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, done: true, doneAt: nowHM(), source } : t
      ),
    });
  },

  reopen(taskId: string) {
    set({
      ...state,
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, done: false, doneAt: undefined, source: undefined } : t
      ),
    });
  },

  // Boss asks a group leader why an overdue task hasn't been done.
  askWhy(taskId: string, fromName: string) {
    if (state.asks.some((a) => a.taskId === taskId && !a.answeredAt)) return; // don't double-ask
    const ask: AskWhy = {
      id: `ask-${taskId}-${state.asks.length}`,
      taskId,
      fromName,
      askedAt: nowHM(),
    };
    set({ ...state, asks: [...state.asks, ask] });
  },

  // Group leader answers a "why" question (choice and/or free text).
  answerAsk(askId: string, choice: string, note: string) {
    set({
      ...state,
      asks: state.asks.map((a) =>
        a.id === askId
          ? { ...a, answerChoice: choice || undefined, answerNote: note || undefined, answeredAt: nowHM() }
          : a
      ),
    });
  },

  addGroup(name: string, leadId: string, memberIds: string[]) {
    const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `g${state.groups.length}`;
    const group: Group = { id, name, leadId, memberIds };
    set({ ...state, groups: [...state.groups, group] });
  },

  addMember(groupId: string, personId: string) {
    set({
      ...state,
      groups: state.groups.map((g) =>
        g.id === groupId && !g.memberIds.includes(personId)
          ? { ...g, memberIds: [...g.memberIds, personId] }
          : g
      ),
    });
  },

  registerPerson(name: string): Person {
    const id = `p-${Date.now().toString(36)}`;
    const person: Person = { id, name: name.trim(), registered: true };
    set({ ...state, people: [...state.people, person] });
    return person;
  },

  resetDemo() {
    set(seedState());
  },
};

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

export function personName(s: State, id: string): string {
  return s.people.find((p) => p.id === id)?.name ?? "Unknown";
}

export function groupById(s: State, id: string): Group | undefined {
  return s.groups.find((g) => g.id === id);
}

export function openAskFor(s: State, taskId: string): AskWhy | undefined {
  // The most recent ask for a task.
  return [...s.asks].reverse().find((a) => a.taskId === taskId);
}
