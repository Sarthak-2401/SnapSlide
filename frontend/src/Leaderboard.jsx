import { useEffect, useState } from "react";
import { API, formatTime } from "./gameApi";

export default function Leaderboard({ difficulty, revision }) {
  const [result, setResult] = useState(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    async function load() {
      try {
        const res = await fetch(`${API}/api/leaderboard?difficulty=${difficulty}`, { signal: abort.signal });
        if (!res.ok) throw Error();
        const rows = await res.json();
        if (!abort.signal.aborted) setResult({ difficulty, rows });
      } catch {
        if (!abort.signal.aborted) setResult({ difficulty, error: true });
      }
    }
    load();
    window.addEventListener("focus", load);
    return () => { abort.abort(); window.removeEventListener("focus", load); };
  }, [difficulty, revision, retry]);
  return <section id="leaderboard" className="scores">
    <h2>Top Solvers · {difficulty.replace("x", "×")}</h2>
    <p>Fastest unassisted solves for the selected grid.</p>
    {result?.difficulty !== difficulty ? <p>Loading scores…</p>
      : result.error ? <p>Could not load scores. <button onClick={() => setRetry(retry + 1)}>Retry</button></p>
      : !result.rows.length ? <p>No scores yet. Be the first to solve this grid.</p>
      : <table><thead><tr><th>Rank</th><th>Player</th><th>Time</th></tr></thead>
          <tbody>{result.rows.map((row, i) => <tr key={i}><td>#{i + 1}</td><td>{row.player}</td><td>{formatTime(row.elapsed_ms)}</td></tr>)}</tbody></table>}
  </section>;
}
