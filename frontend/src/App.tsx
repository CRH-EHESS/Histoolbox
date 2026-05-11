import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { AppShell } from "./components/AppShell";
import { HomePage } from "./pages/HomePage";
import { OCRUploadPage } from "./pages/OCRUploadPage";
import { OCRWaitingPage } from "./pages/OCRWaitingPage";
import { OCRToolboxPage } from "./pages/OCRToolboxPage";
import { getProjectsByStatus, updateProject } from "./db";
import { api } from "./lib/apiClient";

/**
 * Recovery au démarrage : relance le polling pour les tâches `processing`
 * trouvées dans IndexedDB (cas de fermeture de l'onglet en cours de traitement).
 */
function RecoveryWatcher() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    async function recover() {
      const processing = await getProjectsByStatus("processing");
      for (const project of processing) {
        try {
          const { status } = await api.getStatus(project.id);
          if (status === "completed") {
            const result = await api.getResult(project.id);
            await updateProject(project.id, {
              markdownContent: result.markdown,
              status: "completed",
            });
            if (location.pathname.includes(project.id)) {
              navigate(`/ocr/toolbox/${project.id}`);
            }
          } else if (status === "error") {
            await updateProject(project.id, { status: "error" });
          } else {
            // Toujours en cours → naviguer vers la page d'attente pour relancer le poll
            if (!location.pathname.includes(project.id)) {
              navigate(`/ocr/waiting/${project.id}`);
            }
          }
        } catch {
          // Backend inaccessible — on laisse la tâche en processing
        }
      }
    }
    recover();
  }, [navigate, location.pathname]);

  return null;
}

function App() {
  return (
    <BrowserRouter>
      <RecoveryWatcher />
      <AppShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/ocr/upload" element={<OCRUploadPage />} />
          <Route path="/ocr/waiting/:taskId" element={<OCRWaitingPage />} />
          <Route path="/ocr/toolbox/:taskId" element={<OCRToolboxPage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

export default App;
