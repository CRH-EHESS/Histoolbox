import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { HomePage } from "./pages/HomePage";
import { tools } from "./tools/registry";

function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
}

export default App;
