import { useState, useEffect, useRef } from "react";

const LEADERBOARD = [
  { rank: 1, player: "Alex Rivera", grid: "3x3", time: "12.4s", avatar: "AR" },
  { rank: 2, player: "Sarah Chen",  grid: "4x4", time: "34.1s", avatar: "SC" },
  { rank: 3, player: "Mark Johnson",grid: "3x3", time: "14.8s", avatar: "MJ" },
  { rank: 4, player: "Elena Rossi", grid: "5x5", time: "1:42.5",avatar: "ER" },
  { rank: 5, player: "Kenji Tanaka",grid: "4x4", time: "29.6s", avatar: "KT" },
];

const HOW_IT_WORKS = [
  { icon: "📷", step: "01", title: "Start Webcam",   desc: "The app captures a live feed from your camera in real time." },
  { icon: "🤌", step: "02", title: "Select Frame",   desc: "Pinch with left hand (top-left corner) and right hand (bottom-right) then release to lock." },
  { icon: "✊", step: "03", title: "Capture Image",  desc: "Both corners locked → puzzle is sliced and shuffled automatically." },
  { icon: "👋", step: "04", title: "Solve It",       desc: "Pinch a tile, drag it, release over target tile to swap. Both fists = reset." },
];

const API = "http://localhost:8000";

// ── Animated tile background ──────────────────────────────────────────────────
function PuzzleBackground() {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);
    const G = 3, T = 90;
    const COLS = Math.ceil(window.innerWidth  / (T + G)) + 2;
    const ROWS = Math.ceil(window.innerHeight / (T + G)) + 2;
    const tiles = [];
    for (let r = 0; r < ROWS; r++)
      for (let c = 0; c < COLS; c++) {
        const hue = 160 + (r * 3 + c * 7) % 60;
        tiles.push({ x: c*(T+G), y: r*(T+G), tx: c*(T+G), ty: r*(T+G),
          w: T, h: T, hue, label: `${(r%5)*5+(c%5)+1}`,
          depth: 0.4 + Math.random()*0.6, phase: Math.random()*Math.PI*2,
          shuffleT: 0, shuffleDelay: Math.random()*8000 });
      }
    let lastTime = 0;
    function drawTile(tile, t) {
      const px = tile.x + Math.sin(t*.0008+tile.phase)*3;
      const py = tile.y + Math.cos(t*.0006+tile.phase*1.3)*2;
      const a  = 0.12 + tile.depth*.1 + Math.sin(t*.001+tile.phase)*.03;
      ctx.save();
      const cx = px+tile.w/2, cy = py+tile.h/2;
      const sy = 0.85+Math.abs(Math.sin(tile.phase+t*.0005))*.15;
      ctx.translate(cx,cy); ctx.scale(1,sy); ctx.translate(-cx,-cy);
      const rr = 10;
      ctx.beginPath();
      ctx.moveTo(px+rr,py); ctx.lineTo(px+tile.w-rr,py);
      ctx.quadraticCurveTo(px+tile.w,py,px+tile.w,py+rr);
      ctx.lineTo(px+tile.w,py+tile.h-rr);
      ctx.quadraticCurveTo(px+tile.w,py+tile.h,px+tile.w-rr,py+tile.h);
      ctx.lineTo(px+rr,py+tile.h);
      ctx.quadraticCurveTo(px,py+tile.h,px,py+tile.h-rr);
      ctx.lineTo(px,py+rr); ctx.quadraticCurveTo(px,py,px+rr,py);
      ctx.closePath();
      const g = ctx.createLinearGradient(px,py,px+tile.w,py+tile.h);
      g.addColorStop(0,`hsla(${tile.hue},70%,55%,${a})`);
      g.addColorStop(1,`hsla(${tile.hue+20},60%,40%,${a*.6})`);
      ctx.fillStyle = g; ctx.fill();
      ctx.strokeStyle=`hsla(${tile.hue},80%,70%,${a*1.5})`; ctx.lineWidth=0.5; ctx.stroke();
      ctx.fillStyle=`hsla(${tile.hue},80%,80%,${a*2.5})`;
      ctx.font=`bold ${12*tile.depth}px monospace`;
      ctx.textAlign="center"; ctx.textBaseline="middle";
      ctx.fillText(tile.label,px+tile.w/2,py+tile.h/2);
      ctx.restore();
    }
    function animate(ts) {
      const dt = ts - lastTime; lastTime = ts;
      ctx.clearRect(0,0,canvas.width,canvas.height);
      tiles.forEach(tile => {
        if (ts > tile.shuffleDelay) {
          tile.shuffleT += dt;
          const period = 5000+tile.phase*2000;
          if (tile.shuffleT > period) {
            tile.shuffleT = 0;
            tile.tx = Math.floor(Math.random()*Math.ceil(canvas.width/(T+G)))*(T+G);
            tile.ty = Math.floor(Math.random()*Math.ceil(canvas.height/(T+G)))*(T+G);
          }
          tile.x += (tile.tx-tile.x)*.015;
          tile.y += (tile.ty-tile.y)*.015;
        }
        drawTile(tile, ts);
      });
      animRef.current = requestAnimationFrame(animate);
    }
    animRef.current = requestAnimationFrame(animate);
    return () => { cancelAnimationFrame(animRef.current); window.removeEventListener("resize",resize); };
  }, []);
  return (
    <canvas ref={canvasRef} style={{
      position:"fixed",inset:0,width:"100vw",height:"100vh",
      zIndex:0,pointerEvents:"none",
      background:"linear-gradient(135deg,#050d10 0%,#071820 40%,#050e14 100%)",
    }}/>
  );
}

// ── Game viewer overlay (full-screen MJPEG + controls) ────────────────────────
function GameViewer({ onStop, gameState }) {
  const stateLabels = {
    SELECT:  { label: "PHASE 1: SELECT",  color: "#00c9e5", hint: "Left pinch = top-left corner  |  Right pinch = bottom-right corner  |  Release to lock" },
    SHUFFLE: { label: "SHUFFLING…",       color: "#f0c040", hint: "Sit tight, tiles are being scrambled" },
    PLAY:    { label: "PHASE 2: SOLVE",   color: "#00e5a0", hint: "Pinch a tile → drag → release to swap  |  Both fists = reset" },
    SOLVED:  { label: "SOLVED!",          color: "#a78bfa", hint: "Show both fists to play again" },
  };
  const info = stateLabels[gameState] || stateLabels.SELECT;

  return (
    <div style={{
      position:"fixed", inset:0, zIndex:100,
      background:"#050d10",
      display:"flex", flexDirection:"column",
    }}>
      {/* Top bar */}
      <div style={{
        display:"flex", alignItems:"center", justifyContent:"space-between",
        padding:"10px 20px",
        background:"rgba(0,0,0,0.6)",
        borderBottom:"1px solid rgba(0,229,160,0.15)",
        flexShrink:0,
      }}>
        {/* Logo */}
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <div style={{
            width:32,height:32,borderRadius:8,
            background:"linear-gradient(135deg,#00e5a0,#00c9e5)",
            display:"flex",alignItems:"center",justifyContent:"center",
            fontWeight:"bold",fontSize:13,color:"#050d10",
          }}>G</div>
          <span style={{ color:"#e0f5ef",fontWeight:600,fontSize:14,letterSpacing:"0.02em",fontFamily:"'DM Mono',monospace" }}>
            GesturePuzzle
          </span>
        </div>

        {/* Phase badge */}
        <div style={{
          background:`${info.color}15`,
          border:`1px solid ${info.color}50`,
          borderRadius:100,padding:"5px 16px",
          fontSize:12,fontWeight:700,color:info.color,
          letterSpacing:"0.08em",fontFamily:"'DM Mono',monospace",
        }}>
          {info.label}
        </div>

        {/* Stop button */}
        <button onClick={onStop} style={{
          background:"rgba(220,60,60,0.12)",
          border:"1px solid rgba(220,60,60,0.35)",
          borderRadius:8,padding:"7px 18px",
          color:"#ff8080",fontSize:12,fontWeight:600,
          cursor:"pointer",fontFamily:"'DM Mono',monospace",
          letterSpacing:"0.04em",transition:"background 0.2s",
        }}
          onMouseEnter={e=>e.currentTarget.style.background="rgba(220,60,60,0.22)"}
          onMouseLeave={e=>e.currentTarget.style.background="rgba(220,60,60,0.12)"}
        >
          ⏹ Stop Game
        </button>
      </div>

      {/* Camera feed — fills all remaining space */}
      <div style={{ flex:1, overflow:"hidden", position:"relative", background:"#000" }}>
        <img
          src={`${API}/video_feed`}
          alt="game feed"
          style={{
            width:"100%", height:"100%",
            objectFit:"contain",
            display:"block",
          }}
        />
      </div>

      {/* Hint bar */}
      <div style={{
        padding:"8px 20px",
        background:"rgba(0,0,0,0.55)",
        borderTop:"1px solid rgba(0,229,160,0.1)",
        flexShrink:0,
        textAlign:"center",
        fontSize:12,color:"rgba(170,220,200,0.6)",
        fontFamily:"'DM Mono',monospace",
        letterSpacing:"0.04em",
      }}>
        {info.hint}
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [selectedDiff, setSelectedDiff] = useState("3x3");
  const [hoveredRow,   setHoveredRow]   = useState(null);
  // idle | loading | running | error
  const [gameStatus,  setGameStatus]  = useState("idle");
  const [gameState,   setGameState]   = useState("SELECT");  // SELECT/SHUFFLE/PLAY/SOLVED
  const [errorMsg,    setErrorMsg]    = useState("");
  const wsRef = useRef(null);

  // ── Connect WebSocket to receive state events while game runs ──────────────
  useEffect(() => {
    if (gameStatus !== "running") {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
      return;
    }
    const ws = new WebSocket(`ws://localhost:8000/ws/state`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.state)  setGameState(msg.state);
        if (msg.event === "stopped") { setGameStatus("idle"); setGameState("SELECT"); }
        if (msg.event === "error")   { setGameStatus("error"); setErrorMsg(msg.msg || "Game error"); }
      } catch {}
    };
    ws.onerror = () => {};
    wsRef.current = ws;
    return () => { ws.close(); wsRef.current = null; };
  }, [gameStatus]);

  // ── Also poll /api/status so we detect if server restarts ─────────────────
  useEffect(() => {
    if (gameStatus !== "running") return;
    const id = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/status`);
        const d = await r.json();
        if (!d.running) { setGameStatus("idle"); setGameState("SELECT"); }
      } catch {}
    }, 3000);
    return () => clearInterval(id);
  }, [gameStatus]);

  const startGame = async () => {
    if (gameStatus === "loading" || gameStatus === "running") return;
    setGameStatus("loading");
    setErrorMsg("");
    try {
      const res  = await fetch(`${API}/api/start`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({ difficulty: selectedDiff }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Server error");
      setGameState("SELECT");
      setGameStatus("running");
    } catch (err) {
      setGameStatus("error");
      setErrorMsg(err.message || "Could not connect to backend server.");
    }
  };

  const stopGame = async () => {
    try { await fetch(`${API}/api/stop`, { method:"POST" }); } catch {}
    setGameStatus("idle");
    setGameState("SELECT");
  };

  const diffs = [
    { id:"3x3", label:"3×3", tag:"Beginner", desc:"Perfect for getting used to gesture controls.", color:"#00e5a0" },
    { id:"4x4", label:"4×4", tag:"Standard", desc:"The classic sliding puzzle challenge.",         color:"#00c9e5" },
    { id:"5x5", label:"5×5", tag:"Pro",      desc:"Advanced spatial reasoning required.",          color:"#a78bfa" },
  ];

  const btnDisabled = gameStatus === "loading" || gameStatus === "running";
  const btnLabel    = gameStatus === "loading" ? "Launching…"
                    : gameStatus === "running"  ? "Running ✓" : null;

  // ── Shared start button styles ─────────────────────────────────────────────
  const navBtnStyle = {
    background: btnDisabled ? "rgba(0,229,160,0.3)" : "linear-gradient(135deg,#00e5a0,#00b894)",
    border:"none", borderRadius:100, padding:"9px 22px",
    color:"#050d10", fontWeight:700, fontSize:13,
    cursor: btnDisabled ? "not-allowed" : "pointer",
    letterSpacing:"0.03em", transition:"transform 0.15s, box-shadow 0.2s",
    boxShadow: btnDisabled ? "none" : "0 4px 20px rgba(0,229,160,0.25)",
    opacity: btnDisabled ? 0.7 : 1,
  };

  const heroBtnStyle = {
    background: btnDisabled ? "rgba(0,229,160,0.3)" : "linear-gradient(135deg,#00e5a0,#00b894)",
    border:"none", borderRadius:12, padding:"14px 36px",
    color:"#050d10", fontWeight:700, fontSize:15,
    cursor: btnDisabled ? "not-allowed" : "pointer",
    display:"flex", alignItems:"center", gap:8,
    transition:"transform 0.15s, box-shadow 0.2s",
    boxShadow: btnDisabled ? "none" : "0 8px 32px rgba(0,229,160,0.3)",
    opacity: btnDisabled ? 0.7 : 1,
  };

  return (
    <div style={{ minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center",
      padding:"24px 16px", position:"relative", fontFamily:"'DM Mono','Courier New',monospace" }}>

      <PuzzleBackground />

      {/* Full-screen game viewer — rendered on top when running */}
      {gameStatus === "running" && (
        <GameViewer onStop={stopGame} gameState={gameState} />
      )}

      {/* Landing page card */}
      <div style={{
        position:"relative", zIndex:10, width:"100%", maxWidth:"960px",
        borderRadius:"24px", background:"rgba(6,20,28,0.82)",
        backdropFilter:"blur(28px)", WebkitBackdropFilter:"blur(28px)",
        border:"1px solid rgba(0,229,160,0.18)",
        boxShadow:"0 0 80px rgba(0,229,160,0.06),0 32px 80px rgba(0,0,0,0.6),inset 0 1px 0 rgba(255,255,255,0.04)",
        overflow:"hidden",
      }}>

        {/* Nav */}
        <nav style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"20px 36px", borderBottom:"1px solid rgba(0,229,160,0.08)" }}>
          <div style={{ display:"flex", alignItems:"center", gap:"10px" }}>
            <div style={{ width:36,height:36,borderRadius:10,
              background:"linear-gradient(135deg,#00e5a0,#00c9e5)",
              display:"flex",alignItems:"center",justifyContent:"center",
              fontWeight:"bold",fontSize:14,color:"#050d10" }}>G</div>
            <span style={{ color:"#e0f5ef",fontWeight:600,fontSize:15,letterSpacing:"0.02em" }}>GesturePuzzle</span>
          </div>
          <div style={{ display:"flex", gap:"32px", alignItems:"center" }}>
            {["Home","Leaderboard","How It Works"].map(l => (
              <a key={l} href="#" onClick={e=>e.preventDefault()} style={{
                color:"rgba(200,240,225,0.55)",fontSize:13,textDecoration:"none",
                letterSpacing:"0.03em",transition:"color 0.2s" }}
                onMouseEnter={e=>e.target.style.color="#00e5a0"}
                onMouseLeave={e=>e.target.style.color="rgba(200,240,225,0.55)"}
              >{l}</a>
            ))}
            <button onClick={startGame} disabled={btnDisabled} style={navBtnStyle}
              onMouseEnter={e=>{ if(!btnDisabled){e.currentTarget.style.transform="scale(1.04)";e.currentTarget.style.boxShadow="0 4px 28px rgba(0,229,160,0.45)";} }}
              onMouseLeave={e=>{ e.currentTarget.style.transform="scale(1)";e.currentTarget.style.boxShadow="0 4px 20px rgba(0,229,160,0.25)"; }}
            >{btnLabel || "Start Game"}</button>
          </div>
        </nav>

        {/* Hero */}
        <section style={{ padding:"64px 56px 48px", textAlign:"center" }}>
          <div style={{ display:"inline-block",background:"rgba(0,229,160,0.08)",
            border:"1px solid rgba(0,229,160,0.22)",borderRadius:100,
            padding:"5px 16px",fontSize:11,letterSpacing:"0.12em",
            color:"#00e5a0",marginBottom:"24px",textTransform:"uppercase" }}>
            Computer Vision · Gesture Control · AI
          </div>
          <h1 style={{ margin:"0 0 20px",fontSize:"clamp(32px,5vw,56px)",fontWeight:800,
            lineHeight:1.1,color:"#e8f8f2",fontFamily:"'DM Mono',monospace",letterSpacing:"-0.02em" }}>
            Solve Puzzles with{" "}
            <span style={{ background:"linear-gradient(90deg,#00e5a0,#00c9e5)",
              WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent" }}>Hand Gestures</span>
          </h1>
          <p style={{ color:"rgba(190,230,215,0.65)",fontSize:17,maxWidth:540,
            margin:"0 auto 36px",lineHeight:1.7 }}>
            Solve a puzzle generated from your webcam using only hand gestures.
            No mouse. No keyboard. Just you and your hands.
          </p>
          <div style={{ display:"flex",gap:"12px",justifyContent:"center",flexWrap:"wrap" }}>
            <button onClick={startGame} disabled={btnDisabled} style={heroBtnStyle}
              onMouseEnter={e=>{ if(!btnDisabled){e.currentTarget.style.transform="translateY(-2px)";e.currentTarget.style.boxShadow="0 12px 40px rgba(0,229,160,0.45)";} }}
              onMouseLeave={e=>{ e.currentTarget.style.transform="translateY(0)";e.currentTarget.style.boxShadow="0 8px 32px rgba(0,229,160,0.3)"; }}
            >
              {btnLabel ? <>{btnLabel}</> : <>Start Your Session <span>→</span></>}
            </button>
            <button style={{ background:"transparent",border:"1px solid rgba(0,229,160,0.25)",
              borderRadius:12,padding:"14px 28px",color:"#00e5a0",fontWeight:600,fontSize:15,
              cursor:"pointer",transition:"background 0.2s" }}
              onMouseEnter={e=>e.currentTarget.style.background="rgba(0,229,160,0.06)"}
              onMouseLeave={e=>e.currentTarget.style.background="transparent"}
            >Watch Demo</button>
          </div>

          {/* Error banner */}
          {gameStatus === "error" && (
            <div style={{ marginTop:28,borderRadius:14,border:"1px solid rgba(220,60,60,0.3)",
              background:"rgba(220,60,60,0.08)",padding:"16px 20px",
              display:"flex",alignItems:"flex-start",gap:14,
              maxWidth:480,margin:"28px auto 0",textAlign:"left" }}>
              <span style={{ fontSize:18,flexShrink:0,marginTop:1 }}>⚠️</span>
              <div style={{ flex:1 }}>
                <div style={{ color:"#ff6b6b",fontSize:13,fontWeight:700,marginBottom:4 }}>Failed to start</div>
                <div style={{ color:"rgba(170,210,195,0.65)",fontSize:12,lineHeight:1.6 }}>{errorMsg}</div>
                <div style={{ marginTop:8,fontSize:11,color:"rgba(150,200,180,0.4)",fontFamily:"monospace" }}>
                  Make sure <code style={{ background:"rgba(255,255,255,0.06)",padding:"1px 6px",borderRadius:4 }}>server.py</code> is running on port 8000
                </div>
              </div>
              <button onClick={()=>setGameStatus("idle")} style={{
                background:"none",border:"none",color:"rgba(150,200,180,0.4)",
                cursor:"pointer",fontSize:16,padding:0,flexShrink:0 }}>✕</button>
            </div>
          )}
        </section>

        <div style={{ height:1,background:"linear-gradient(90deg,transparent,rgba(0,229,160,0.12),transparent)",margin:"0 40px" }}/>

        {/* Difficulty */}
        <section style={{ padding:"48px 56px" }}>
          <h2 style={{ textAlign:"center",color:"#e8f8f2",marginBottom:6,fontSize:20,fontWeight:700 }}>Select Difficulty</h2>
          <p style={{ textAlign:"center",color:"rgba(150,200,180,0.5)",fontSize:13,marginBottom:32 }}>Choose your grid size before starting</p>
          <div style={{ display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:16 }}>
            {diffs.map(d => (
              <button key={d.id} onClick={()=>{ if(!btnDisabled) setSelectedDiff(d.id); }} style={{
                background: selectedDiff===d.id
                  ? `rgba(${d.color==="#00e5a0"?"0,229,160":d.color==="#00c9e5"?"0,201,229":"167,139,250"},0.1)`
                  : "rgba(255,255,255,0.03)",
                border:`1.5px solid ${selectedDiff===d.id?d.color:"rgba(255,255,255,0.06)"}`,
                borderRadius:16,padding:"24px 20px",textAlign:"left",
                cursor:btnDisabled?"not-allowed":"pointer",
                opacity:btnDisabled&&selectedDiff!==d.id?0.5:1,
                transition:"all 0.2s",
                boxShadow:selectedDiff===d.id?`0 0 24px ${d.color}22`:"none",
                transform:selectedDiff===d.id?"translateY(-3px)":"none",
              }}
                onMouseEnter={e=>{ if(selectedDiff!==d.id&&!btnDisabled) e.currentTarget.style.background="rgba(255,255,255,0.05)"; }}
                onMouseLeave={e=>{ if(selectedDiff!==d.id) e.currentTarget.style.background="rgba(255,255,255,0.03)"; }}
              >
                <div style={{ fontSize:11,letterSpacing:"0.1em",color:d.color,marginBottom:8,fontWeight:600 }}>{d.tag}</div>
                <div style={{ fontSize:28,fontWeight:800,color:"#e8f8f2",marginBottom:8 }}>{d.label} Grid</div>
                <div style={{ fontSize:12,color:"rgba(160,210,190,0.55)",lineHeight:1.6 }}>{d.desc}</div>
                {selectedDiff===d.id && (
                  <div style={{ marginTop:16,display:"inline-flex",alignItems:"center",gap:6,
                    background:`${d.color}18`,border:`1px solid ${d.color}44`,
                    borderRadius:100,padding:"4px 12px",fontSize:10,color:d.color,letterSpacing:"0.08em" }}>✓ SELECTED</div>
                )}
              </button>
            ))}
          </div>
        </section>

        <div style={{ height:1,background:"linear-gradient(90deg,transparent,rgba(0,229,160,0.12),transparent)",margin:"0 40px" }}/>

        {/* How It Works */}
        <section style={{ padding:"48px 56px" }}>
          <h2 style={{ textAlign:"center",color:"#e8f8f2",marginBottom:6,fontSize:20,fontWeight:700 }}>How It Works</h2>
          <p style={{ textAlign:"center",color:"rgba(150,200,180,0.5)",fontSize:13,marginBottom:36 }}>Four simple steps to get started</p>
          <div style={{ display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(200px,1fr))",gap:20 }}>
            {HOW_IT_WORKS.map((h,i) => (
              <div key={i} style={{ background:"rgba(255,255,255,0.02)",border:"1px solid rgba(255,255,255,0.05)",
                borderRadius:16,padding:"24px 20px",position:"relative",overflow:"hidden" }}>
                <div style={{ position:"absolute",top:16,right:16,fontSize:11,fontWeight:700,
                  color:"rgba(0,229,160,0.18)",letterSpacing:"0.05em" }}>{h.step}</div>
                <div style={{ fontSize:28,marginBottom:12 }}>{h.icon}</div>
                <div style={{ color:"#d0f0e4",fontSize:14,fontWeight:600,marginBottom:8 }}>{h.title}</div>
                <div style={{ color:"rgba(150,200,180,0.55)",fontSize:12,lineHeight:1.7 }}>{h.desc}</div>
              </div>
            ))}
          </div>
        </section>

        <div style={{ height:1,background:"linear-gradient(90deg,transparent,rgba(0,229,160,0.12),transparent)",margin:"0 40px" }}/>

        {/* Leaderboard */}
        <section style={{ padding:"48px 56px" }}>
          <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:28,flexWrap:"wrap",gap:12 }}>
            <div>
              <h2 style={{ color:"#e8f8f2",fontSize:20,fontWeight:700,margin:0,marginBottom:4 }}>Top Solvers</h2>
              <p style={{ color:"rgba(150,200,180,0.5)",fontSize:12,margin:0 }}>Fastest recorded solve times</p>
            </div>
            <div style={{ background:"rgba(0,229,160,0.06)",border:"1px solid rgba(0,229,160,0.2)",
              borderRadius:100,padding:"5px 14px",fontSize:11,color:"rgba(0,229,160,0.8)",letterSpacing:"0.06em" }}>
              ● LIVE · Updated 2m ago
            </div>
          </div>
          <div style={{ borderRadius:14,overflow:"hidden",border:"1px solid rgba(255,255,255,0.05)" }}>
            <div style={{ display:"grid",gridTemplateColumns:"60px 1fr 90px 110px",
              padding:"10px 20px",background:"rgba(0,0,0,0.3)",borderBottom:"1px solid rgba(255,255,255,0.05)" }}>
              {["RANK","PLAYER","GRID","TIME"].map(h=>(
                <div key={h} style={{ fontSize:10,letterSpacing:"0.12em",color:"rgba(150,200,180,0.4)",fontWeight:600 }}>{h}</div>
              ))}
            </div>
            {LEADERBOARD.map((row,i)=>(
              <div key={i} onMouseEnter={()=>setHoveredRow(i)} onMouseLeave={()=>setHoveredRow(null)} style={{
                display:"grid",gridTemplateColumns:"60px 1fr 90px 110px",padding:"14px 20px",
                background:hoveredRow===i?"rgba(0,229,160,0.04)":i===0?"rgba(0,229,160,0.02)":"transparent",
                borderBottom:i<LEADERBOARD.length-1?"1px solid rgba(255,255,255,0.04)":"none",
                transition:"background 0.15s",cursor:"default",alignItems:"center",
              }}>
                <div style={{ fontSize:13,fontWeight:700,color:i===0?"#00e5a0":i===1?"#00c9e5":i===2?"#a78bfa":"rgba(150,200,180,0.4)" }}>#{row.rank}</div>
                <div style={{ display:"flex",alignItems:"center",gap:10 }}>
                  <div style={{
                    width:28,height:28,borderRadius:"50%",
                    background:`rgba(${i===0?"0,229,160":i===1?"0,201,229":"167,139,250"},0.15)`,
                    border:`1px solid rgba(${i===0?"0,229,160":i===1?"0,201,229":"167,139,250"},0.3)`,
                    display:"flex",alignItems:"center",justifyContent:"center",
                    fontSize:9,fontWeight:700,color:i===0?"#00e5a0":i===1?"#00c9e5":"#a78bfa",
                  }}>{row.avatar}</div>
                  <span style={{ color:"#c8e8d8",fontSize:13,fontWeight:i===0?600:400 }}>{row.player}</span>
                  {i===0&&<span style={{ fontSize:9,background:"rgba(0,229,160,0.12)",border:"1px solid rgba(0,229,160,0.25)",color:"#00e5a0",padding:"2px 8px",borderRadius:100,letterSpacing:"0.08em" }}>BEST</span>}
                </div>
                <div style={{ color:"rgba(150,200,180,0.6)",fontSize:12,fontFamily:"monospace" }}>{row.grid}</div>
                <div style={{ fontSize:13,fontFamily:"monospace",color:i===0?"#00e5a0":"rgba(180,220,200,0.75)",fontWeight:i===0?700:400 }}>{row.time}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer style={{ padding:"20px 40px",borderTop:"1px solid rgba(0,229,160,0.08)",
          display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:12 }}>
          <div style={{ color:"rgba(120,180,155,0.5)",fontSize:12 }}>
            <span style={{ color:"#00e5a0",fontWeight:600 }}>GesturePuzzle</span> © 2024. All rights reserved.
          </div>
          <div style={{ display:"flex",gap:24,alignItems:"center" }}>
            {["GitHub","Privacy Policy","Credits"].map(l=>(
              <a key={l} href="#" onClick={e=>e.preventDefault()} style={{
                color:"rgba(120,180,155,0.5)",fontSize:12,textDecoration:"none",transition:"color 0.2s" }}
                onMouseEnter={e=>e.target.style.color="#00e5a0"}
                onMouseLeave={e=>e.target.style.color="rgba(120,180,155,0.5)"}
              >{l}</a>
            ))}
          </div>
        </footer>
      </div>
    </div>
  );
}
