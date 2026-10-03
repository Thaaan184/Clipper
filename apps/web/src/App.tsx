import { useState } from "react";

export default function App(): JSX.Element {
  const [url, setUrl] = useState("");

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-6 text-center">
      <div className="max-w-xl w-full p-8 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-xl">
        <h1 className="text-3xl font-extrabold tracking-tight text-white mb-2">
          ClipForge <span className="text-orange-500">v2</span>
        </h1>
        <p className="text-zinc-400 text-sm mb-6">
          Signal-First, LLM-Last Gaming Video Clipper
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (url) {
              alert(`ClipForge v2 scaffold ready. Job submission: ${url}`);
            }
          }}
          className="flex flex-col gap-4 text-left"
        >
          <div>
            <label htmlFor="url-input" className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1">
              YouTube VOD URL
            </label>
            <input
              id="url-input"
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              className="w-full px-4 py-2.5 bg-zinc-950 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-orange-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            className="w-full mt-2 py-3 bg-orange-600 hover:bg-orange-500 font-bold rounded-lg text-white transition-all shadow-md active:scale-98"
          >
            Mulai Analisis Sinyal (Scaffold)
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-zinc-800 flex justify-between items-center text-xs text-zinc-500">
          <span>Engine: Signal-First (v2.0.0)</span>
          <span className="text-green-500">API: Readyz Checked</span>
        </div>
      </div>
    </div>
  );
}
