import { useState } from "react";
import { getStoredToken, storeToken } from "../lib/apiClient";

interface TokenGateProps {
  children: React.ReactNode;
}

/**
 * Bloque le rendu si aucun token d'accès n'est stocké dans localStorage.
 * Affiche un formulaire de saisie minimaliste. Une fois validé, recharge la page.
 *
 * Ignoré si VITE_API_KEY_REQUIRED n'est pas "true" (dev local sans auth).
 */
export function TokenGate({ children }: TokenGateProps) {
  const authRequired = import.meta.env.VITE_API_KEY_REQUIRED === "true";
  const [token, setToken] = useState("");
  const [error, setError] = useState(false);

  if (!authRequired || getStoredToken()) {
    return <>{children}</>;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = token.trim();
    if (!trimmed) {
      setError(true);
      return;
    }
    storeToken(trimmed);
    // Recharge pour que tous les hooks/composants repartent proprement
    window.location.reload();
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fdfbf7]">
      <div className="w-full max-w-sm px-8 py-10 bg-white rounded-2xl shadow-md border border-stone-100">
        <h1 className="text-lg font-bold text-stone-800 mb-1">Histoolbox</h1>
        <p className="text-sm text-stone-500 mb-6">
          Accès réservé aux bêta-testeurs. Entrez votre clé d'accès.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="password"
            autoFocus
            autoComplete="current-password"
            placeholder="Clé d'accès"
            value={token}
            onChange={(e) => { setToken(e.target.value); setError(false); }}
            className={`w-full rounded-lg border px-4 py-2.5 text-sm outline-none transition-colors ${
              error
                ? "border-red-400 focus:border-red-500"
                : "border-stone-300 focus:border-stone-500"
            }`}
          />
          {error && (
            <p className="text-xs text-red-600">La clé ne peut pas être vide.</p>
          )}
          <button
            type="submit"
            className="rounded-lg bg-stone-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-stone-700 transition-colors"
          >
            Accéder
          </button>
        </form>
      </div>
    </div>
  );
}
