import { BrowserRouter, Route, Routes } from "react-router-dom";
import HoursBanner from "./components/HoursBanner";
import HomePage from "./pages/HomePage";
import SessionPage from "./pages/SessionPage";
import SessionRagChunksPage from "./pages/SessionRagChunksPage";
import SetupPage from "./pages/SetupPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-dvh flex-col">
        <HoursBanner />
        <div className="min-h-0 flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/s/:sessionId" element={<SessionPage />} />
            <Route
              path="/s/:sessionId/rag/:documentId/chunks"
              element={<SessionRagChunksPage />}
            />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
