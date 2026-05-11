import { useNavigate } from "react-router-dom";
import { tools } from "../tools/registry";

/** Page d'accueil — grille de cartes générée depuis le registre des tools. */
export function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-6xl mx-auto px-8 py-10">
        <h1 className="text-2xl font-bold mb-2">Histoolbox</h1>
        <p className="text-stone-500 mb-8">
          Plateforme modulaire de traitement de documents anciens.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
          {tools.map((tool) =>
            tool.available ? (
              <button
                key={tool.id}
                onClick={() => navigate(tool.entryPath)}
                className="group text-left rounded-xl border border-stone-200 bg-white p-6 shadow-sm hover:shadow-md hover:border-stone-300 transition-all"
              >
                <div className="text-3xl mb-3">{tool.icon}</div>
                <h2 className="font-semibold text-lg mb-1 group-hover:text-stone-700">
                  {tool.label}
                </h2>
                <p className="text-stone-500 text-sm">{tool.description}</p>
              </button>
            ) : (
              <div
                key={tool.id}
                className="rounded-xl border border-dashed border-stone-200 p-6 opacity-40 select-none"
              >
                <div className="text-3xl mb-3">{tool.icon}</div>
                <h2 className="font-semibold text-lg mb-1">{tool.label}</h2>
                <p className="text-stone-400 text-sm">Bientôt disponible</p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
