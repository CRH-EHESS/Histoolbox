import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { TokenGate } from "./components/TokenGate";
import { HomePage } from "./pages/HomePage";
import { tools } from "./tools/registry";

function App() {
  return (
    <BrowserRouter basename={import.meta.env.VITE_BASE_PATH ?? "/"}>
      <TokenGate>
        {/* Composants de recovery déclarés par chaque tool (null-renders) */}
        {tools.map(({ id, Recovery }) =>
          Recovery ? <Recovery key={id} /> : null
        )}

        <AppShell>
          <Routes>
            <Route path="/" element={<HomePage />} />
            {tools.flatMap(({ id, routes }) =>
              routes.map((route) => (
                <Route key={`${id}-${route.path}`} path={route.path} element={route.element} />
              ))
            )}
          </Routes>
        </AppShell>
      </TokenGate>
    </BrowserRouter>
  );
}

export default App;
