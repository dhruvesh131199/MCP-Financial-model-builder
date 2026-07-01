import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import SessionPage from "./pages/SessionPage";
import SessionRagChunksPage from "./pages/SessionRagChunksPage";
import SetupPage from "./pages/SetupPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/s/:sessionId" element={<SessionPage />} />
        <Route
          path="/s/:sessionId/rag/:documentId/chunks"
          element={<SessionRagChunksPage />}
        />
      </Routes>
    </BrowserRouter>
  );
}
