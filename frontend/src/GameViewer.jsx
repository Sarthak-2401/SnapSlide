import { useEffect, useRef, useState } from "react";
import { API, formatTime } from "./gameApi";
import "./game.css";

const phases = {
  SELECT: ["Select your frame", "Pinch opposite corners with your left and right hands, then release each pinch to lock."],
  CONFIRM: ["Confirm frame", "Close either fist briefly to capture the locked frame."],
  SHUFFLE: ["Shuffling", "Your puzzle is being shuffled."],
  PLAY: ["Solve the puzzle", "Pinch a tile, drag it over another tile, then release to swap. Hold both fists to start over."],
  SOLVED: ["Puzzle solved", "Hold both fists to play again, or stop the game."],
};

export default function GameViewer({ stream, difficulty, onStop, onFailure, onSaved }) {
  const screen = useRef(null);
  const socket = useRef(null);
  const [round, setRound] = useState(null);
  const [solution, setSolution] = useState(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    let raf = 0;
    let previousRound;
    let lastVideoTime = -1;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    const input = document.createElement("canvas");
    const capture = input.getContext("2d", { alpha: false });
    const output = screen.current;
    const display = output.getContext("2d", { alpha: false });
    const url = new URL("/ws/game", API);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.searchParams.set("difficulty", difficulty);
    const ws = new WebSocket(url);
    ws.binaryType = "blob";
    socket.current = ws;

    function fail(message) {
      if (active) {
        active = false;
        onFailure(message);
      }
    }
    function nextFrame() {
      if (!active || ws.readyState !== WebSocket.OPEN) return;
      if (video.readyState < 2 || video.currentTime === lastVideoTime) {
        raf = requestAnimationFrame(nextFrame);
        return;
      }
      lastVideoTime = video.currentTime;
      const width = Math.min(960, video.videoWidth);
      const height = Math.max(1, Math.round(width * video.videoHeight / video.videoWidth));
      if (input.width !== width || input.height !== height) {
        input.width = width;
        input.height = height;
      }
      capture.setTransform(-1, 0, 0, 1, width, 0);
      capture.drawImage(video, 0, 0, width, height);
      input.toBlob(blob => {
        if (!active || ws.readyState !== WebSocket.OPEN) return;
        if (!blob) return fail("Could not capture a webcam frame.");
        ws.send(blob);
      }, "image/jpeg", 0.78);
    }
    ws.onmessage = async ({ data }) => {
      if (!active) return;
      if (typeof data !== "string") {
        try {
          const image = await createImageBitmap(data);
          if (active) {
            if (output.width !== image.width || output.height !== image.height) {
              output.width = image.width;
              output.height = image.height;
            }
            display.drawImage(image, 0, 0);
          }
          image.close();
          if (active) nextFrame();
        } catch { fail("Could not display the camera feed."); }
        return;
      }
      const msg = JSON.parse(data);
      if (msg.error) return fail(msg.error);
      const first = !previousRound;
      if (previousRound !== msg.round_id) {
        setSolution(null);
        setBusy(false);
        setName("");
        setNotice("");
      }
      previousRound = msg.round_id;
      setRound(msg);
      if (msg.solution || msg.solution_hidden || msg.action_error || msg.score_saved) {
        setBusy(false);
        setNotice(msg.action_error || "");
      }
      if (msg.solution) setSolution(msg.solution);
      if (msg.solution_hidden) setSolution(null);
      if (msg.score_saved) onSaved();
      if (first) nextFrame();
    };
    ws.onerror = () => fail("Could not reach the SnapSlide game server on port 8000.");
    ws.onclose = () => fail("The game connection closed. Start a new session to reconnect.");
    video.play().catch(() => fail("Could not start the webcam preview."));
    const track = stream.getVideoTracks()[0];
    const ended = () => fail("Webcam access ended. Start a new session to reconnect.");
    track.addEventListener("ended", ended);
    return () => {
      active = false;
      cancelAnimationFrame(raf);
      track.removeEventListener("ended", ended);
      ws.onmessage = ws.onclose = ws.onerror = null;
      ws.close();
      socket.current = null;
      video.pause();
      video.srcObject = null;
    };
  }, [stream, difficulty, onFailure, onSaved]);

  function send(action, extra = {}) {
    if (!round || busy || socket.current?.readyState !== WebSocket.OPEN) return;
    setBusy(true);
    setNotice("");
    socket.current.send(JSON.stringify({ action, round_id: round.round_id, ...extra }));
  }
  const [title, hint] = phases[round?.state] || ["Starting camera", "Connecting hand tracking…"];
  const created = ["SHUFFLE", "PLAY", "SOLVED"].includes(round?.state);
  return (
    <main className="game-view">
      <header className="game-toolbar">
        <strong>SnapSlide · {difficulty.replace("x", "×")}</strong>
        <span aria-live="polite">{title}</span>
        <button onClick={onStop}>Stop game</button>
      </header>
      <div className="camera-stage">
        <canvas ref={screen} aria-label="Live gesture puzzle" />
        {solution && <div className="solution-panel">
          <strong>Solution</strong>
          <img src={solution} alt="Original photo in solved tile order" />
          <button disabled={busy} onClick={() => send("hide_solution")}>Hide solution</button>
        </div>}
      </div>
      <footer className="game-controls">
        <p>{hint}</p>
        {created && !solution && <button disabled={busy} onClick={() => send("solution")}>Show solution</button>}
        {created && round.state !== "SOLVED" && <small>{round.assisted ? "Practice round" : "Viewing the solution makes this a practice round."}</small>}
        {round?.state === "SOLVED" && <>
          <strong>Solved in {formatTime(round.elapsed_ms)}</strong>
          {round.saved ? <span role="status">Score saved to the leaderboard.</span>
            : round.assisted ? <span>Practice round · solution viewed</span>
            : <form onSubmit={event => { event.preventDefault(); send("score", { player: name.trim() }); }}>
                <label>Leaderboard name <input maxLength={32} required value={name} onChange={e => setName(e.target.value)} /></label>
                <button disabled={busy || !name.trim()}>Save score</button>
              </form>}
        </>}
        {notice && <span role="alert">{notice}</span>}
      </footer>
    </main>
  );
}
