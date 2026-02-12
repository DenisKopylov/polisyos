import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import Shell from "./components/layout/Shell";
import ArtifactInspector from "./pages/ArtifactInspector";
import Dashboard from "./pages/Dashboard";
import DataManagement from "./pages/DataManagement";
import LaunchRun from "./pages/LaunchRun";
import RunDetail from "./pages/RunDetail";
import RunsList from "./pages/RunsList";
import SystemHealth from "./pages/SystemHealth";

export default function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/runs" element={<RunsList />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/artifacts/:artifactId" element={<ArtifactInspector />} />
          <Route path="/launch" element={<LaunchRun />} />
          <Route path="/data" element={<DataManagement />} />
          <Route path="/health" element={<SystemHealth />} />
          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
