export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function formatTime(ms) {
  const centiseconds = Math.floor(ms / 10);
  const seconds = Math.floor(centiseconds / 100);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}.${String(centiseconds % 100).padStart(2, "0")}`;
}
