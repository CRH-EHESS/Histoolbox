import { NavLink } from "react-router-dom";
import { tools } from "../tools/registry";

interface AppShellProps {
  children: React.ReactNode;
}

/** Header fixe + zone de contenu principal pleine largeur. */
export function AppShell({ children }: AppShellProps) {
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors hover:bg-stone-100 ${
      isActive ? "bg-stone-100 font-medium" : ""
    }`;

  return (
    <div className="flex flex-col h-screen bg-[#fdfbf7] text-[#262626]">
      {/* Header — bande pleine largeur, intérieur contraint à 2xl max */}
      <header className="shrink-0 border-b border-stone-200 bg-white">
        <div className="flex items-center gap-4 px-6 py-2.5 max-w-screen-2xl mx-auto w-full">
          {/* Logo */}
          <div className="flex items-center gap-2 mr-2">
            <span className="text-xl">📜</span>
            <span className="font-semibold text-sm tracking-wide">Histoolbox</span>
          </div>

          {/* Navigation — générée depuis le registre des tools */}
          <nav className="flex gap-1">
            <NavLink to="/" end className={navLinkClass}>
              <span>🏠</span>
              <span>Accueil</span>
            </NavLink>
            {tools
              .filter((t) => t.available)
              .map((tool) => (
                <NavLink key={tool.id} to={tool.entryPath} className={navLinkClass}>
                  <span>{tool.icon}</span>
                  <span>{tool.label}</span>
                </NavLink>
              ))}
          </nav>
        </div>
      </header>

      {/* Contenu principal — 90 % de largeur, centré */}
      <main className="flex-1 overflow-hidden w-[90%] mx-auto">{children}</main>
    </div>
  );
}
