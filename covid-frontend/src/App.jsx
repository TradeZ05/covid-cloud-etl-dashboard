import { useState, useEffect, useRef, useMemo } from "react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  RadialBarChart, RadialBar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import {
  Globe2, MapPinned, Activity, Stethoscope, X, Send, Loader2, ShieldAlert,
  AlertTriangle, RadioTower,
} from "lucide-react";
import vietnamProvinceGeo from "./data/vietnam-provinces.json";

// ============================================================
// Đổi địa chỉ này nếu backend chạy ở host/port khác.
// LƯU Ý: nếu bạn đang xem artifact này TRONG claude.ai, trình duyệt có
// thể chặn gọi ra localhost vì lý do sandbox — nếu vậy, copy code này
// chạy trong dự án React thật trên máy bạn (npm create vite) thì sẽ
// gọi được bình thường, vì lúc đó không còn chạy trong sandbox nữa.
// ============================================================
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const INK = "#1A2E33";
const PAPER = "#F6F5F1";
const CARD = "#FFFFFF";
const LINE = "#D9D7CC";
const TEAL = "#0E6E6A";
const CORAL = "#B5533C";
const AMBER = "#B8873B";
const MUTED = "#6B6A62";
const PIE_COLORS = [TEAL, "#C7C5B8"];

const mono = "'IBM Plex Mono', monospace";
const serif = "'Source Serif 4', serif";
const sans = "'Inter', sans-serif";

function formatNumber(n) {
  if (n == null || Number.isNaN(n)) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString("vi-VN");
}

function formatDateTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatDateOnly(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("vi-VN", {
      day: "2-digit", month: "2-digit", year: "numeric",
    });
  } catch {
    return value;
  }
}

async function fetchJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} trả về lỗi HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
function StatCard({ label, value, accent, sub }) {
  return (
    <div style={{ background: CARD, border: `1px solid ${LINE}`, padding: "16px 18px" }}>
      <p style={{ fontFamily: mono, fontSize: 10.5, letterSpacing: "0.08em", textTransform: "uppercase", color: MUTED, margin: 0 }}>
        {label}
      </p>
      <p style={{ fontFamily: mono, fontSize: 26, fontWeight: 600, color: accent || INK, margin: "6px 0 0", letterSpacing: "-0.01em" }}>
        {value}
      </p>
      {sub && <p style={{ fontFamily: sans, fontSize: 11, color: MUTED, margin: "4px 0 0" }}>{sub}</p>}
    </div>
  );
}

function SectionTitle({ children, note }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 16, flexWrap: "wrap", gap: 6 }}>
      <h2 style={{ fontFamily: serif, fontSize: 17, fontWeight: 600, margin: 0 }}>{children}</h2>
      {note && <span style={{ fontFamily: mono, fontSize: 10.5, color: MUTED }}>{note}</span>}
    </div>
  );
}

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: INK, color: PAPER, padding: "8px 12px", fontFamily: mono, fontSize: 12 }}>
      <div style={{ opacity: 0.6, marginBottom: 2 }}>{label}</div>
      <div>{Number(payload[0].value).toLocaleString("vi-VN")}{unit || ""}</div>
    </div>
  );
}

function RankedBarList({ data, nameKey, valueKey, highlightName }) {
  if (!data?.length) {
    return <p style={{ color: MUTED, fontSize: 13, margin: 0 }}>Chưa có dữ liệu để hiển thị.</p>;
  }
  const max = Math.max(...data.map((d) => d[valueKey] || 0), 1);
  return (
    <div>
      {data.map((c, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "28px 1fr 90px", alignItems: "center", gap: 12, padding: "9px 0", borderBottom: `1px solid ${LINE}` }}>
          <span style={{ fontFamily: mono, fontSize: 11, color: MUTED }}>{String(i + 1).padStart(2, "0")}</span>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 500, marginBottom: 4 }}>{c[nameKey]}</div>
            <div style={{ height: 4, background: PAPER }}>
              <div style={{ height: "100%", width: `${((c[valueKey] || 0) / max) * 100}%`, background: c[nameKey] === highlightName ? CORAL : TEAL }} />
            </div>
          </div>
          <span style={{ fontFamily: mono, fontSize: 13, textAlign: "right" }}>{formatNumber(c[valueKey])}</span>
        </div>
      ))}
    </div>
  );
}

function ErrorBox({ message }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", background: "#FCEBEB", border: "1px solid #E3B8AF", padding: 14, fontSize: 12.5, color: "#791F1F" }}>
      <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
      <div>
        <strong>Không gọi được API.</strong> Kiểm tra: (1) backend FastAPI có đang chạy ở {API_BASE} không, (2) nếu đang xem artifact này trong claude.ai, thử copy code chạy ở dự án React riêng trên máy bạn.
        <div style={{ marginTop: 4, fontFamily: mono, opacity: 0.8 }}>{message}</div>
      </div>
    </div>
  );
}

const STATUS_COLORS = {
  success: { bg: "#EAF3DE", fg: "#27500A" },
  failed: { bg: "#FCEBEB", fg: "#791F1F" },
  running: { bg: "#FAEEDA", fg: "#633806" },
};

const VN_COORDS = {
  "ha noi": [105.85, 21.03], "ho chi minh city": [106.63, 10.82], "hai phong": [106.68, 20.86],
  "da nang": [108.22, 16.07], "can tho": [105.78, 10.05], "an giang": [105.17, 10.52],
  "ba ria-vung tau": [107.24, 10.54], "bac giang": [106.20, 21.28], "bac kan": [105.84, 22.15],
  "bac lieu": [105.72, 9.29], "bac ninh": [106.08, 21.19], "ben tre": [106.38, 10.24],
  "binh dinh": [109.22, 13.77], "binh duong": [106.67, 11.17], "binh phuoc": [106.89, 11.75],
  "binh thuan": [108.10, 10.93], "ca mau": [105.15, 9.18], "cao bang": [106.26, 22.67],
  "dak lak": [108.04, 12.67], "dak nong": [107.69, 12.00], "dien bien": [103.02, 21.39],
  "dong nai": [107.17, 10.95], "dong thap": [105.64, 10.46], "gia lai": [108.00, 13.98],
  "ha giang": [104.98, 22.83], "ha nam": [105.92, 20.54], "ha tinh": [105.90, 18.34],
  "hai duong": [106.32, 20.94], "hau giang": [105.64, 9.78], "hoa binh": [105.34, 20.82],
  "hung yen": [106.05, 20.65], "khanh hoa": [109.20, 12.26], "kien giang": [105.13, 10.02],
  "kon tum": [108.00, 14.35], "lai chau": [103.46, 22.40], "lam dong": [108.44, 11.94],
  "lang son": [106.76, 21.85], "lao cai": [104.00, 22.48], "long an": [106.17, 10.54],
  "nam dinh": [106.17, 20.42], "nghe an": [104.92, 19.23], "ninh binh": [105.97, 20.25],
  "ninh thuan": [108.99, 11.57], "phu tho": [105.22, 21.32], "phu yen": [109.09, 13.09],
  "quang binh": [106.60, 17.47], "quang nam": [108.33, 15.57], "quang ngai": [108.80, 15.12],
  "quang ninh": [107.29, 21.01], "quang tri": [107.19, 16.75], "soc trang": [105.97, 9.60],
  "son la": [103.91, 21.33], "tay ninh": [106.13, 11.31], "thai binh": [106.34, 20.45],
  "thai nguyen": [105.84, 21.59], "thanh hoa": [105.78, 19.81], "thua thien-hue": [107.59, 16.46],
  "tien giang": [106.35, 10.45], "tra vinh": [106.34, 9.93], "tuyen quang": [105.22, 21.82],
  "vinh long": [105.97, 10.25], "vinh phuc": [105.60, 21.31], "yen bai": [104.87, 21.72],
};

function normalizePlaceName(name) {
  return String(name || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .replace(/\s+province$/i, "")
    .replace(/\s+city$/i, "")
    .trim()
    .toLowerCase();
}

function VietnamHeatMap({ data }) {
  const points = (data || [])
    .map((p) => ({ ...p, coords: VN_COORDS[normalizePlaceName(p.province_name)] }))
    .filter((p) => p.coords);
  const coverageValues = points.map((p) => Number(p.doses_per_100) || 0).filter(Boolean);
  const minCoverage = Math.min(...coverageValues, 0);
  const maxCoverage = Math.max(...coverageValues, 1);
  const topLabels = new Set([...points]
    .sort((a, b) => (b.doses_per_100 || 0) - (a.doses_per_100 || 0))
    .slice(0, 8)
    .map((p) => p.province_name));
  const topDoses = [...points]
    .sort((a, b) => (b.doses_administered || 0) - (a.doses_administered || 0))
    .slice(0, 4)
    .map((p) => p.province_name);

  const project = ([lon, lat]) => {
    const x = 46 + ((lon - 102.1) / (109.6 - 102.1)) * 246;
    const y = 36 + ((23.4 - lat) / (23.4 - 8.4)) * 522;
    return [x, y];
  };

  const colorFor = (value) => {
    const ratio = ((Number(value) || 0) - minCoverage) / Math.max(maxCoverage - minCoverage, 1);
    if (ratio >= 0.82) return TEAL;
    if (ratio >= 0.64) return "#4B9B84";
    if (ratio >= 0.46) return AMBER;
    if (ratio >= 0.28) return "#D58A45";
    return CORAL;
  };

  const heatCells = points.map((p) => {
    const [x, y] = project(p.coords);
    return { ...p, x, y, color: colorFor(p.doses_per_100) };
  });

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1fr) 190px", gap: 18, alignItems: "center" }}>
      <svg viewBox="0 0 430 640" role="img" aria-label="Ban do nhiet tiem chung Viet Nam" style={{ width: "100%", height: 360 }}>
        <rect x="0" y="0" width="430" height="640" fill="#E9F1F0" />
        {Array.from({ length: 9 }).map((_, i) => (
          <line key={`v-${i}`} x1={36 + i * 44} y1="22" x2={36 + i * 44} y2="612" stroke="#D4E0DD" strokeDasharray="3 7" />
        ))}
        {Array.from({ length: 12 }).map((_, i) => (
          <line key={`h-${i}`} x1="24" y1={34 + i * 50} x2="404" y2={34 + i * 50} stroke="#D4E0DD" strokeDasharray="3 7" />
        ))}
        <path d="M128 40 L154 54 L170 86 L155 117 L171 150 L208 174 L226 213 L205 246 L220 280 L254 319 L245 350 L268 386 L296 424 L289 462 L320 506 L301 548 L256 584 L213 602 L170 586 L139 550 L157 506 L142 464 L108 430 L121 392 L102 350 L125 309 L100 270 L121 232 L107 194 L129 160 L104 121 L98 78 Z" fill="#F7F4EC" stroke="#AAB7B3" strokeWidth="2.5" />
        <path d="M139 53 C169 92 146 127 173 160 C202 196 231 213 204 250 C181 282 226 299 250 338 C268 366 253 391 283 429 C316 472 293 535 228 580" fill="none" stroke="#CDD4CF" strokeWidth="2" strokeDasharray="4 5" />
        {heatCells.map((p) => (
            <g key={p.province_name}>
              <rect x={p.x - 7} y={p.y - 7} width="14" height="14" rx="3" transform={`rotate(45 ${p.x} ${p.y})`} fill={p.color} fillOpacity="0.9" stroke={CARD} strokeWidth="1.4">
                <title>{`${p.province_name}: ${formatNumber(p.doses_administered)} liều, ${p.doses_per_100 ?? "—"} liều/100 dân`}</title>
              </rect>
              {topLabels.has(p.province_name) && (
                <text x={p.x + 10} y={p.y + 3} fontSize="9" fill={INK} fontFamily="Inter" fontWeight={600}>{p.province_name}</text>
              )}
            </g>
        ))}
        <g opacity="0.95">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <ellipse key={`hs-${i}`} cx={326 + (i % 3) * 15} cy={244 + Math.floor(i / 3) * 14} rx="4.8" ry="2.8" fill={CARD} stroke="#7D8E8A" strokeWidth="1.2" />
          ))}
          <text x="302" y="226" fontFamily="IBM Plex Mono" fontSize="12" fill={MUTED} fontWeight={600}>QĐ HOÀNG SA</text>
        </g>
        <g opacity="0.95">
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
            <ellipse key={`ts-${i}`} cx={295 + (i % 4) * 18} cy={468 + Math.floor(i / 4) * 17} rx="4.5" ry="2.6" fill={CARD} stroke="#7D8E8A" strokeWidth="1.2" />
          ))}
          <text x="272" y="448" fontFamily="IBM Plex Mono" fontSize="12" fill={MUTED} fontWeight={600}>QĐ TRƯỜNG SA</text>
        </g>
        <g>
          <rect x="24" y="574" width="186" height="44" fill={CARD} fillOpacity="0.88" stroke={LINE} />
          <text x="36" y="594" fontFamily="IBM Plex Mono" fontSize="10" fill={MUTED}>Heatmap: liều/100 dân</text>
          {[CORAL, "#D58A45", AMBER, "#4B9B84", TEAL].map((c, i) => (
            <rect key={c} x={36 + i * 22} y="603" width="20" height="8" fill={c} />
          ))}
          <text x="36" y="624" fontFamily="IBM Plex Mono" fontSize="9" fill={MUTED}>thấp</text>
          <text x="122" y="624" fontFamily="IBM Plex Mono" fontSize="9" fill={MUTED}>cao</text>
        </g>
      </svg>
      <div>
        <p style={{ fontFamily: mono, fontSize: 10.5, color: MUTED, textTransform: "uppercase", margin: "0 0 8px" }}>Vietnam heatmap</p>
        <p style={{ fontSize: 12.5, color: MUTED, lineHeight: 1.5, margin: 0 }}>
          Mỗi ô màu đại diện cho một tỉnh/thành theo vị trí địa lý tương đối. Màu càng xanh nghĩa là tỷ lệ liều/100 dân càng cao.
        </p>
        <div style={{ display: "grid", gap: 7, marginTop: 14, fontFamily: mono, fontSize: 11, color: MUTED }}>
          <span><span style={{ display: "inline-block", width: 10, height: 10, background: TEAL, marginRight: 6 }} /> Cao nhất</span>
          <span><span style={{ display: "inline-block", width: 10, height: 10, background: AMBER, marginRight: 6 }} /> Trung bình</span>
          <span><span style={{ display: "inline-block", width: 10, height: 10, background: CORAL, marginRight: 6 }} /> Thấp hơn</span>
        </div>
        <p style={{ fontFamily: mono, fontSize: 10.5, color: MUTED, marginTop: 16, lineHeight: 1.5 }}>
          Top liều đã tiêm: {topDoses.join(" · ") || "—"}
        </p>
      </div>
    </div>
  );
}

function provinceKey(name) {
  const raw = String(name || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[đĐ]/g, "d")
    .replace(/\s+province$/i, "")
    .replace(/\s+city$/i, "")
    .replace(/[^a-zA-Z0-9]/g, "")
    .toLowerCase();
  return ({
    hochiminhcity: "hochiminh",
    hochiminh: "hochiminh",
    thuathienhue: "thuathienhue",
  })[raw] || raw;
}

function projectVietnam([lon, lat]) {
  return [
    70 + (lon - 101.8) * 31,
    24 + (23.7 - lat) * 35.5,
  ];
}

function polygonPath(ring) {
  return ring
    .map((coord, i) => {
      const [x, y] = projectVietnam(coord);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ") + " Z";
}

function geometryPath(geometry) {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  return polygons
    .flatMap((polygon) => polygon.map((ring) => polygonPath(ring)))
    .join(" ");
}

function geometryCenter(geometry) {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  let bestRing = polygons[0]?.[0] || [];
  for (const polygon of polygons) {
    const ring = polygon[0] || [];
    if (ring.length > bestRing.length) bestRing = ring;
  }
  const sums = bestRing.reduce((acc, [lon, lat]) => {
    acc.lon += lon;
    acc.lat += lat;
    return acc;
  }, { lon: 0, lat: 0 });
  return projectVietnam([
    sums.lon / Math.max(bestRing.length, 1),
    sums.lat / Math.max(bestRing.length, 1),
  ]);
}

function VietnamGeoHeatMap({ data }) {
  const provinceRows = useMemo(() => {
    return new Map((data || []).map((row) => [provinceKey(row.province_name), row]));
  }, [data]);

  const features = useMemo(() => {
    return vietnamProvinceGeo.features.map((feature) => ({
      key: provinceKey(feature.properties.NAME_1),
      name: feature.properties.NAME_1,
      path: geometryPath(feature.geometry),
      center: geometryCenter(feature.geometry),
    }));
  }, []);

  const values = (data || []).map((row) => Number(row.doses_per_100) || 0).filter(Boolean);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const topKeys = new Set([...(data || [])]
    .sort((a, b) => (b.doses_per_100 || 0) - (a.doses_per_100 || 0))
    .slice(0, 8)
    .map((row) => provinceKey(row.province_name)));

  const colorFor = (value) => {
    const ratio = ((Number(value) || 0) - min) / Math.max(max - min, 1);
    if (ratio >= 0.82) return TEAL;
    if (ratio >= 0.64) return "#4B9B84";
    if (ratio >= 0.46) return AMBER;
    if (ratio >= 0.28) return "#D58A45";
    return CORAL;
  };

  const islandGroups = [
    { label: "QĐ HOÀNG SA", labelPos: [392, 292], points: [[111.6, 16.4], [111.9, 16.7], [112.2, 16.3], [112.5, 16.8], [112.0, 17.1], [111.4, 16.9]] },
    { label: "QĐ TRƯỜNG SA", labelPos: [386, 482], points: [[112.3, 11.4], [113.1, 10.8], [114.0, 10.2], [114.8, 9.7], [115.6, 8.9], [113.5, 9.2], [112.8, 8.8], [115.1, 11.0], [114.2, 8.4]] },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 18, alignItems: "center" }}>
      <svg viewBox="0 0 560 640" role="img" aria-label="Bản đồ nhiệt tiêm chủng Việt Nam theo tỉnh thành" style={{ width: "100%", height: 460 }}>
        <rect x="0" y="0" width="560" height="640" fill="#E7F1F2" />
        {Array.from({ length: 12 }).map((_, i) => (
          <line key={`gv-${i}`} x1={36 + i * 44} y1="18" x2={36 + i * 44} y2="616" stroke="#CFE0E0" strokeDasharray="3 7" />
        ))}
        {Array.from({ length: 13 }).map((_, i) => (
          <line key={`gh-${i}`} x1="24" y1={32 + i * 46} x2="536" y2={32 + i * 46} stroke="#CFE0E0" strokeDasharray="3 7" />
        ))}

        <g filter="drop-shadow(3px 4px 2px rgba(26, 46, 51, 0.22))">
          {features.map((feature) => {
            const row = provinceRows.get(feature.key);
            const fill = row ? colorFor(row.doses_per_100) : "#D7D7D2";
            return (
              <path
                key={feature.key}
                d={feature.path}
                fill={fill}
                stroke={CARD}
                strokeWidth="1.15"
                strokeLinejoin="round"
              >
                <title>{`${row?.province_name || feature.name}: ${row?.doses_per_100 ?? "-"} liều/100 dân, ${formatNumber(row?.doses_administered)} liều đã tiêm`}</title>
              </path>
            );
          })}
        </g>

        {features.map((feature) => {
          const row = provinceRows.get(feature.key);
          if (!row || !topKeys.has(feature.key)) return null;
          const [x, y] = feature.center;
          return (
            <g key={`label-${feature.key}`}>
              <circle cx={x} cy={y} r="2.6" fill={CARD} stroke={INK} strokeWidth="0.7" />
              <text x={x + 5} y={y + 3} fontFamily="Inter" fontSize="9" fontWeight="700" fill={INK}>{row.province_name}</text>
            </g>
          );
        })}

        {islandGroups.map((group) => (
          <g key={group.label}>
            {group.points.map((coord, i) => {
              const [x, y] = projectVietnam(coord);
              return <ellipse key={i} cx={x} cy={y} rx="5.2" ry="3" fill={CARD} stroke="#677C7B" strokeWidth="1.2" />;
            })}
            <text x={group.labelPos[0]} y={group.labelPos[1]} fontFamily="IBM Plex Mono" fontSize="13" fill={MUTED} fontWeight="700">{group.label}</text>
          </g>
        ))}

        <g>
          <rect x="28" y="572" width="210" height="46" fill={CARD} fillOpacity="0.9" stroke={LINE} />
          <text x="40" y="592" fontFamily="IBM Plex Mono" fontSize="10" fill={MUTED}>Heatmap: liều/100 dân</text>
          {[CORAL, "#D58A45", AMBER, "#4B9B84", TEAL].map((c, i) => (
            <rect key={c} x={40 + i * 24} y="602" width="22" height="8" fill={c} />
          ))}
          <text x="40" y="624" fontFamily="IBM Plex Mono" fontSize="9" fill={MUTED}>thấp</text>
          <text x="136" y="624" fontFamily="IBM Plex Mono" fontSize="9" fill={MUTED}>cao</text>
        </g>
      </svg>

      <div style={{ display: "none" }}>
        <p style={{ fontFamily: mono, fontSize: 10.5, color: MUTED, textTransform: "uppercase", margin: "0 0 8px" }}>GeoJSON heatmap</p>
        <p style={{ fontSize: 12.5, color: MUTED, lineHeight: 1.5, margin: 0 }}>
          Bản đồ dùng ranh giới tỉnh/thành từ GeoJSON GADM, tô màu theo tỷ lệ liều/100 dân. Di chuột lên từng tỉnh để xem số liệu.
        </p>
        <div style={{ display: "grid", gap: 7, marginTop: 14, fontFamily: mono, fontSize: 11, color: MUTED }}>
          <span><span style={{ display: "inline-block", width: 10, height: 10, background: TEAL, marginRight: 6 }} /> Cao nhất</span>
          <span><span style={{ display: "inline-block", width: 10, height: 10, background: AMBER, marginRight: 6 }} /> Trung bình</span>
          <span><span style={{ display: "inline-block", width: 10, height: 10, background: CORAL, marginRight: 6 }} /> Thấp hơn</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TRỢ LÝ AI Y TẾ
// ---------------------------------------------------------------------------
const SYSTEM_PROMPT = `Bạn là trợ lý AI hỗ trợ thông tin y tế tổng quát, được nhúng trong một dashboard theo dõi dịch bệnh COVID-19.
Quy tắc:
- Trả lời bằng tiếng Việt, ngắn gọn, dễ hiểu, đúng trọng tâm câu hỏi.
- Chỉ cung cấp thông tin tổng quát về COVID-19, bệnh truyền nhiễm, phòng ngừa, triệu chứng phổ biến. KHÔNG chẩn đoán bệnh cụ thể cho người dùng.
- Luôn nhắc rằng đây là thông tin tham khảo, không thay thế tư vấn/chẩn đoán từ bác sĩ.
- Nếu người dùng mô tả dấu hiệu cấp cứu, khuyên gọi cấp cứu 115 hoặc đến cơ sở y tế gần nhất ngay lập tức.
- Không kê đơn thuốc hay liều lượng cụ thể.`;

function AiHealthAssistant({ open, onClose }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Xin chào 👋 Mình là trợ lý thông tin y tế. Bạn muốn hỏi gì về COVID-19, triệu chứng, hay cách phòng ngừa?" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    const nextMessages = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/assistant/health`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await response.json();
      const reply = data.reply || "Xin lỗi, mình chưa có câu trả lời phù hợp.";
      setMessages((cur) => [...cur, { role: "assistant", content: reply }]);
    } catch (e) {
      setMessages((cur) => [...cur, { role: "assistant", content: "Có lỗi khi kết nối tới trợ lý. Bạn thử lại sau nhé." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      position: "fixed", top: 0, right: 0, height: "100vh", width: "min(380px, 100vw)",
      background: CARD, borderLeft: `1px solid ${LINE}`,
      boxShadow: open ? "-8px 0 24px rgba(0,0,0,0.08)" : "none",
      transform: open ? "translateX(0)" : "translateX(100%)",
      transition: "transform 220ms ease", display: "flex", flexDirection: "column",
      zIndex: 50, fontFamily: sans,
    }}>
      <div style={{ padding: "16px 18px", borderBottom: `1px solid ${LINE}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Stethoscope size={17} color={TEAL} />
          <span style={{ fontFamily: serif, fontSize: 15, fontWeight: 600 }}>Trợ lý y tế AI</span>
        </div>
        <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: MUTED }}>
          <X size={18} />
        </button>
      </div>
      <div style={{ padding: "10px 18px", background: "#FBF3E9", borderBottom: `1px solid ${LINE}`, display: "flex", gap: 8 }}>
        <ShieldAlert size={14} color={AMBER} style={{ flexShrink: 0, marginTop: 2 }} />
        <p style={{ fontSize: 11.5, color: "#6B4E1E", margin: 0, lineHeight: 1.4 }}>
          Thông tin tham khảo, không thay thế chẩn đoán của bác sĩ. Trường hợp khẩn cấp, gọi 115.
        </p>
      </div>
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "16px 18px", display: "flex", flexDirection: "column", gap: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-end" : "flex-start", maxWidth: "88%",
            background: m.role === "user" ? TEAL : PAPER, color: m.role === "user" ? "#fff" : INK,
            padding: "9px 12px", fontSize: 13.5, lineHeight: 1.5, whiteSpace: "pre-wrap",
          }}>
            {m.content}
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 6, color: MUTED, fontSize: 12.5 }}>
            <Loader2 size={14} className="spin" /> Đang trả lời...
          </div>
        )}
      </div>
      <div style={{ padding: 14, borderTop: `1px solid ${LINE}`, display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Nhập câu hỏi..."
          style={{ flex: 1, border: `1px solid ${LINE}`, padding: "8px 10px", fontSize: 13, fontFamily: sans, outline: "none" }}
        />
        <button onClick={handleSend} disabled={loading} style={{ background: TEAL, border: "none", color: "#fff", width: 36, display: "flex", alignItems: "center", justifyContent: "center", cursor: loading ? "default" : "pointer", opacity: loading ? 0.6 : 1 }}>
          <Send size={15} />
        </button>
      </div>
      <style>{`.spin { animation: spin 0.9s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
export default function CovidDashboardLive() {
  const [tab, setTab] = useState("global");
  const [chatOpen, setChatOpen] = useState(false);
  const [globalDays, setGlobalDays] = useState(2000);
  const [selectedDisease, setSelectedDisease] = useState("");

  const [summary, setSummary] = useState(null);
  const [topCountries, setTopCountries] = useState(null);
  const [trends, setTrends] = useState(null);
  const [etlJobs, setEtlJobs] = useState(null);
  const [vnSummary, setVnSummary] = useState(null);
  const [vnProvinces, setVnProvinces] = useState(null);
  const [vnTrends, setVnTrends] = useState(null);
  const [vnCaseSummary, setVnCaseSummary] = useState(null);
  const [vnCaseTrends, setVnCaseTrends] = useState(null);
  const [vnProvinceCases, setVnProvinceCases] = useState(null);
  const [outbreakDiseases, setOutbreakDiseases] = useState([]);
  const [outbreakSummary, setOutbreakSummary] = useState({});
  const [outbreakTrends, setOutbreakTrends] = useState([]);
  const [outbreakLocations, setOutbreakLocations] = useState([]);
  const [outbreakLatest, setOutbreakLatest] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const diseaseQuery = selectedDisease ? `?disease=${encodeURIComponent(selectedDisease)}` : "";
    const diseaseJoin = selectedDisease ? `&disease=${encodeURIComponent(selectedDisease)}` : "";
    Promise.all([
      fetchJson("/api/summary/global"),
      fetchJson("/api/countries/top?limit=10"),
      fetchJson(`/api/trends/global?days=${globalDays}`),
      fetchJson("/api/etl/jobs?limit=15"),
      fetchJson("/api/summary/vietnam"),
      fetchJson("/api/vietnam/provinces?limit=100"),
      fetchJson("/api/vietnam/trends?days=30"),
      fetchJson("/api/vietnam/cases/summary").catch(() => ({})),
      fetchJson("/api/vietnam/cases/trends?days=3000").catch(() => []),
      fetchJson("/api/vietnam/cases/provinces?limit=10").catch(() => []),
      fetchJson("/api/outbreaks/diseases").catch(() => []),
      fetchJson(`/api/outbreaks/summary${diseaseQuery}`).catch(() => ({})),
      fetchJson(`/api/outbreaks/trends${diseaseQuery}`).catch(() => []),
      fetchJson(`/api/outbreaks/locations?limit=10${diseaseJoin}`).catch(() => []),
      fetchJson(`/api/outbreaks/latest?limit=8${diseaseJoin}`).catch(() => []),
    ])
      .then(([s, tc, tr, jobs, vns, vnp, vnt, vcs, vct, vpc, od, os, ot, ol, oe]) => {
        if (cancelled) return;
        setSummary(s);
        setTopCountries(tc);
        setTrends(tr);
        setEtlJobs(jobs);
        setVnSummary(vns);
        setVnProvinces(vnp);
        setVnTrends(vnt);
        setVnCaseSummary(vcs);
        setVnCaseTrends(vct);
        setVnProvinceCases(vpc);
        setOutbreakDiseases(od);
        setOutbreakSummary(os);
        setOutbreakTrends(ot);
        setOutbreakLocations(ol);
        setOutbreakLatest(oe);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [globalDays, selectedDisease]);

  const todayPoint = trends?.length ? trends[trends.length - 1] : null;
  const cfrOverall = summary && summary.total_cases
    ? ((summary.total_deaths / summary.total_cases) * 100).toFixed(2)
    : null;

  const cfrByCountry = useMemo(() => {
    if (!topCountries) return [];
    return topCountries
      .filter((c) => c.latest_total_cases > 0)
      .map((c) => ({
        name: c.country_name,
        cfr: Number(((c.latest_total_deaths / c.latest_total_cases) * 100).toFixed(2)),
      }))
      .sort((a, b) => b.cfr - a.cfr)
      .slice(0, 8);
  }, [topCountries]);

  const top5VsRest = useMemo(() => {
    if (!topCountries || !summary) return [];
    const top5Sum = topCountries.slice(0, 5).reduce((s, c) => s + (c.latest_total_cases || 0), 0);
    const rest = Math.max((summary.total_cases || 0) - top5Sum, 0);
    return [
      { name: "Top 5 quốc gia", value: top5Sum },
      { name: "Các quốc gia còn lại", value: rest },
    ];
  }, [topCountries, summary]);

  const timeRanges = [
    { label: "30 ngày", value: 30 },
    { label: "90 ngày", value: 90 },
    { label: "1 năm", value: 365 },
    { label: "Toàn bộ", value: 2000 },
  ];

  const timeRangeLabel = timeRanges.find((r) => r.value === globalDays)?.label || "Tùy chọn";

  const trendStepDays = globalDays <= 45 ? 1 : globalDays <= 120 ? 7 : 30;
  const trendStepLabel = trendStepDays === 1 ? "theo ngày" : trendStepDays === 7 ? "theo tuần" : "theo tháng";
  const trendChartData = useMemo(() => {
    const rows = trends || [];
    const groups = [];
    for (let i = 0; i < rows.length; i += trendStepDays) {
      const chunk = rows.slice(i, i + trendStepDays);
      if (!chunk.length) continue;
      const first = chunk[0].date?.slice(0, 10);
      const last = chunk[chunk.length - 1].date?.slice(0, 10);
      const cases = chunk.reduce((sum, item) => sum + (item.total_new_cases_global || 0), 0) / chunk.length;
      const deaths = chunk.reduce((sum, item) => sum + (item.total_new_deaths_global || 0), 0) / chunk.length;
      groups.push({
        date: first === last ? first : `${first} - ${last}`,
        shortDate: trendStepDays === 30
          ? `${first?.slice(5, 7)}/${first?.slice(0, 4)}`
          : `${first?.slice(8, 10)}/${first?.slice(5, 7)}/${first?.slice(0, 4)}`,
        newCases: Math.round(cases),
        newDeaths: Math.round(deaths),
      });
    }
    return groups;
  }, [trends, trendStepDays]);

  const vnChartData = (vnTrends || []).map((t) => ({
    date: t.date?.slice(5),
    dosesAdministered: t.doses_administered,
    dosesPer100: t.doses_per_100,
  }));

  const vnCaseChartData = useMemo(() => {
    const rows = vnCaseTrends || [];
    const groups = [];
    for (let i = 0; i < rows.length; i += 30) {
      const chunk = rows.slice(i, i + 30);
      if (!chunk.length) continue;
      const first = chunk[0];
      const last = chunk[chunk.length - 1];
      const avgNewCases = chunk.reduce((sum, item) => sum + (item.new_cases || 0), 0) / chunk.length;
      const avgNewDeaths = chunk.reduce((sum, item) => sum + (item.new_deaths || 0), 0) / chunk.length;
      groups.push({
        date: `${first.date?.slice(5, 7)}/${first.date?.slice(0, 4)}`,
        totalCases: last.total_cases,
        totalDeaths: last.total_deaths,
        newCases: Math.round(avgNewCases),
        newDeaths: Math.round(avgNewDeaths),
      });
    }
    return groups;
  }, [vnCaseTrends]);

  const vnTopCoverage = [...(vnProvinces || [])]
    .sort((a, b) => (b.doses_per_100 || 0) - (a.doses_per_100 || 0))
    .slice(0, 8);

  const outbreakTrendData = useMemo(() => {
    return (outbreakTrends || []).map((row) => ({
      period: `${String(row.month).padStart(2, "0")}/${row.year}`,
      reportCount: row.report_count || 0,
      reportedCases: row.reported_cases || 0,
      reportedDeaths: row.reported_deaths || 0,
    }));
  }, [outbreakTrends]);

  const outbreakDiseaseShare = useMemo(() => {
    const rows = selectedDisease
      ? (outbreakLocations || []).slice(0, 6).map((row) => ({ name: row.location_text, value: row.report_count || 0 }))
      : (outbreakDiseases || []).slice(0, 6).map((row) => ({ name: row.disease, value: row.report_count || 0 }));
    const known = rows.reduce((sum, row) => sum + row.value, 0);
    const total = outbreakSummary?.report_count || known;
    if (total > known) rows.push({ name: "Khác", value: total - known });
    return rows;
  }, [selectedDisease, outbreakLocations, outbreakDiseases, outbreakSummary]);

  const outbreakCaseTrend = outbreakTrendData.filter((row) => row.reportedCases || row.reportedDeaths);

  return (
    <div style={{ background: PAPER, minHeight: "100vh", fontFamily: sans, color: INK }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        * { box-sizing: border-box; }
      `}</style>

      <header style={{ borderBottom: `1px solid ${LINE}`, background: CARD }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "18px 24px" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <div>
              <p style={{ fontFamily: mono, fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: TEAL, margin: 0 }}>
                Situation Report · Live data từ MySQL
              </p>
              <h1 style={{ fontFamily: serif, fontSize: 26, fontWeight: 600, margin: "4px 0 0" }}>
                Theo dõi dữ liệu dịch bệnh COVID-19
              </h1>
            </div>
            <p style={{ fontFamily: mono, fontSize: 12, color: MUTED, margin: 0, textAlign: "right" }}>
              <span style={{ display: "block" }}>Pipeline chạy lúc: {formatDateTime(summary?.last_updated)}</span>
              <span style={{ display: "block", fontSize: 11, opacity: 0.75 }}>
                Dữ liệu dịch tễ tính đến: {todayPoint?.date?.slice(0, 10) || "—"}
              </span>
            </p>
          </div>

          <nav style={{ display: "flex", gap: 4, marginTop: 18 }}>
            {[
              { id: "global", label: "Toàn cầu", icon: Globe2 },
              { id: "vietnam", label: "Việt Nam", icon: MapPinned },
              { id: "outbreaks", label: "WHO Monitor", icon: RadioTower },
              { id: "etl", label: "Nhật ký ETL", icon: Activity },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
                  fontFamily: sans, fontSize: 13, fontWeight: 500, border: "none",
                  borderBottom: tab === id ? `2px solid ${TEAL}` : "2px solid transparent",
                  background: "transparent", color: tab === id ? INK : MUTED, cursor: "pointer",
                }}
              >
                <Icon size={14} strokeWidth={2} />
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px 60px" }}>
        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: MUTED, fontSize: 13, padding: "40px 0", justifyContent: "center" }}>
            <Loader2 size={16} className="spin" /> Đang tải dữ liệu từ API...
            <style>{`.spin { animation: spin 0.9s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {!loading && error && <ErrorBox message={error} />}

        {!loading && !error && tab === "global" && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 1, background: LINE, marginBottom: 28 }}>
              <StatCard label="Tổng ca nhiễm" value={formatNumber(summary?.total_cases)} />
              <StatCard label="Tổng tử vong" value={formatNumber(summary?.total_deaths)} accent={CORAL} sub={cfrOverall ? `CFR: ${cfrOverall}%` : null} />
              <StatCard label="Tiêm chủng TB" value={summary?.avg_vaccination_rate != null ? `${summary.avg_vaccination_rate}%` : "—"} accent={TEAL} />
              <StatCard label="Số quốc gia theo dõi" value={summary?.country_count ?? "—"} />
              <StatCard label="Ca mới gần nhất" value={formatNumber(todayPoint?.total_new_cases_global)} accent={TEAL} sub={todayPoint ? `Ngày ${todayPoint.date?.slice(0, 10)}` : null} />
              <StatCard label="Tử vong mới gần nhất" value={formatNumber(todayPoint?.total_new_deaths_global)} accent={CORAL} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20, marginBottom: 28 }}>
              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
                  <div>
                    <h2 style={{ fontFamily: serif, fontSize: 18, fontWeight: 600, margin: 0 }}>Xu hướng ca nhiễm mới</h2>
                    <p style={{ margin: "4px 0 0", fontSize: 12, color: MUTED }}>{trendChartData.length} mốc · {timeRangeLabel} · {trendStepLabel}</p>
                  </div>
                  <div style={{ display: "flex", border: `1px solid ${LINE}`, background: PAPER }}>
                    {timeRanges.map((range) => (
                      <button
                        key={range.value}
                        onClick={() => setGlobalDays(range.value)}
                        style={{
                          border: "none",
                          borderRight: `1px solid ${LINE}`,
                          padding: "7px 11px",
                          background: globalDays === range.value ? TEAL : "transparent",
                          color: globalDays === range.value ? CARD : MUTED,
                          fontFamily: sans,
                          fontSize: 12,
                          cursor: "pointer",
                        }}
                      >
                        {range.label}
                      </button>
                    ))}
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={trendChartData} margin={{ top: 4, right: 14, left: -8, bottom: 0 }}>
                    <CartesianGrid stroke={LINE} vertical={false} />
                    <XAxis dataKey="shortDate" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={{ stroke: LINE }} tickLine={false} interval={Math.ceil(trendChartData.length / 10)} />
                    <YAxis domain={[0, "auto"]} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} tickFormatter={formatNumber} width={52} />
                    <Tooltip content={<CustomTooltip unit=" ca/ngày TB" />} />
                    <Line type="monotone" dataKey="newCases" stroke={TEAL} strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </section>

              <section style={{ display: "none" }}>
                <SectionTitle>Tiêm chủng trung bình</SectionTitle>
                <div style={{ position: "relative", height: 200 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <RadialBarChart innerRadius="72%" outerRadius="100%" data={[{ value: summary?.avg_vaccination_rate || 0, fill: TEAL }]} startAngle={90} endAngle={-270}>
                      <RadialBar background={{ fill: PAPER }} dataKey="value" cornerRadius={6} />
                    </RadialBarChart>
                  </ResponsiveContainer>
                  <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ fontFamily: mono, fontSize: 26, fontWeight: 600 }}>{summary?.avg_vaccination_rate ?? "—"}%</span>
                    <span style={{ fontFamily: sans, fontSize: 11, color: MUTED }}>trung bình {summary?.country_count} quốc gia</span>
                  </div>
                </div>
              </section>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20, marginBottom: 28 }}>
              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>Tử vong mới trung bình</SectionTitle>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={trendChartData} margin={{ top: 4, right: 14, left: -8, bottom: 0 }}>
                    <CartesianGrid stroke={LINE} vertical={false} />
                    <XAxis dataKey="shortDate" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={{ stroke: LINE }} tickLine={false} interval={Math.ceil(trendChartData.length / 10)} />
                    <YAxis domain={[0, "auto"]} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} tickFormatter={formatNumber} width={52} />
                    <Tooltip content={<CustomTooltip unit=" ca/ngày TB" />} />
                    <Bar dataKey="newDeaths" fill={CORAL} radius={[3, 3, 0, 0]} maxBarSize={46} />
                  </BarChart>
                </ResponsiveContainer>
              </section>

              <section style={{ display: "none" }}>
                <SectionTitle>Tỷ trọng ca nhiễm: Top 5 vs còn lại</SectionTitle>
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie data={top5VsRest} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={2}>
                      {top5VsRest.map((entry, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontFamily: sans, fontSize: 11.5 }} />
                  </PieChart>
                </ResponsiveContainer>
              </section>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20 }}>
              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle note="agg_country_summary">Top 10 quốc gia theo tổng ca nhiễm</SectionTitle>
                {topCountries && <RankedBarList data={topCountries} nameKey="country_name" valueKey="latest_total_cases" highlightName="Vietnam" />}
              </section>

              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>Tỷ lệ tử vong (CFR %) — trong top 10</SectionTitle>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={cfrByCountry} layout="vertical" margin={{ left: 10 }}>
                    <CartesianGrid stroke={LINE} horizontal={false} />
                    <XAxis type="number" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} unit="%" />
                    <YAxis type="category" dataKey="name" tick={{ fontFamily: "Inter", fontSize: 11.5, fill: INK }} axisLine={false} tickLine={false} width={80} />
                    <Tooltip content={<CustomTooltip unit="%" />} />
                    <Bar dataKey="cfr" radius={[0, 3, 3, 0]}>
                      {cfrByCountry.map((d, i) => <Cell key={i} fill={d.name === "Vietnam" ? TEAL : CORAL} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </section>
            </div>
          </>
        )}

        {!loading && !error && tab === "vietnam" && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 1, background: LINE, marginBottom: 28 }}>
              <StatCard label="Dân số theo dõi" value={formatNumber(vnSummary?.population)} />
              <StatCard label="Liều đã tiêm" value={formatNumber(vnSummary?.doses_administered)} accent={TEAL} />
              <StatCard label="Liều phân bổ" value={formatNumber(vnSummary?.doses_distributed)} accent={AMBER} />
              <StatCard label="Liều / 100 dân" value={vnSummary?.doses_per_100 != null ? `${vnSummary.doses_per_100}` : "—"} accent={CORAL} sub={`${vnSummary?.province_count ?? "—"} địa phương`} />
            </div>

            <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24, marginBottom: 28 }}>
              <SectionTitle>Nguồn ca mắc COVID-19 tại Việt Nam</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 1, background: LINE, marginBottom: 22 }}>
                <StatCard label="Tổng ca nhiễm" value={formatNumber(vnCaseSummary?.total_cases)} />
                <StatCard label="Tổng tử vong" value={formatNumber(vnCaseSummary?.total_deaths)} accent={CORAL} />
                <StatCard label="Ca mới cập nhật" value={formatNumber(vnCaseSummary?.new_cases)} accent={TEAL} sub={vnCaseSummary?.latest_date ? `Ngày ${vnCaseSummary.latest_date}` : null} />
                <StatCard label="CFR Việt Nam" value={vnCaseSummary?.cfr != null ? `${vnCaseSummary.cfr}%` : "—"} accent={AMBER} />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 20, alignItems: "start" }}>
                <section style={{ border: `1px solid ${LINE}`, padding: 18 }}>
                  <SectionTitle>Diễn biến tổng ca nhiễm</SectionTitle>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={vnCaseChartData} margin={{ top: 4, right: 12, left: -6, bottom: 0 }}>
                      <CartesianGrid stroke={LINE} vertical={false} />
                      <XAxis dataKey="date" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={{ stroke: LINE }} tickLine={false} interval={Math.ceil(vnCaseChartData.length / 8)} />
                      <YAxis domain={[0, "auto"]} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} tickFormatter={formatNumber} width={58} />
                      <Tooltip content={<CustomTooltip unit=" ca" />} />
                      <Line type="monotone" dataKey="totalCases" stroke={TEAL} strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </section>

                <section style={{ border: `1px solid ${LINE}`, padding: 18 }}>
                  <SectionTitle>Ca mới trung bình theo tháng</SectionTitle>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={vnCaseChartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                      <CartesianGrid stroke={LINE} vertical={false} />
                      <XAxis dataKey="date" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={{ stroke: LINE }} tickLine={false} interval={Math.ceil(vnCaseChartData.length / 6)} />
                      <YAxis domain={[0, "auto"]} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} tickFormatter={formatNumber} width={52} />
                      <Tooltip content={<CustomTooltip unit=" ca/ngày TB" />} />
                      <Bar dataKey="newCases" fill={AMBER} radius={[3, 3, 0, 0]} maxBarSize={38} />
                    </BarChart>
                  </ResponsiveContainer>
                </section>
              </div>

              <div style={{ marginTop: 20 }}>
                <SectionTitle>Top địa phương theo tổng ca nhiễm</SectionTitle>
                <RankedBarList data={vnProvinceCases || []} nameKey="province_name" valueKey="total_cases" />
              </div>
            </section>

            <div style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 20, marginBottom: 28, alignItems: "start" }}>
              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>Bản đồ nhiệt tiêm chủng Việt Nam</SectionTitle>
                <VietnamGeoHeatMap data={vnProvinces || []} />
              </section>

              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>Top địa phương theo liều / 100 dân</SectionTitle>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={vnTopCoverage} layout="vertical" margin={{ left: 12, right: 4 }}>
                    <CartesianGrid stroke={LINE} horizontal={false} />
                    <XAxis type="number" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="province_name" tick={{ fontFamily: "Inter", fontSize: 11.5, fill: INK }} axisLine={false} tickLine={false} width={94} />
                    <Tooltip content={<CustomTooltip unit=" liều/100 dân" />} />
                    <Bar dataKey="doses_per_100" fill={AMBER} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </section>
            </div>

            <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
              <SectionTitle>Top 15 địa phương theo số liều đã tiêm</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "32px 1fr 120px 130px 130px 110px", padding: "6px 0", borderBottom: `1px solid ${LINE}`, fontFamily: mono, fontSize: 10.5, color: MUTED, textTransform: "uppercase" }}>
                <span>#</span><span>Tỉnh/thành</span><span style={{ textAlign: "right" }}>Dân số</span><span style={{ textAlign: "right" }}>Phân bổ</span><span style={{ textAlign: "right" }}>Đã tiêm</span><span style={{ textAlign: "right" }}>Liều/100</span>
              </div>
              {(vnProvinces || []).slice(0, 15).map((p, i) => (
                <div key={p.province_name} style={{ display: "grid", gridTemplateColumns: "32px 1fr 120px 130px 130px 110px", alignItems: "center", padding: "10px 0", borderBottom: `1px solid ${LINE}`, fontSize: 13 }}>
                  <span style={{ fontFamily: mono, color: MUTED }}>{String(i + 1).padStart(2, "0")}</span>
                  <span style={{ fontWeight: 500 }}>{p.province_name}</span>
                  <span style={{ textAlign: "right", fontFamily: mono }}>{formatNumber(p.population)}</span>
                  <span style={{ textAlign: "right", fontFamily: mono, color: AMBER }}>{formatNumber(p.doses_distributed)}</span>
                  <span style={{ textAlign: "right", fontFamily: mono, color: TEAL }}>{formatNumber(p.doses_administered)}</span>
                  <span style={{ textAlign: "right", fontFamily: mono, color: CORAL }}>{p.doses_per_100 ?? "—"}</span>
                </div>
              ))}
            </section>
          </>
        )}

        {!loading && !error && tab === "outbreaks" && (
          <>
            <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24, marginBottom: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 18, flexWrap: "wrap" }}>
                <div>
                  <p style={{ fontFamily: mono, fontSize: 10.5, letterSpacing: "0.08em", textTransform: "uppercase", color: TEAL, margin: "0 0 6px" }}>
                    WHO Disease Outbreak News
                  </p>
                  <h2 style={{ fontFamily: serif, fontSize: 20, fontWeight: 600, margin: 0 }}>Giám sát cảnh báo dịch bệnh hiện hành</h2>
                  <p style={{ maxWidth: 660, margin: "8px 0 0", fontSize: 13, color: MUTED, lineHeight: 1.55 }}>
                    Nguồn dữ liệu chính thức từ WHO, cập nhật theo các bản tin outbreak. Tab này chứng minh pipeline có thể mở rộng sang nguồn dữ liệu đang tiếp tục phát sinh, không chỉ dashboard COVID lịch sử.
                  </p>
                </div>
                <label style={{ display: "grid", gap: 6, minWidth: 250 }}>
                  <span style={{ fontFamily: mono, fontSize: 10.5, color: MUTED, textTransform: "uppercase" }}>Lọc theo dịch bệnh</span>
                  <select
                    value={selectedDisease}
                    onChange={(e) => setSelectedDisease(e.target.value)}
                    style={{ border: `1px solid ${LINE}`, background: PAPER, padding: "9px 10px", fontFamily: sans, fontSize: 13, color: INK, outline: "none" }}
                  >
                    <option value="">Tất cả dịch bệnh</option>
                    {(outbreakDiseases || []).map((row) => (
                      <option key={row.disease} value={row.disease}>
                        {row.disease} ({row.report_count})
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 1, background: LINE, marginBottom: 24 }}>
              <StatCard label="Bản tin WHO" value={formatNumber(outbreakSummary?.report_count)} />
              <StatCard label="Dịch bệnh theo dõi" value={formatNumber(outbreakSummary?.disease_count)} accent={TEAL} />
              <StatCard label="Khu vực/quốc gia" value={formatNumber(outbreakSummary?.location_count)} accent={AMBER} />
              <StatCard label="Ca được trích xuất" value={formatNumber(outbreakSummary?.reported_cases)} accent={TEAL} />
              <StatCard label="Tử vong được trích xuất" value={formatNumber(outbreakSummary?.reported_deaths)} accent={CORAL} />
              <StatCard label="Cập nhật mới nhất" value={formatDateOnly(outbreakSummary?.latest_report_date)} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1.35fr 0.85fr", gap: 20, marginBottom: 24 }}>
              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>Số bản tin WHO theo thời gian</SectionTitle>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={outbreakTrendData} margin={{ top: 4, right: 14, left: -8, bottom: 0 }}>
                    <CartesianGrid stroke={LINE} vertical={false} />
                    <XAxis dataKey="period" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={{ stroke: LINE }} tickLine={false} interval={Math.ceil(outbreakTrendData.length / 10)} />
                    <YAxis domain={[0, "auto"]} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} tickFormatter={formatNumber} width={50} />
                    <Tooltip content={<CustomTooltip unit=" bản tin" />} />
                    <Line type="monotone" dataKey="reportCount" stroke={TEAL} strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </section>

              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>{selectedDisease ? "Tỷ trọng theo khu vực" : "Tỷ trọng theo dịch bệnh"}</SectionTitle>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={outbreakDiseaseShare} dataKey="value" nameKey="name" innerRadius={52} outerRadius={84} paddingAngle={2}>
                      {outbreakDiseaseShare.map((_, i) => (
                        <Cell key={i} fill={[TEAL, AMBER, CORAL, "#4B9B84", "#D58A45", "#8A8174", "#C7C5B8"][i % 7]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip unit=" bản tin" />} />
                    <Legend wrapperStyle={{ fontFamily: sans, fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              </section>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>Top khu vực/quốc gia được WHO nhắc tới</SectionTitle>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={outbreakLocations || []} layout="vertical" margin={{ left: 12, right: 4 }}>
                    <CartesianGrid stroke={LINE} horizontal={false} />
                    <XAxis type="number" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="location_text" tick={{ fontFamily: "Inter", fontSize: 11, fill: INK }} axisLine={false} tickLine={false} width={118} />
                    <Tooltip content={<CustomTooltip unit=" bản tin" />} />
                    <Bar dataKey="report_count" fill={AMBER} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </section>

              <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
                <SectionTitle>Số ca/tử vong trích xuất từ bản tin</SectionTitle>
                {outbreakCaseTrend.length ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={outbreakCaseTrend} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
                      <CartesianGrid stroke={LINE} vertical={false} />
                      <XAxis dataKey="period" tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={{ stroke: LINE }} tickLine={false} interval={Math.ceil(outbreakCaseTrend.length / 8)} />
                      <YAxis domain={[0, "auto"]} tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: MUTED }} axisLine={false} tickLine={false} tickFormatter={formatNumber} width={52} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontFamily: sans, fontSize: 11 }} />
                      <Bar dataKey="reportedCases" name="Ca bệnh" fill={TEAL} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="reportedDeaths" name="Tử vong" fill={CORAL} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p style={{ color: MUTED, fontSize: 13, lineHeight: 1.55, margin: 0 }}>
                    Một số bản tin WHO chỉ là cảnh báo/tình hình dịch và không luôn có bảng số ca chuẩn. Khi nội dung có số ca hoặc tử vong, pipeline sẽ tự trích xuất để đưa vào biểu đồ này.
                  </p>
                )}
              </section>
            </div>

            <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
              <SectionTitle note="raw_who_outbreak_news">Bản tin WHO mới nhất</SectionTitle>
              <div style={{ display: "grid", gap: 12 }}>
                {(outbreakLatest || []).map((item, i) => (
                  <a
                    key={`${item.title}-${i}`}
                    href={item.source_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ display: "grid", gridTemplateColumns: "110px 1fr 130px", gap: 14, alignItems: "start", textDecoration: "none", color: INK, borderBottom: `1px solid ${LINE}`, paddingBottom: 12 }}
                  >
                    <span style={{ fontFamily: mono, fontSize: 11, color: MUTED }}>{formatDateOnly(item.publication_date)}</span>
                    <span>
                      <strong style={{ display: "block", fontSize: 13.5, marginBottom: 3 }}>{item.title}</strong>
                      <span style={{ display: "block", fontSize: 12, color: MUTED, lineHeight: 1.45 }}>{item.location_text}</span>
                    </span>
                    <span style={{ fontFamily: mono, fontSize: 11, color: TEAL, textAlign: "right" }}>{item.disease}</span>
                  </a>
                ))}
                {!outbreakLatest?.length && (
                  <p style={{ color: MUTED, fontSize: 13, padding: "20px 0", textAlign: "center" }}>
                    Chưa có dữ liệu WHO. Hãy chạy `python who_outbreak_load.py` để nạp nguồn Disease Outbreak News.
                  </p>
                )}
              </div>
            </section>
          </>
        )}

        {!loading && !error && tab === "etl" && (
          <section style={{ background: CARD, border: `1px solid ${LINE}`, padding: 24 }}>
            <SectionTitle note="etl_job_log">Nhật ký các lần chạy pipeline</SectionTitle>
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "1.3fr 0.8fr 0.8fr 1fr 1fr", padding: "6px 0", borderBottom: `1px solid ${LINE}`, fontFamily: mono, fontSize: 10.5, color: MUTED, textTransform: "uppercase" }}>
                <span>Job</span><span>Trạng thái</span><span style={{ textAlign: "right" }}>Số dòng</span><span style={{ textAlign: "right" }}>Bắt đầu</span><span style={{ textAlign: "right" }}>Kết thúc</span>
              </div>
              {(etlJobs || []).map((job) => {
                const c = STATUS_COLORS[job.status] || STATUS_COLORS.running;
                return (
                  <div key={job.job_id} style={{ display: "grid", gridTemplateColumns: "1.3fr 0.8fr 0.8fr 1fr 1fr", alignItems: "center", padding: "10px 0", borderBottom: `1px solid ${LINE}`, fontSize: 13 }}>
                    <span style={{ fontFamily: mono }}>{job.job_name}</span>
                    <span>
                      <span style={{ background: c.bg, color: c.fg, fontSize: 11.5, padding: "2px 8px" }}>{job.status}</span>
                    </span>
                    <span style={{ textAlign: "right", fontFamily: mono, color: MUTED }}>{job.rows_processed ?? "—"}</span>
                    <span style={{ textAlign: "right", fontFamily: mono, color: MUTED, fontSize: 11.5 }}>{formatDateTime(job.started_at)}</span>
                    <span style={{ textAlign: "right", fontFamily: mono, color: MUTED, fontSize: 11.5 }}>{formatDateTime(job.finished_at)}</span>
                  </div>
                );
              })}
              {!etlJobs?.length && <p style={{ color: MUTED, fontSize: 13, padding: "20px 0", textAlign: "center" }}>Chưa có log nào.</p>}
            </div>
          </section>
        )}
      </main>

      {!chatOpen && (
        <button onClick={() => setChatOpen(true)} style={{
          position: "fixed", bottom: 24, right: 24, background: TEAL, color: "#fff",
          border: "none", padding: "12px 18px", display: "flex", alignItems: "center", gap: 8,
          fontFamily: sans, fontSize: 13.5, fontWeight: 500, cursor: "pointer",
          boxShadow: "0 6px 16px rgba(14,110,106,0.35)", zIndex: 40,
        }}>
          <Stethoscope size={16} /> Hỏi trợ lý y tế
        </button>
      )}
      <AiHealthAssistant open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
