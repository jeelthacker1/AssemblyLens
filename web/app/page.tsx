"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import {
  ScanLine,
  Video,
  GitBranch,
  Boxes,
  ClipboardCheck,
  ChartNoAxesCombined,
  BrainCircuit,
  Settings,
  Camera,
  Play,
  Square,
  RefreshCw,
  Plus,
  Check,
  ShieldCheck,
  AlertTriangle,
  Download,
  ChevronUp,
  ChevronDown,
  Trash2,
  Radio,
  LogOut,
  Layers,
  Activity,
  Upload,
  Eye,
} from "lucide-react";

type Obj = Record<string, any>;
type Entry = { id: string; kind: string; body: Obj; created: string };
type Step = {
  id: string;
  part: string;
  instruction: string;
  zone: number[];
  angle: number | null;
  tolerance: number;
  min_confidence: number;
};
type Part = {
  id: string;
  name: string;
  hsv_low: number[];
  hsv_high: number[];
  min_area: number;
};
type Workflow = {
  name: string;
  variant: string;
  parts: Part[];
  steps: Step[];
  stable_frames: number;
};
type Inspection = {
  id: string;
  serial: string;
  station: string;
  workflow: Workflow;
  state: Obj;
  version: number;
  last_sequence: number;
  created: string;
  observation?: Obj;
};
type Api = (path: string, init?: RequestInit) => Promise<any>;
const pages = [
  ["Operator station", Video],
  ["Workflows & BOM", GitBranch],
  ["Stations & cameras", Boxes],
  ["Inspections", ClipboardCheck],
  ["Quality analytics", ChartNoAxesCombined],
  ["Models & datasets", BrainCircuit],
  ["Integrations", Settings],
] as const;
const statusName = (v: string) => v?.replaceAll("_", " ") || "Unknown";
function Badge({ value }: { value: string }) {
  return (
    <span
      className={
        "badge " +
        (["approved", "step_completed", "active"].includes(value)
          ? "green"
          : ["needs_review", "incorrect_order", "rejected"].includes(value)
            ? "orange"
            : ["in_progress", "awaiting_approval", "shadow"].includes(value)
              ? "blue"
              : "")
      }
    >
      {statusName(value)}
    </span>
  );
}
function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Layers size={30} />
      <strong>{title}</strong>
      <p className="sub">{children}</p>
    </div>
  );
}

export default function App() {
  const [apiUrl, setApiUrl] = useState(
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010",
  );
  const [key, setKey] = useState("");
  const [user, setUser] = useState<Obj | null>(null);
  const [page, setPage] = useState("Operator station");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [records, setRecords] = useState<Record<string, Entry[]>>({
    workflow: [],
    station: [],
    factory: [],
    camera: [],
    model: [],
    dataset: [],
  });
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [stats, setStats] = useState<Obj>({
    statuses: {},
    failures: {},
    total: 0,
    window: 0,
  });
  const [selected, setSelected] = useState<Inspection | null>(null);
  const api: Api = useCallback(
    async (path, init = {}) => {
      const headers = new Headers(init.headers);
      headers.set("Authorization", "Bearer " + key);
      if (init.body && !(init.body instanceof FormData))
        headers.set("Content-Type", "application/json");
      const response = await fetch(apiUrl.replace(/\/$/, "") + path, {
        ...init,
        headers,
      });
      if (!response.ok) {
        let detail;
        try {
          detail = (await response.json()).detail;
        } catch {
          detail = response.statusText;
        }
        throw Error(
          typeof detail === "string" ? detail : JSON.stringify(detail),
        );
      }
      if (response.headers.get("content-type")?.includes("application/json"))
        return response.json();
      return response.blob();
    },
    [apiUrl, key],
  );
  const refresh = useCallback(async () => {
    const kinds = [
      "workflow",
      "station",
      "factory",
      "camera",
      "model",
      "dataset",
    ];
    const data = await Promise.all(kinds.map((k) => api("/records/" + k)));
    setRecords(Object.fromEntries(kinds.map((k, i) => [k, data[i]])));
    const [items, summary] = await Promise.all([
      api("/inspections"),
      api("/analytics"),
    ]);
    setInspections(items);
    setStats(summary);
  }, [api]);
  async function run(task: () => Promise<void>) {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      await task();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function login() {
    await run(async () => {
      const me = await api("/me");
      await refresh();
      setUser(me);
    });
  }
  async function initialize() {
    await run(async () => {
      await api("/bootstrap", { method: "POST" });
      await refresh();
      setMessage("Training fixture and pilot station are ready.");
    });
  }
  async function download() {
    await run(async () => {
      const blob = await api("/export.csv");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "assemblylens-inspections.csv";
      a.click();
      URL.revokeObjectURL(url);
    });
  }
  if (!user)
    return (
      <div className="login">
        <section className="login-intro">
          <div className="brand">
            <div className="brand-mark">
              <ScanLine />
            </div>
            AssemblyLens
          </div>
          <div className="eyebrow" style={{ color: "#8ab7ff" }}>
            VISUAL ASSEMBLY INTELLIGENCE
          </div>
          <h1>
            Every part.
            <br />
            Every step.
            <br />A clearer picture.
          </h1>
          <p>
            Connect the production floor to visual instructions, real-time
            verification, and traceable human decisions.
          </p>
          <div className="row">
            <ShieldCheck color="#75b6ff" />
            <span>Built for the operator. Designed for evidence.</span>
          </div>
        </section>
        <section className="login-panel">
          <form
            className="login-form"
            onSubmit={(e) => {
              e.preventDefault();
              login();
            }}
          >
            <div>
              <h2>Connect your workspace</h2>
              <p className="sub">Sign in to your AssemblyLens API.</p>
            </div>
            {error && <div className="notice error">{error}</div>}
            <label>
              API address
              <input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                required
                type="url"
              />
            </label>
            <label>
              Access key
              <input
                value={key}
                onChange={(e) => setKey(e.target.value)}
                type="password"
                autoComplete="off"
                placeholder="Your administrator-issued key"
                required
              />
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Connecting…" : "Open workspace"}
            </button>
            <p className="sub">
              For the local demo, start the API with <code>DEMO_MODE=1</code>{" "}
              and use <code>demo-admin</code>. Access keys stay in this tab’s
              memory.
            </p>
            <p className="tiny muted">
              Visual assistance supports human verification. It does not certify
              product quality or replace safety inspections.
            </p>
          </form>
        </section>
      </div>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ScanLine size={24} />
          </div>
          <span>AssemblyLens</span>
        </div>
        <div>
          <div className="nav-label">PRODUCTION WORKSPACE</div>
          <nav>
            {pages.map(([name, Icon]) => (
              <button
                key={name}
                title={name}
                className={page === name ? "active" : ""}
                onClick={() => {
                  setPage(name);
                  setError("");
                  setMessage("");
                }}
              >
                <Icon size={19} />
                <span>{name}</span>
              </button>
            ))}
          </nav>
        </div>
        <div className="sidebar-bottom">
          <strong>{user.tenant}</strong>
          <span>Assembly assistance platform</span>
          <p className="tiny" style={{ marginTop: 12 }}>
            Human verification required
          </p>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>
            Workspace{" "}
            <span style={{ margin: "0 9px", color: "#c5d0da" }}>/</span>
            <strong>{page}</strong>
          </span>
          <div className="topbar-right">
            <span className="connection">
              <span className="dot online" /> API connected
            </span>
            <span className="avatar">
              {user.user.slice(0, 2).toUpperCase()}
            </span>
            <button
              className="small"
              title="Sign out"
              onClick={() => {
                setUser(null);
                setKey("");
                setSelected(null);
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">
                ASSEMBLYLENS / {user.tenant.toUpperCase()}
              </div>
              <h1>{page}</h1>
              <p className="sub">
                {page === "Operator station"
                  ? "A live view of your assembly. Clear guidance at every step."
                  : page === "Workflows & BOM"
                    ? "Define the product, place inspection zones, and build the sequence."
                    : page === "Stations & cameras"
                      ? "Connect your facilities, stations, and edge cameras."
                      : page === "Inspections"
                        ? "Follow every serial number from first observation to human review."
                        : page === "Quality analytics"
                          ? "Understand inspection outcomes and recurring failure patterns."
                          : page === "Models & datasets"
                            ? "Keep training data, validation, and deployment decisions traceable."
                            : "Connect AssemblyLens to your manufacturing systems."}
              </p>
            </div>
            <div className="row">
              {!records.workflow.length && (
                <button
                  className="primary"
                  onClick={initialize}
                  disabled={busy}
                >
                  <Plus size={16} />
                  Set up training kit
                </button>
              )}
              <button
                onClick={() => run(refresh)}
                disabled={busy}
                title="Refresh workspace"
              >
                <RefreshCw size={16} />
                Refresh
              </button>
            </div>
          </div>
          {error && (
            <div className="notice error" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button className="small" onClick={() => setError("")}>
                Dismiss
              </button>
            </div>
          )}
          {message && (
            <div className="notice success" style={{ marginBottom: 18 }}>
              {message}
            </div>
          )}
          {page === "Operator station" && (
            <Operator
              api={api}
              records={records}
              selected={selected}
              setSelected={setSelected}
              run={run}
              refresh={refresh}
            />
          )}
          {page === "Workflows & BOM" && (
            <WorkflowEditor
              entries={records.workflow}
              api={api}
              run={run}
              refresh={refresh}
            />
          )}
          {page === "Stations & cameras" && (
            <Stations records={records} api={api} run={run} refresh={refresh} />
          )}
          {page === "Inspections" && (
            <InspectionList
              inspections={inspections}
              selected={selected}
              setSelected={setSelected}
              api={api}
              run={run}
              refresh={refresh}
              download={download}
            />
          )}
          {page === "Quality analytics" && (
            <Analytics stats={stats} download={download} />
          )}
          {page === "Models & datasets" && (
            <Models records={records} api={api} run={run} refresh={refresh} />
          )}
          {page === "Integrations" && (
            <div className="grid2">
              <div className="card">
                <div className="card-head">
                  <h2>Manufacturing execution API</h2>
                  <Badge value="active" />
                </div>
                <div className="card-body stack">
                  <p>
                    Use scoped bearer keys for each tenant, reviewer, and edge
                    gateway. The serial number joins inspection results to your
                    MES.
                  </p>
                  <a href={apiUrl + "/docs"} target="_blank" rel="noreferrer">
                    Open interactive API documentation
                  </a>
                  <pre>{`POST /inspections\nPOST /inspections/{id}/frame?sequence=0\nPOST /inspections/{id}/observations\nGET  /inspections/{id}\nPOST /inspections/{id}/decision\nGET  /events?inspection_id={id}\nGET  /export.csv`}</pre>
                  <div className="notice">
                    <ShieldCheck size={20} />
                    No machinery-control endpoints. Integration results are
                    advisory until human verification.
                  </div>
                </div>
              </div>
              <div className="card">
                <div className="card-head">
                  <h2>Your session</h2>
                </div>
                <div className="card-body stack">
                  <label>
                    Tenant
                    <input value={user.tenant} readOnly />
                  </label>
                  <label>
                    Role
                    <input value={user.role} readOnly />
                  </label>
                  <label>
                    API
                    <input value={apiUrl} readOnly />
                  </label>
                  <p className="sub">
                    Production keys are configured through API_KEYS_JSON. Demo
                    authentication must be disabled before production
                    deployment. See repository operations documentation for
                    PostgreSQL, object storage, Kafka, and retention setup.
                  </p>
                </div>
              </div>
            </div>
          )}
          <p className="footer-note">
            AssemblyLens · Visual predictions are assistance, not a guarantee of
            product quality. Required safety inspections remain mandatory.
          </p>
        </div>
      </main>
    </div>
  );
}

function Operator({
  api,
  records,
  selected,
  setSelected,
  run,
  refresh,
}: {
  api: Api;
  records: Record<string, Entry[]>;
  selected: Inspection | null;
  setSelected: (v: Inspection | null) => void;
  run: (f: () => Promise<void>) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [station, setStation] = useState("");
  const [workflow, setWorkflow] = useState("");
  const [serial, setSerial] = useState("");
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [transport, setTransport] = useState("jpeg");
  const peer = useRef<RTCPeerConnection | null>(null);
  const [device, setDevice] = useState("");
  const [live, setLive] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const mounted = useRef(true);
  const [cameraError, setCameraError] = useState("");
  const [observation, setObservation] = useState<Obj | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const running = useRef(false);
  const current = useRef(selected);
  const inflight = useRef(false);
  current.current = selected;
  useEffect(() => {
    if (!station && records.station[0]) setStation(records.station[0].id);
    if (!workflow && records.workflow[0]) setWorkflow(records.workflow[0].id);
  }, [records, station, workflow]);
  const stop = useCallback(() => {
    running.current = false;
    peer.current?.close();
    peer.current = null;
    if (timer.current) clearTimeout(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setLive(false);
  }, []);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      running.current = false;
      peer.current?.close();
      peer.current = null;
      if (timer.current) clearTimeout(timer.current);
      stream.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);
  const wf =
    selected?.workflow ||
    (records.workflow.find((w) => w.id === workflow)?.body as
      Workflow | undefined);
  async function sample() {
    if (!running.current) return;
    const inspect = current.current;
    if (
      inspect &&
      video.current &&
      video.current.readyState >= 2 &&
      !inflight.current &&
      !["approved", "rejected"].includes(inspect.state.status)
    ) {
      inflight.current = true;
      try {
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(
          Math.min(
            960,
            (1080 * video.current.videoWidth) / video.current.videoHeight,
          ),
        );
        canvas.height = Math.round(
          (canvas.width * video.current.videoHeight) / video.current.videoWidth,
        );
        canvas
          .getContext("2d")!
          .drawImage(video.current, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise<Blob | null>((resolve) =>
          canvas.toBlob(resolve, "image/jpeg", 0.8),
        );
        if (!blob) throw Error("Could not capture camera frame");
        const form = new FormData();
        form.append("file", blob, "frame.jpg");
        const result = await api(
          `/inspections/${inspect.id}/frame?sequence=${inspect.last_sequence + 1}`,
          { method: "POST", body: form },
        );
        if (running.current) {
          current.current = result;
          setSelected(result);
          setObservation(result.observation);
          setCameraError("");
        }
      } catch (e) {
        setCameraError(
          e instanceof Error ? e.message : "Frame processing failed",
        );
        stop();
      } finally {
        inflight.current = false;
      }
    }
    if (running.current) timer.current = setTimeout(sample, 500);
  }
  async function connect() {
    if (
      connecting ||
      !selected ||
      ["approved", "rejected"].includes(selected.state.status)
    )
      return;
    setConnecting(true);
    setCameraError("");
    let expired = false;
    let permissionTimer: ReturnType<typeof setTimeout> | undefined;
    try {
      if (!navigator.mediaDevices)
        throw Error("Camera access requires localhost or HTTPS.");
      const request = navigator.mediaDevices
        .getUserMedia({
          video: device
            ? { deviceId: { exact: device } }
            : { width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        })
        .then((media) => {
          if (expired || !mounted.current) {
            media.getTracks().forEach((track) => track.stop());
            throw Error("Camera request was cancelled.");
          }
          return media;
        });
      const media = await Promise.race([
        request,
        new Promise<MediaStream>((_, reject) => {
          permissionTimer = setTimeout(() => {
            expired = true;
            reject(
              Error(
                "Camera connection timed out. Check browser camera permission and whether a camera is connected.",
              ),
            );
          }, 15000);
        }),
      ]);
      clearTimeout(permissionTimer);
      stream.current = media;
      if (video.current) {
        video.current.srcObject = media;
        await video.current.play();
      }
      setDevices(
        (await navigator.mediaDevices.enumerateDevices()).filter(
          (d) => d.kind === "videoinput",
        ),
      );
      setLive(true);
      running.current = true;
      if (transport === "webrtc") {
        const pc = new RTCPeerConnection({ iceServers: [] });
        peer.current = pc;
        media.getTracks().forEach((track) => pc.addTrack(track, media));
        const channel = pc.createDataChannel("inspection");
        channel.onmessage = (e) => {
          const result = JSON.parse(e.data);
          if (result.error) {
            setCameraError(result.error);
            stop();
            return;
          }
          if (running.current) {
            current.current = result;
            setSelected(result);
            setObservation(result.observation);
          }
        };
        pc.onconnectionstatechange = () => {
          if (["failed", "disconnected"].includes(pc.connectionState)) {
            setCameraError("WebRTC connection lost");
            stop();
          }
        };
        await pc.setLocalDescription(await pc.createOffer());
        await new Promise<void>((resolve) => {
          if (pc.iceGatheringState === "complete") resolve();
          else {
            const timeout = setTimeout(resolve, 5000);
            pc.onicegatheringstatechange = () => {
              if (pc.iceGatheringState === "complete") {
                clearTimeout(timeout);
                resolve();
              }
            };
          }
        });
        const answer = await api("/webrtc/offer", {
          method: "POST",
          body: JSON.stringify({
            inspection_id: current.current!.id,
            sdp: pc.localDescription!.sdp,
            type: "offer",
          }),
        });
        await pc.setRemoteDescription(answer);
      } else sample();
    } catch (e) {
      setCameraError(
        e instanceof Error ? e.message : "Camera permission denied",
      );
      stop();
    } finally {
      if (permissionTimer) clearTimeout(permissionTimer);
      if (mounted.current) setConnecting(false);
    }
  }
  async function start() {
    await run(async () => {
      if (!serial.trim()) throw Error("Enter a product serial number");
      const result = await api("/inspections", {
        method: "POST",
        body: JSON.stringify({
          serial: serial.trim(),
          station_id: station,
          workflow_id: workflow,
        }),
      });
      current.current = result;
      setSelected(result);
      setObservation(null);
      await refresh();
    });
  }
  const cursor = selected?.state.cursor || 0;
  const steps = wf?.steps || [];
  return (
    <>
      <div className="toolbar">
        <label>
          Production station
          <select
            value={station}
            onChange={(e) => setStation(e.target.value)}
            disabled={live}
          >
            {records.station.map((s) => (
              <option key={s.id} value={s.id}>
                {s.body.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Product / variant
          <select
            value={workflow}
            onChange={(e) => setWorkflow(e.target.value)}
            disabled={live}
          >
            {records.workflow.map((s) => (
              <option key={s.id} value={s.id}>
                {s.body.name} · {s.body.variant}
              </option>
            ))}
          </select>
        </label>
        <label>
          Product serial
          <input
            placeholder="e.g. KIT-0001"
            value={serial}
            onChange={(e) => setSerial(e.target.value)}
            disabled={live}
          />
        </label>
        <button
          className="primary"
          onClick={start}
          disabled={!station || !workflow || live}
        >
          <Plus size={16} />
          Start inspection
        </button>
      </div>
      <div className="row" style={{ marginBottom: 16 }}>
        <label>
          Camera transport
          <select
            value={transport}
            onChange={(e) => setTransport(e.target.value)}
            disabled={live}
          >
            <option value="jpeg">Sampled JPEG - default</option>
            <option value="webrtc">
              WebRTC - optional server module, same LAN
            </option>
          </select>
        </label>
      </div>
      <div className="operator-grid">
        <div className="stack">
          <div className="card">
            <div className="card-head">
              <div className="row">
                <Camera size={18} />
                <h2>Live inspection</h2>
                <Badge value={selected?.state.status || "not_started"} />
              </div>
              <span className="tiny muted">
                {selected?.serial || "No active serial"}
              </span>
            </div>
            <div
              className="video"
              style={
                video.current?.videoWidth
                  ? {
                      aspectRatio: `${video.current.videoWidth}/${video.current.videoHeight}`,
                    }
                  : {}
              }
            >
              <video ref={video} muted playsInline autoPlay />
              {!live && (
                <div className="video-placeholder">
                  <div
                    style={{
                      padding: 16,
                      border: "1px solid #34495e",
                      borderRadius: 14,
                    }}
                  >
                    <Video size={34} />
                  </div>
                  <strong>Your production floor, in focus</strong>
                  <p>
                    Start an inspection, then connect a real webcam. Frames are
                    analyzed as they arrive.
                  </p>
                  <button
                    className="primary"
                    onClick={connect}
                    disabled={
                      !selected ||
                      connecting ||
                      ["approved", "rejected"].includes(selected.state.status)
                    }
                  >
                    <Camera size={16} />
                    {connecting ? "Connecting camera..." : "Connect camera"}
                  </button>
                </div>
              )}
              {live && (
                <>
                  <span className="camera-tag">
                    LIVE CAMERA · {observation?.model || "Waiting for analysis"}
                  </span>
                  <svg
                    className="overlay"
                    viewBox="0 0 1000 1000"
                    preserveAspectRatio="none"
                  >
                    {steps.map((s, i) => (
                      <g key={s.id}>
                        <rect
                          x={s.zone[0] * 1000}
                          y={s.zone[1] * 1000}
                          width={s.zone[2] * 1000}
                          height={s.zone[3] * 1000}
                          fill="none"
                          stroke={
                            i < cursor
                              ? "#48d1a2"
                              : i === cursor
                                ? "#74a8ff"
                                : "#7c8d9d"
                          }
                          strokeWidth="3"
                          strokeDasharray="10 8"
                        />
                        <text
                          x={s.zone[0] * 1000 + 8}
                          y={s.zone[1] * 1000 + 26}
                          fill="white"
                          fontSize="21"
                        >
                          {i + 1}. {s.part}
                        </text>
                      </g>
                    ))}
                    {observation?.detections?.map((d: Obj, i: number) => (
                      <rect
                        key={i}
                        x={d.bbox[0] * 1000}
                        y={d.bbox[1] * 1000}
                        width={d.bbox[2] * 1000}
                        height={d.bbox[3] * 1000}
                        fill="#36d69b14"
                        stroke="#5fe3b7"
                        strokeWidth="3"
                      />
                    ))}
                  </svg>
                </>
              )}
            </div>
            <div className="video-footer">
              <span className="connection">
                <span className={"dot " + (live ? "online" : "")} />
                {live ? "Camera connected" : "Camera offline"}
              </span>
              <span>
                {observation
                  ? `${observation.latency_ms?.toFixed(1)} ms vision · ${observation.detections?.length || 0} detections`
                  : "No inference data yet"}
              </span>
              {live ? (
                <button className="small" onClick={stop}>
                  <Square size={13} />
                  Stop
                </button>
              ) : (
                <button
                  className="small"
                  onClick={connect}
                  disabled={
                    !selected ||
                    connecting ||
                    ["approved", "rejected"].includes(selected.state.status)
                  }
                >
                  <Play size={13} />
                  Connect
                </button>
              )}
            </div>
          </div>
          {cameraError && (
            <div className="notice error" role="alert">
              {cameraError}
            </div>
          )}
          <div className="card">
            <div className="card-head">
              <h2>Observation details</h2>
              <span className="tiny muted">Live results, never simulated</span>
            </div>
            {observation ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Component</th>
                      <th>Mask score</th>
                      <th>Orientation</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {observation.detections.map((d: Obj, i: number) => (
                      <tr key={i}>
                        <td>{d.part}</td>
                        <td>{(d.confidence * 100).toFixed(1)}%</td>
                        <td>
                          {d.angle == null
                            ? "Not estimated"
                            : d.angle.toFixed(1) + "°"}
                        </td>
                        <td>{observation.model}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="tiny muted" style={{ padding: 16 }}>
                  Color-kit scores describe mask geometry; they are not
                  calibrated probabilities. QR:{" "}
                  {observation.codes?.join(", ") || "none"}
                </p>
              </div>
            ) : (
              <Empty title="Waiting for the first frame">
                Detected parts and orientation will appear here.
              </Empty>
            )}
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <div className="card-head">
              <h2>Assembly sequence</h2>
              <span className="badge blue">
                {cursor} / {steps.length}
              </span>
            </div>
            <div style={{ padding: "18px 20px" }}>
              <div className="progress">
                <span
                  style={{
                    width: `${steps.length ? (cursor / steps.length) * 100 : 0}%`,
                  }}
                />
              </div>
              <p className="sub">{wf?.variant || "Choose a workflow"}</p>
            </div>
            {steps.map((s, i) => (
              <div
                className={
                  "step " +
                  (i < cursor ? "done" : i === cursor ? "current" : "")
                }
                key={s.id}
              >
                <span className="step-number">
                  {i < cursor ? <Check size={15} /> : i + 1}
                </span>
                <div>
                  <strong>
                    {wf?.parts.find((p) => p.id === s.part)?.name || s.part}
                  </strong>
                  <p>{s.instruction}</p>
                  {i === cursor && (
                    <span
                      className="badge blue"
                      style={{ display: "inline-block", marginTop: 8 }}
                    >
                      Current step
                    </span>
                  )}
                </div>
              </div>
            ))}
            {!steps.length && (
              <Empty title="No workflow configured">
                Use Set up training kit to begin.
              </Empty>
            )}
          </div>
          <div className="notice warning">
            <ShieldCheck size={22} />
            <div>
              <strong>Human verification</strong>
              <p className="tiny" style={{ marginTop: 4 }}>
                Completion creates a review request. Only authorized reviewers
                can approve an inspection.
              </p>
            </div>
          </div>
          {selected?.state.faults?.length > 0 && (
            <div className="card">
              <div className="card-head">
                <h2>Attention required</h2>
                <AlertTriangle size={18} color="#ad6a0d" />
              </div>
              <div className="card-body stack">
                {selected!.state.faults.map((f: Obj, i: number) => (
                  <div key={i}>
                    <Badge value={f.kind} />
                    <p className="sub">Component: {f.part}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {selected && (
            <button
              disabled={
                live || ["approved", "rejected"].includes(selected.state.status)
              }
              onClick={() =>
                run(async () => {
                  setSelected(
                    await api(`/inspections/${selected!.id}/finish`, {
                      method: "POST",
                    }),
                  );
                  await refresh();
                })
              }
            >
              <ClipboardCheck size={17} />
              Finish and request review
            </button>
          )}
          {devices.length > 0 && (
            <label>
              Camera device
              <select
                value={device}
                onChange={(e) => setDevice(e.target.value)}
                disabled={live}
              >
                <option value="">Default camera</option>
                {devices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || "Camera"}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>
    </>
  );
}

function WorkflowEditor({
  entries,
  api,
  run,
  refresh,
}: {
  entries: Entry[];
  api: Api;
  run: (f: () => Promise<void>) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [id, setId] = useState("");
  const [draft, setDraft] = useState<Workflow | null>(null);
  const [active, setActive] = useState(0);
  const board = useRef<HTMLDivElement>(null);
  const drag = useRef<Obj | null>(null);
  useEffect(() => {
    if (!draft && entries[0]) {
      setId(entries[0].id);
      setDraft(structuredClone(entries[0].body) as Workflow);
    }
  }, [entries, draft]);
  function change(next: Workflow) {
    setDraft(next);
  }
  function updateStep(index: number, patch: Partial<Step>) {
    if (draft)
      change({
        ...draft,
        steps: draft.steps.map((s, i) =>
          i === index ? { ...s, ...patch } : s,
        ),
      });
  }
  function move(index: number, delta: number) {
    if (!draft) return;
    const steps = [...draft.steps];
    [steps[index], steps[index + delta]] = [steps[index + delta], steps[index]];
    change({ ...draft, steps });
    setActive(index + delta);
  }
  function pointer(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag.current || !draft || !board.current) return;
    const rect = board.current.getBoundingClientRect();
    const dx = (e.clientX - drag.current.x) / rect.width,
      dy = (e.clientY - drag.current.y) / rect.height;
    const [x, y, w, h] = drag.current.zone;
    const zone = drag.current.resize
      ? [
          x,
          y,
          Math.max(0.03, Math.min(1 - x, w + dx)),
          Math.max(0.03, Math.min(1 - y, h + dy)),
        ]
      : [
          Math.max(0, Math.min(1 - w, x + dx)),
          Math.max(0, Math.min(1 - h, y + dy)),
          w,
          h,
        ];
    updateStep(drag.current.index, {
      zone: zone.map((v) => Math.round(v * 1000) / 1000),
    });
  }
  function add() {
    if (!draft) return;
    const part = "part_" + (draft.parts.length + 1);
    change({
      ...draft,
      parts: [
        ...draft.parts,
        {
          id: part,
          name: "New component",
          hsv_low: [0, 100, 70],
          hsv_high: [10, 255, 255],
          min_area: 0.003,
        },
      ],
      steps: [
        ...draft.steps,
        {
          id: crypto.randomUUID(),
          part,
          instruction: "Install the component in the inspection zone.",
          zone: [0.1, 0.2, 0.2, 0.5],
          angle: null,
          tolerance: 20,
          min_confidence: 0.75,
        },
      ],
    });
    setActive(draft.steps.length);
  }
  return (
    <div className="stack">
      <div className="row">
        <select
          style={{ maxWidth: 400 }}
          value={id}
          onChange={(e) => {
            setId(e.target.value);
            setDraft(
              structuredClone(
                entries.find((x) => x.id === e.target.value)!.body,
              ) as Workflow,
            );
            setActive(0);
          }}
        >
          {entries.map((w) => (
            <option value={w.id} key={w.id}>
              {w.body.name} · {w.body.variant}
            </option>
          ))}
        </select>
        <button
          onClick={() => {
            setId("");
            setDraft({
              name: "New assembly",
              variant: "Standard",
              parts: [
                {
                  id: "part_1",
                  name: "Component 1",
                  hsv_low: [0, 100, 70],
                  hsv_high: [10, 255, 255],
                  min_area: 0.003,
                },
              ],
              steps: [
                {
                  id: "step_1",
                  part: "part_1",
                  instruction: "Place the component.",
                  zone: [0.1, 0.1, 0.8, 0.8],
                  angle: null,
                  tolerance: 20,
                  min_confidence: 0.75,
                },
              ],
              stable_frames: 3,
            });
          }}
        >
          <Plus size={16} />
          New workflow
        </button>
        {draft && (
          <button
            className="primary"
            onClick={() =>
              run(async () => {
                const saved = await api(
                  "/records/workflow" + (id ? "/" + id : ""),
                  {
                    method: id ? "PUT" : "POST",
                    body: JSON.stringify({ body: draft }),
                  },
                );
                setId(saved.id);
                await refresh();
              })
            }
          >
            <Check size={16} />
            Save workflow
          </button>
        )}
      </div>
      {draft ? (
        <div className="grid2">
          <div className="card">
            <div className="card-head">
              <h2>Product and sequence</h2>
              <button className="small" onClick={add}>
                <Plus size={15} />
                Add part
              </button>
            </div>
            <div className="card-body">
              <div className="form-grid">
                <label>
                  Product name
                  <input
                    value={draft.name}
                    onChange={(e) => change({ ...draft, name: e.target.value })}
                  />
                </label>
                <label>
                  Variant
                  <input
                    value={draft.variant}
                    onChange={(e) =>
                      change({ ...draft, variant: e.target.value })
                    }
                  />
                </label>
                <label>
                  Stable frames required
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={draft.stable_frames}
                    onChange={(e) =>
                      change({
                        ...draft,
                        stable_frames: Number(e.target.value),
                      })
                    }
                  />
                </label>
              </div>
              <div className="section-gap">
                {draft.steps.map((s, i) => (
                  <div
                    className="editor-step"
                    key={s.id}
                    style={i === active ? { borderColor: "#6598ed" } : {}}
                    onClick={() => setActive(i)}
                  >
                    <div
                      className="row"
                      style={{
                        justifyContent: "space-between",
                        marginBottom: 12,
                      }}
                    >
                      <strong>
                        Step {i + 1} · {s.part}
                      </strong>
                      <div className="row">
                        <button
                          className="small"
                          title="Move step up"
                          disabled={!i}
                          onClick={(e) => {
                            e.stopPropagation();
                            move(i, -1);
                          }}
                        >
                          <ChevronUp size={14} />
                        </button>
                        <button
                          className="small"
                          title="Move step down"
                          disabled={i === draft.steps.length - 1}
                          onClick={(e) => {
                            e.stopPropagation();
                            move(i, 1);
                          }}
                        >
                          <ChevronDown size={14} />
                        </button>
                        <button
                          className="small danger"
                          title="Delete step"
                          disabled={draft.steps.length === 1}
                          onClick={(e) => {
                            e.stopPropagation();
                            change({
                              ...draft,
                              steps: draft.steps.filter((_, j) => j !== i),
                              parts: draft.parts.filter((p) => p.id !== s.part),
                            });
                            setActive(0);
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <label>
                      Visual instruction
                      <textarea
                        rows={2}
                        value={s.instruction}
                        onChange={(e) =>
                          updateStep(i, { instruction: e.target.value })
                        }
                      />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="stack">
            <div className="card">
              <div className="card-head">
                <h2>Inspection zones</h2>
                <span className="badge blue">Drag to position</span>
              </div>
              <div className="card-body">
                <div
                  ref={board}
                  className="zones-editor"
                  onPointerMove={pointer}
                  onPointerUp={() => {
                    drag.current = null;
                  }}
                  onPointerCancel={() => {
                    drag.current = null;
                  }}
                >
                  {draft.steps.map((s, i) => (
                    <div
                      key={s.id}
                      className={"zone " + (i === active ? "selected" : "")}
                      style={{
                        left: s.zone[0] * 100 + "%",
                        top: s.zone[1] * 100 + "%",
                        width: s.zone[2] * 100 + "%",
                        height: s.zone[3] * 100 + "%",
                      }}
                      onPointerDown={(e) => {
                        e.currentTarget.setPointerCapture(e.pointerId);
                        setActive(i);
                        drag.current = {
                          index: i,
                          x: e.clientX,
                          y: e.clientY,
                          zone: s.zone,
                          resize: (e.target as HTMLElement).classList.contains(
                            "zone-handle",
                          ),
                        };
                      }}
                    >
                      {i + 1} · {s.part}
                      <div className="zone-handle" />
                    </div>
                  ))}
                </div>
                <p className="sub">
                  Drag a zone to move it; drag its lower-right corner to resize.
                  Coordinates are relative to the entire camera frame.
                </p>
              </div>
            </div>
            {draft.steps[active] && (
              <div className="card">
                <div className="card-head">
                  <h2>Component configuration</h2>
                </div>
                <div className="card-body stack">
                  {(() => {
                    const s = draft.steps[active];
                    const p = draft.parts.find((p) => p.id === s.part)!;
                    function patchPart(patch: Partial<Part>) {
                      change({
                        ...draft!,
                        parts: draft!.parts.map((v) =>
                          v.id === p.id ? { ...v, ...patch } : v,
                        ),
                      });
                    }
                    return (
                      <>
                        <label>
                          Component name
                          <input
                            value={p.name}
                            onChange={(e) =>
                              patchPart({ name: e.target.value })
                            }
                          />
                        </label>
                        <div className="form-grid">
                          <label>
                            HSV lower bound
                            <input
                              key={p.id + "-low"}
                              defaultValue={p.hsv_low.join(",")}
                              onBlur={(e) =>
                                patchPart({
                                  hsv_low: e.target.value
                                    .split(",")
                                    .map(Number),
                                })
                              }
                            />
                          </label>
                          <label>
                            HSV upper bound
                            <input
                              key={p.id + "-high"}
                              defaultValue={p.hsv_high.join(",")}
                              onBlur={(e) =>
                                patchPart({
                                  hsv_high: e.target.value
                                    .split(",")
                                    .map(Number),
                                })
                              }
                            />
                          </label>
                          <label>
                            Orientation ° (blank = any)
                            <input
                              type="number"
                              value={s.angle ?? ""}
                              onChange={(e) =>
                                updateStep(active, {
                                  angle:
                                    e.target.value === ""
                                      ? null
                                      : Number(e.target.value),
                                })
                              }
                            />
                          </label>
                          <label>
                            Angle tolerance °
                            <input
                              type="number"
                              value={s.tolerance}
                              onChange={(e) =>
                                updateStep(active, {
                                  tolerance: Number(e.target.value),
                                })
                              }
                            />
                          </label>
                          <label>
                            Minimum score
                            <input
                              type="number"
                              min="0"
                              max="1"
                              step=".05"
                              value={s.min_confidence}
                              onChange={(e) =>
                                updateStep(active, {
                                  min_confidence: Number(e.target.value),
                                })
                              }
                            />
                          </label>
                          <label>
                            Minimum frame area
                            <input
                              type="number"
                              min=".0001"
                              max=".9"
                              step=".001"
                              value={p.min_area}
                              onChange={(e) =>
                                patchPart({ min_area: Number(e.target.value) })
                              }
                            />
                          </label>
                        </div>
                      </>
                    );
                  })()}
                  <div className="notice warning">
                    HSV settings recognize the colored training kit. Visually
                    similar factory parts need a trained and validated model.
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <Empty title="Create your first workflow">
          Or initialize the three-part training kit.
        </Empty>
      )}
    </div>
  );
}

function Stations({
  records,
  api,
  run,
  refresh,
}: {
  records: Record<string, Entry[]>;
  api: Api;
  run: (f: () => Promise<void>) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [kind, setKind] = useState("camera");
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const [driver, setDriver] = useState("opencv");
  const [source, setSource] = useState("0");
  const parents = kind === "station" ? records.factory : records.station;
  return (
    <div className="grid2">
      <div className="stack">
        {records.station.map((station) => (
          <div className="card" key={station.id}>
            <div className="card-head">
              <div className="row">
                <Boxes size={19} />
                <h2>{station.body.name}</h2>
              </div>
              <span className="badge">
                {
                  records.camera.filter((c) => c.body.station_id === station.id)
                    .length
                }{" "}
                cameras
              </span>
            </div>
            <div className="card-body">
              <p className="sub">
                {
                  records.factory.find((f) => f.id === station.body.factory_id)
                    ?.body.name
                }{" "}
                · <span className="mono">{station.id}</span>
              </p>
              {records.camera
                .filter((c) => c.body.station_id === station.id)
                .map((c) => (
                  <div
                    key={c.id}
                    className="editor-step"
                    style={{ marginTop: 15 }}
                  >
                    <div
                      className="row"
                      style={{ justifyContent: "space-between" }}
                    >
                      <div className="row">
                        <Camera size={18} />
                        <strong>{c.body.name}</strong>
                      </div>
                      <Badge
                        value={
                          c.body.health?.connected &&
                          Date.now() - Date.parse(c.body.health.at) < 15000
                            ? "active"
                            : "offline"
                        }
                      />
                    </div>
                    <p className="sub">
                      {c.body.driver} · source {c.body.source}
                    </p>
                    <p className="mono muted">{c.id}</p>
                    {c.body.health && (
                      <p className="tiny muted">
                        {c.body.health.fps} target FPS · {c.body.health.dropped}{" "}
                        replaced frames · last heartbeat{" "}
                        {new Date(c.body.health.at).toLocaleString()}
                      </p>
                    )}
                  </div>
                ))}
            </div>
          </div>
        ))}
        {!records.station.length && (
          <div className="card">
            <Empty title="No stations yet">
              Create a factory, then its production stations.
            </Empty>
          </div>
        )}
      </div>
      <div className="stack">
        <div className="card">
          <div className="card-head">
            <h2>Register equipment</h2>
          </div>
          <form
            className="card-body stack"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await api("/records/" + kind, {
                  method: "POST",
                  body: JSON.stringify({
                    body: {
                      name,
                      ...(kind === "station"
                        ? { factory_id: parent || parents[0]?.id }
                        : kind === "camera"
                          ? {
                              station_id: parent || parents[0]?.id,
                              driver,
                              source,
                            }
                          : {}),
                    },
                  }),
                });
                setName("");
                await refresh();
              });
            }}
          >
            <label>
              Record type
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setParent("");
                }}
              >
                <option value="camera">Camera</option>
                <option value="station">Production station</option>
                <option value="factory">Factory</option>
              </select>
            </label>
            <label>
              Name
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Overhead camera"
              />
            </label>
            {kind !== "factory" && (
              <label>
                {kind === "station" ? "Factory" : "Station"}
                <select
                  required
                  value={parent || parents[0]?.id || ""}
                  onChange={(e) => setParent(e.target.value)}
                >
                  {parents.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.body.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {kind === "camera" && (
              <>
                <label>
                  Capture driver
                  <select
                    value={driver}
                    onChange={(e) => setDriver(e.target.value)}
                  >
                    <option value="opencv">OpenCV · USB / RTSP</option>
                    <option value="browser">Browser webcam</option>
                    <option value="pylon">Basler pylon · industrial</option>
                  </select>
                </label>
                <label>
                  Source / serial
                  <input
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    placeholder="0 or rtsp://camera/stream"
                  />
                </label>
                <p className="sub">
                  Credentials belong in CAMERA_SOURCE on the edge gateway. Do
                  not put passwords in this form.
                </p>
              </>
            )}
            <button className="primary">
              <Plus size={16} />
              Register {kind}
            </button>
          </form>
        </div>
        <div className="notice">
          <Radio size={23} />
          <div>
            <strong>Run capture at the edge</strong>
            <p className="sub">
              Discover connected cameras with{" "}
              <code>python -m edge.agent --discover</code>. The edge agent
              handles reconnection and sends heartbeat updates.
            </p>
          </div>
        </div>
        <div className="notice warning">
          One observation source per active inspection. Multiple station cameras
          may monitor separate inspections; automatic cross-camera fusion is not
          implemented.
        </div>
      </div>
    </div>
  );
}

function Evidence({ id, api }: { id: string; api: Api }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let objectUrl = "";
    api("/evidence/" + id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (active) setUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, api]);
  return url ? (
    <img className="evidence" src={url} alt="Captured inspection evidence" />
  ) : (
    <p className="sub">{error || "Loading evidence…"}</p>
  );
}

function InspectionList({
  inspections,
  selected,
  setSelected,
  api,
  run,
  refresh,
  download,
}: {
  inspections: Inspection[];
  selected: Inspection | null;
  setSelected: (v: Inspection | null) => void;
  api: Api;
  run: (f: () => Promise<void>) => Promise<void>;
  refresh: () => Promise<void>;
  download: () => Promise<void>;
}) {
  const [events, setEvents] = useState<Obj[]>([]);
  const [reason, setReason] = useState("");
  const [filter, setFilter] = useState("");
  async function open(id: string) {
    await run(async () => {
      setSelected(await api("/inspections/" + id));
      setEvents(await api("/events?inspection_id=" + id));
    });
  }
  async function decide(action: string) {
    if (!selected) return;
    await run(async () => {
      const result = await api(`/inspections/${selected.id}/decision`, {
        method: "POST",
        body: JSON.stringify({
          action,
          reason,
          expected_version: selected.version,
        }),
      });
      setSelected(result);
      setEvents(await api("/events?inspection_id=" + selected.id));
      await refresh();
      setReason("");
    });
  }
  return (
    <div className="stack">
      <div className="row">
        <input
          style={{ maxWidth: 340 }}
          placeholder="Find a product serial…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button onClick={download}>
          <Download size={16} />
          Export CSV
        </button>
      </div>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product serial</th>
              <th>Workflow</th>
              <th>Progress</th>
              <th>Status</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {inspections
              .filter((i) =>
                i.serial.toLowerCase().includes(filter.toLowerCase()),
              )
              .map((i) => (
                <tr key={i.id}>
                  <td>
                    <strong>{i.serial}</strong>
                  </td>
                  <td>{i.workflow.name}</td>
                  <td>
                    {i.state.cursor}/{i.workflow.steps.length}
                  </td>
                  <td>
                    <Badge value={i.state.status} />
                  </td>
                  <td>{new Date(i.created).toLocaleString()}</td>
                  <td>
                    <button className="small" onClick={() => open(i.id)}>
                      <Eye size={14} />
                      Review
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        {!inspections.length && (
          <Empty title="No inspections recorded">
            Start a real camera inspection from the operator station.
          </Empty>
        )}
      </div>
      {selected && (
        <div className="grid2">
          <div className="card">
            <div className="card-head">
              <h2>Review · {selected.serial}</h2>
              <Badge value={selected.state.status} />
            </div>
            <div className="card-body stack">
              <div className="row">
                <span className="badge">Version {selected.version}</span>
                <span className="badge">
                  {selected.state.frames} processed frames
                </span>
              </div>
              {selected.state.faults?.map((f: Obj, i: number) => (
                <div className="notice warning" key={i}>
                  {statusName(f.kind)} · {f.part}
                </div>
              ))}
              <label>
                Decision reason
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Record what you inspected and why you reached this decision (at least 5 characters)."
                />
              </label>
              <div className="row">
                <button
                  className="primary"
                  disabled={reason.trim().length < 5}
                  onClick={() => decide("approve")}
                >
                  <Check size={16} />
                  Approve
                </button>
                <button
                  className="danger"
                  disabled={reason.trim().length < 5}
                  onClick={() => decide("reject")}
                >
                  Reject
                </button>
                <button
                  disabled={reason.trim().length < 5}
                  onClick={() => decide("rework")}
                >
                  Start rework
                </button>
                <button
                  disabled={reason.trim().length < 5}
                  onClick={() => decide("override")}
                >
                  Admin override
                </button>
              </div>
              <p className="sub">
                Approval requires a verified sequence without unresolved faults.
                Overrides require administrator permission and are permanently
                recorded in the audit history.
              </p>
              <button onClick={() => open(selected.id)}>
                <RefreshCw size={15} />
                Reload inspection and evidence
              </button>
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h2>Evidence & audit trail</h2>
              <span className="badge">{events.length} events</span>
            </div>
            <div className="card-body stack">
              {events.map((e) => (
                <div className="editor-step" key={e.id}>
                  <div
                    className="row"
                    style={{ justifyContent: "space-between" }}
                  >
                    <strong>{statusName(e.action)}</strong>
                    <span className="tiny muted">
                      {new Date(e.created).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="sub">
                    {e.actor}
                    {e.body.reason ? " · " + e.body.reason : ""}
                  </p>
                  {e.body.evidence_id && (
                    <div style={{ marginTop: 12 }}>
                      <Evidence id={e.body.evidence_id} api={api} />
                    </div>
                  )}
                  <details>
                    <summary className="sub">Event provenance</summary>
                    <pre>{JSON.stringify(e.body, null, 2)}</pre>
                  </details>
                </div>
              ))}
              {!events.length && (
                <p className="sub">
                  Select Review or Reload to retrieve this inspection’s audit
                  history.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Analytics({
  stats,
  download,
}: {
  stats: Obj;
  download: () => Promise<void>;
}) {
  const metrics = [
    ["All inspections", stats.total, ClipboardCheck],
    ["Approved in window", stats.statuses.approved || 0, ShieldCheck],
    ["Needs review", stats.statuses.needs_review || 0, AlertTriangle],
    ["Awaiting approval", stats.statuses.awaiting_approval || 0, Activity],
  ] as const;
  return (
    <>
      <div className="metrics">
        {metrics.map(([name, value, Icon]) => (
          <div className="metric" key={name}>
            <Icon className="icon" size={20} />
            <span className="label">{name}</span>
            <div className="value">{value}</div>
            <span className="tiny muted">
              {name === "All inspections"
                ? "Tenant-wide total"
                : "Latest " + stats.window + " inspections"}
            </span>
          </div>
        ))}
      </div>
      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h2>Failure patterns</h2>
            <span className="badge">Observed faults</span>
          </div>
          <div className="card-body stack">
            {Object.entries(stats.failures).map(([name, count]) => (
              <div key={name}>
                <div
                  className="row"
                  style={{ justifyContent: "space-between", marginBottom: 8 }}
                >
                  <span>{statusName(name)}</span>
                  <strong>{String(count)}</strong>
                </div>
                <div className="bar">
                  <span
                    style={{
                      width: `${(Number(count) / Math.max(1, stats.window)) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
            {!Object.keys(stats.failures).length && (
              <Empty title="No faults recorded in this window">
                Failure trends populate from real inspections.
              </Empty>
            )}
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <h2>Validation is a separate measurement</h2>
          </div>
          <div className="card-body stack">
            <p>
              Operational approval rates do not measure model precision or false
              acceptance. Those require photographed examples with independently
              reviewed ground truth.
            </p>
            <div className="notice warning">
              No production accuracy claim is available. Run the labeled
              evaluation tool on representative factory samples before
              deployment.
            </div>
            <button onClick={download}>
              <Download size={16} />
              Download inspection report
            </button>
            <p className="sub">{stats.scope}</p>
          </div>
        </div>
      </div>
    </>
  );
}

function Models({
  records,
  api,
  run,
  refresh,
}: {
  records: Record<string, Entry[]>;
  api: Api;
  run: (f: () => Promise<void>) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [tab, setTab] = useState("datasets");
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [labels, setLabels] = useState('["base","bracket","cap"]');
  const [queue, setQueue] = useState<Obj[]>([]);
  const [modelId, setModelId] = useState("");
  const [stage, setStage] = useState("shadow");
  const [reason, setReason] = useState("");
  const [validation, setValidation] = useState("{}");
  return (
    <div className="stack">
      <div className="tabs">
        {["datasets", "models", "active learning"].map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {statusName(t)}
          </button>
        ))}
      </div>
      {tab === "active learning" ? (
        <>
          <div>
            <button
              onClick={() =>
                run(async () => setQueue(await api("/learning/queue")))
              }
            >
              <RefreshCw size={15} />
              Load uncertain samples
            </button>
          </div>
          <div className="grid2">
            {queue.map((q) => (
              <div className="card" key={q.id}>
                <div className="card-head">
                  <h2>{statusName(q.body.reason)}</h2>
                  <span className="badge orange">
                    Priority {q.body.priority.toFixed(2)}
                  </span>
                </div>
                <div className="card-body">
                  {q.body.evidence_id ? (
                    <Evidence id={q.body.evidence_id} api={api} />
                  ) : (
                    <p>No photograph retained for this event.</p>
                  )}
                  <p className="sub mono">Inspection {q.body.inspection}</p>
                </div>
              </div>
            ))}
          </div>
          {!queue.length && (
            <div className="card">
              <Empty title="Review uncertain observations">
                Load the queue to prioritize samples for annotation.
              </Empty>
            </div>
          )}
        </>
      ) : (
        <div className="grid2">
          <div className="card">
            <div className="card-head">
              <h2>
                {tab === "datasets" ? "Dataset versions" : "Model registry"}
              </h2>
              <span className="badge">
                {records[tab === "datasets" ? "dataset" : "model"].length}
              </span>
            </div>
            <div className="card-body stack">
              {records[tab === "datasets" ? "dataset" : "model"].map((r) => (
                <div className="editor-step" key={r.id}>
                  <div
                    className="row"
                    style={{ justifyContent: "space-between" }}
                  >
                    <strong>{r.body.name}</strong>
                    {r.body.stage && <Badge value={r.body.stage} />}
                  </div>
                  <p className="sub">
                    {r.body.images
                      ? r.body.images.length + " annotated images"
                      : r.body.labels?.join(", ")}
                  </p>
                  <p className="mono muted">SHA256 {r.body.sha256}</p>
                  <p className="mono muted">ID {r.id}</p>
                  {r.body.validation && (
                    <details>
                      <summary className="sub">Validation report</summary>
                      <pre>{JSON.stringify(r.body.validation, null, 2)}</pre>
                    </details>
                  )}
                </div>
              ))}
              {!records[tab === "datasets" ? "dataset" : "model"].length && (
                <Empty
                  title={
                    tab === "datasets"
                      ? "No dataset versions yet"
                      : "No trained models registered"
                  }
                >
                  {tab === "datasets"
                    ? "Import CVAT image annotations to start a versioned dataset."
                    : "The live training kit uses real OpenCV segmentation. Register a validated ONNX detector for other parts."}
                </Empty>
              )}
            </div>
          </div>
          <div className="stack">
            <div className="card">
              <div className="card-head">
                <h2>
                  {tab === "datasets"
                    ? "Import annotations"
                    : "Register an ONNX model"}
                </h2>
              </div>
              <form
                className="card-body stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  run(async () => {
                    if (!file) throw Error("Select a file");
                    const form = new FormData();
                    form.append("file", file);
                    await api(
                      tab === "datasets"
                        ? "/datasets/import-cvat?name=" +
                            encodeURIComponent(name)
                        : "/models/upload?name=" +
                            encodeURIComponent(name) +
                            "&labels=" +
                            encodeURIComponent(labels),
                      { method: "POST", body: form },
                    );
                    await refresh();
                    setName("");
                  });
                }}
              >
                <label>
                  Name
                  <input
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                {tab === "models" && (
                  <label>
                    Class labels (JSON array)
                    <input
                      value={labels}
                      onChange={(e) => setLabels(e.target.value)}
                    />
                  </label>
                )}
                <label>
                  {tab === "datasets" ? "CVAT image XML" : "ONNX file"}
                  <input
                    key={tab}
                    type="file"
                    accept={tab === "datasets" ? ".xml" : ".onnx"}
                    required
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
                <button className="primary">
                  <Upload size={16} />
                  Upload and validate
                </button>
                <p className="sub">
                  {tab === "datasets"
                    ? "Imports boxes and polygons. Image files stay in your dataset storage. Training scripts resolve images by CVAT filename."
                    : "Contract: RGB NCHW 0–1 input, [1,N,6] decoded boxes with NMS. Arbitrary detector exports need a compatible adapter."}
                </p>
              </form>
            </div>
            {tab === "models" && (
              <div className="card">
                <div className="card-head">
                  <h2>Deployment decision</h2>
                </div>
                <form
                  className="card-body stack"
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(async () => {
                      await api(
                        "/models/" +
                          (modelId || records.model[0]?.id) +
                          "/deployment",
                        {
                          method: "POST",
                          body: JSON.stringify({
                            stage,
                            reason,
                            validation: JSON.parse(validation),
                          }),
                        },
                      );
                      await refresh();
                    });
                  }}
                >
                  <label>
                    Model
                    <select
                      value={modelId || records.model[0]?.id || ""}
                      onChange={(e) => setModelId(e.target.value)}
                    >
                      {records.model.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.body.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Stage
                    <select
                      value={stage}
                      onChange={(e) => setStage(e.target.value)}
                    >
                      <option>shadow</option>
                      <option>active</option>
                      <option>retired</option>
                    </select>
                  </label>
                  <label>
                    Reason
                    <input
                      required
                      minLength={5}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </label>
                  <label>
                    Validation report (JSON)
                    <textarea
                      rows={5}
                      value={validation}
                      onChange={(e) => setValidation(e.target.value)}
                    />
                  </label>
                  <button disabled={!records.model.length}>
                    Record deployment decision
                  </button>
                  <p className="sub">
                    Activation requires precision, recall, false
                    acceptance/rejection rates, and dataset_sha256. Configure
                    station model IDs through the API after recording the
                    deployment decision.
                  </p>
                </form>
              </div>
            )}
            <div className="notice">
              <BrainCircuit size={22} />
              <span>
                PyTorch training, MLflow logging, ONNX inference, and
                quantization evaluation tools are included in the repository.
                Training is run explicitly on your dataset and compute
                environment.
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
