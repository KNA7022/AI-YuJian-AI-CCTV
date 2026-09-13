import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { CalibrationPage } from "./pages/CalibrationPage";
import { HistoryPage } from "./pages/HistoryPage";
import { JobPage } from "./pages/JobPage";
import { UploadPage } from "./pages/UploadPage";
import { LivePage } from "./pages/LivePage";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/live" element={<LivePage />} />
        <Route path="/jobs/:jobId/calibrate" element={<CalibrationPage />} />
        <Route path="/jobs/:jobId" element={<JobPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
