import { useState } from "react";
import { useStore } from "./store";
import { TopBar } from "./components/TopBar";
import { DailySheet } from "./components/DailySheet";
import { DailyStatus } from "./components/DailyStatus";
import { Groups } from "./components/Groups";
import { LeaderView } from "./components/LeaderView";
import { MyTasks } from "./components/MyTasks";

export default function App() {
  const state = useStore();
  const [managerTab, setManagerTab] = useState("sheet");

  // Badge count: open questions waiting on the current group leader.
  const leaderGroup = state.groups.find((g) => g.leadId === state.currentLeaderId);
  const leaderTaskIds = new Set(
    state.tasks.filter((t) => t.groupId === leaderGroup?.id).map((t) => t.id)
  );
  const pendingForLeader = state.asks.filter((a) => leaderTaskIds.has(a.taskId) && !a.answeredAt).length;

  return (
    <>
      <TopBar
        state={state}
        managerTab={managerTab}
        setManagerTab={setManagerTab}
        pendingForLeader={pendingForLeader}
      />
      {state.role === "manager" && managerTab === "sheet" && <DailySheet state={state} />}
      {state.role === "manager" && managerTab === "status" && <DailyStatus state={state} />}
      {state.role === "manager" && managerTab === "groups" && <Groups state={state} />}
      {state.role === "leader" && <LeaderView state={state} />}
      {state.role === "employee" && <MyTasks state={state} />}
    </>
  );
}
