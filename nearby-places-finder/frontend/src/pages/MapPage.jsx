import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer, TileLayer, Marker, Popup, Circle, Polygon, Polyline, CircleMarker, useMapEvents,
} from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { api, errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { CATEGORIES, iconFor } from "../categories";
import PlaceForm from "../components/PlaceForm";

const PUNE = [18.5204, 73.8567];

// Small helper component: tells us where the user clicked on the map.
function ClickHandler({ onClick }) {
  useMapEvents({ click: (e) => onClick(e.latlng) });
  return null;
}

const MODES = [
  { id: "browse", label: "👀 Browse", hint: "Click a marker to see details." },
  { id: "add", label: "➕ Add place", hint: "Click on the map where the new place is." },
  { id: "nearby", label: "📍 Nearby", hint: "Click the map to find places within the radius." },
  { id: "nearest", label: "🔝 Nearest N", hint: "Click the map to find the N closest places." },
  { id: "polygon", label: "⬠ Polygon", hint: "Click 3+ points to outline an area, then press Finish." },
];

export default function MapPage() {
  const { user, logout } = useAuth();
  const mapRef = useRef(null);

  const [places, setPlaces] = useState([]);          // GeoJSON features shown on the map
  const [activeCats, setActiveCats] = useState([]);   // category filter ([] = all)
  const [mode, setMode] = useState("browse");
  const [draft, setDraft] = useState(null);           // {lat,lng} of a place being added
  const [editing, setEditing] = useState(null);       // feature being edited
  const [selected, setSelected] = useState(null);     // feature whose popup is open
  const [selDistance, setSelDistance] = useState(null);
  const [radius, setRadius] = useState(2);
  const [nearN, setNearN] = useState(5);
  const [center, setCenter] = useState(null);         // centre of nearby / nearest search
  const [polyPts, setPolyPts] = useState([]);         // polygon being drawn [[lat,lng],...]
  const [polyDone, setPolyDone] = useState(null);     // finished polygon
  const [results, setResults] = useState(null);       // {title, features}
  const [me, setMe] = useState(null);                 // browser geolocation
  const [toast, setToast] = useState(null);
  const [importReport, setImportReport] = useState(null);
  const [busy, setBusy] = useState(false);

  const notify = useCallback((type, text) => setToast({ type, text }), []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  // ---------- load places (re-runs when the category filter changes) ----------
  const loadPlaces = useCallback(async () => {
    try {
      const { data } = await api.get("/places/", { params: { category: activeCats.join(",") || undefined } });
      setPlaces(data.features);
    } catch (e) {
      notify("error", errorMessage(e));
    }
  }, [activeCats, notify]);
  useEffect(() => { loadPlaces(); }, [loadPlaces]);

  // ---------- distance from my location to the selected place (calculated in PostGIS) ----------
  useEffect(() => {
    setSelDistance(null);
    if (!selected || !me) return;
    api.get(`/places/${selected.id}/distance/`, { params: { lat: me.lat, lng: me.lng } })
      .then(({ data }) => setSelDistance(data.distance_m))
      .catch(() => {});
  }, [selected, me]);

  const highlighted = useMemo(() => new Set((results?.features || []).map((f) => f.id)), [results]);

  // ---------- spatial searches ----------
  const catParam = activeCats.join(",") || undefined;

  const runNearby = useCallback(async (pt, km) => {
    setCenter(pt);
    setBusy(true);
    try {
      const { data } = await api.get("/places/nearby/", { params: { lat: pt.lat, lng: pt.lng, radius_km: km, category: catParam } });
      setResults({ title: `Within ${km} km: ${data.features.length} place(s)`, features: data.features });
    } catch (e) { notify("error", errorMessage(e)); } finally { setBusy(false); }
  }, [catParam, notify]);

  const runNearest = useCallback(async (pt, n) => {
    setCenter(pt);
    setBusy(true);
    try {
      const { data } = await api.get("/places/nearest/", { params: { lat: pt.lat, lng: pt.lng, n, category: catParam } });
      setResults({ title: `Nearest ${data.features.length} place(s)`, features: data.features });
    } catch (e) { notify("error", errorMessage(e)); } finally { setBusy(false); }
  }, [catParam, notify]);

  // re-run the nearby search when the radius slider moves (debounced)
  useEffect(() => {
    if (mode !== "nearby" || !center) return;
    const t = setTimeout(() => runNearby(center, radius), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [radius]);

  async function finishPolygon() {
    if (polyPts.length < 3) return notify("error", "Click at least 3 points on the map to make a polygon.");
    // GeoJSON wants [lng, lat] and a closed ring (first point repeated at the end)
    const ring = [...polyPts, polyPts[0]].map(([lat, lng]) => [lng, lat]);
    setBusy(true);
    try {
      const { data } = await api.post("/places/within/", { polygon: { type: "Polygon", coordinates: [ring] } });
      setResults({ title: `Inside polygon: ${data.features.length} place(s)`, features: data.features });
      setPolyDone(polyPts);
      setPolyPts([]);
    } catch (e) { notify("error", errorMessage(e)); } finally { setBusy(false); }
  }

  // ---------- map click depends on the current tool ----------
  function onMapClick({ lat, lng }) {
    if (mode === "add") { setEditing(null); setDraft({ lat, lng }); }
    else if (mode === "nearby") runNearby({ lat, lng }, radius);
    else if (mode === "nearest") runNearest({ lat, lng }, nearN);
    else if (mode === "polygon") { setPolyDone(null); setPolyPts((p) => [...p, [lat, lng]]); }
  }

  function clearTool() {
    setDraft(null); setCenter(null); setPolyPts([]); setPolyDone(null); setResults(null);
  }
  function changeMode(m) {
    clearTool(); setEditing(null); setSelected(null); setMode(m);
  }

  // ---------- create / update / delete ----------
  async function savePlace(v) {
    const body = {
      type: "Feature",
      geometry: { type: "Point", coordinates: [v.lng, v.lat] },
      properties: { name: v.name, category: v.category, description: v.description },
    };
    if (editing) await api.put(`/places/${editing.id}/`, body);   // throws on error -> shown in the form
    else await api.post("/places/", body);
    notify("success", editing ? "Place updated." : "Place added.");
    setDraft(null); setEditing(null); setSelected(null);
    await loadPlaces();
  }

  async function deletePlace(f) {
    if (!window.confirm(`Delete "${f.properties.name}"?`)) return;
    try {
      await api.delete(`/places/${f.id}/`);
      notify("success", "Place deleted.");
      setSelected(null);
      await loadPlaces();
    } catch (e) { notify("error", errorMessage(e)); }
  }

  // ---------- bulk import ----------
  async function onImport(e) {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      const { data } = await api.post("/places/import/", fd);
      setImportReport(data);
      notify("success", `Imported ${data.created} place(s), rejected ${data.rejected_count}.`);
      await loadPlaces();
    } catch (err) {
      if (err.response?.data?.rejected) setImportReport(err.response.data);
      notify("error", errorMessage(err));
    } finally { setBusy(false); }
  }

  // ---------- browser geolocation ----------
  function locateMe() {
    if (!navigator.geolocation) return notify("error", "Your browser does not support geolocation.");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setMe(p);
        mapRef.current?.flyTo([p.lat, p.lng], 14);
      },
      (err) => notify("error", err.code === 1 ? "Location permission denied. Allow it in your browser settings."
                                                : "Could not get your location."),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  function flyToFeature(f) {
    const [lng, lat] = f.geometry.coordinates;
    mapRef.current?.flyTo([lat, lng], 16);
    setSelected(f);
  }

  const fmtDistance = (m) => (m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`);
  const toggleCat = (c) => setActiveCats((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));
  const currentMode = MODES.find((m) => m.id === mode);

  return (
    <div className="app">
      <header className="topbar">
        <strong>📍 Nearby Places Finder</strong>
        <span className="spacer" />
        {user.is_staff && <span className="badge">Admin: viewing all users' places</span>}
        <span className="muted-light">{user.email}</span>
        <button className="btn small" onClick={logout}>Log out</button>
      </header>

      <div className="main">
        <aside className="sidebar">
          {toast && <div className={`alert ${toast.type}`}>{toast.text}</div>}

          <div className="card">
            <h3>Filter by category</h3>
            <div className="chips">
              {Object.entries(CATEGORIES).map(([k, c]) => (
                <button key={k} className={`chip ${activeCats.includes(k) ? "on" : ""}`} onClick={() => toggleCat(k)}>
                  {c.emoji} {c.label}
                </button>
              ))}
            </div>
            <p className="muted">{places.length} place(s) shown{activeCats.length === 0 ? " (all categories)" : ""}</p>
          </div>

          <div className="card">
            <h3>Tools</h3>
            <div className="chips">
              {MODES.map((m) => (
                <button key={m.id} className={`chip ${mode === m.id ? "on" : ""}`} onClick={() => changeMode(m.id)}>{m.label}</button>
              ))}
            </div>
            <p className="muted">{currentMode.hint}</p>

            {mode === "nearby" && (
              <label>Radius: <b>{radius} km</b>
                <input type="range" min="0.5" max="20" step="0.5" value={radius} onChange={(e) => setRadius(Number(e.target.value))} />
              </label>
            )}
            {mode === "nearest" && (
              <label>N: <b>{nearN}</b>
                <input type="range" min="1" max="20" value={nearN} onChange={(e) => setNearN(Number(e.target.value))} />
              </label>
            )}
            {mode === "polygon" && (
              <div className="row">
                <button className="btn primary small" onClick={finishPolygon} disabled={busy}>Finish ({polyPts.length} pts)</button>
                <button className="btn small" onClick={() => { setPolyPts([]); setPolyDone(null); setResults(null); }}>Reset</button>
              </div>
            )}
            <div className="row" style={{ marginTop: 8 }}>
              <button className="btn small" onClick={locateMe}>🎯 My location</button>
              {(results || center || polyDone) && <button className="btn small" onClick={clearTool}>Clear results</button>}
            </div>
          </div>

          {(draft || editing) && (
            <PlaceForm
              key={editing ? `e${editing.id}` : `d${draft.lat}${draft.lng}`}
              title={editing ? "Edit place" : "Add a new place"}
              submitLabel={editing ? "Save changes" : "Add place"}
              initial={editing
                ? { ...editing.properties, lng: editing.geometry.coordinates[0], lat: editing.geometry.coordinates[1] }
                : { lat: Number(draft.lat.toFixed(6)), lng: Number(draft.lng.toFixed(6)) }}
              onSubmit={savePlace}
              onCancel={() => { setDraft(null); setEditing(null); }}
            />
          )}

          {results && (
            <div className="card">
              <h3>{results.title}</h3>
              {results.features.length === 0 && <p className="muted">No places found.</p>}
              <ul className="results">
                {results.features.map((f) => (
                  <li key={f.id} onClick={() => flyToFeature(f)}>
                    <span>{CATEGORIES[f.properties.category]?.emoji} {f.properties.name}</span>
                    {f.properties.distance_m != null && <small>{fmtDistance(f.properties.distance_m)}</small>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card">
            <h3>Bulk import</h3>
            <p className="muted">Upload a .geojson or .csv file (columns: name, category, description, latitude, longitude).</p>
            <input type="file" accept=".geojson,.json,.csv" onChange={onImport} disabled={busy} />
            {importReport && (
              <div className="report">
                <b>Imported {importReport.created}</b>, rejected {importReport.rejected_count}
                {importReport.rejected?.length > 0 && (
                  <ul>{importReport.rejected.slice(0, 8).map((r) => <li key={r.row}>Row {r.row}: {r.reason}</li>)}</ul>
                )}
              </div>
            )}
          </div>
        </aside>

        <div className="map-wrap">
          <MapContainer center={PUNE} zoom={12} ref={mapRef} className="map">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <ClickHandler onClick={onMapClick} />

            {/* Clustering: nearby markers are grouped into numbered circles when zoomed out */}
            <MarkerClusterGroup chunkedLoading>
              {places.map((f) => {
                const [lng, lat] = f.geometry.coordinates;
                return (
                  <Marker key={f.id} position={[lat, lng]}
                          icon={iconFor(f.properties.category, highlighted.has(f.id))}
                          eventHandlers={{ click: () => setSelected(f) }} />
                );
              })}
            </MarkerClusterGroup>

            {/* One shared popup for the selected marker (faster than 10,000 popups) */}
            {selected && (
              <Popup key={selected.id}
                     position={[selected.geometry.coordinates[1], selected.geometry.coordinates[0]]}
                     offset={[0, -14]}
                     eventHandlers={{ remove: () => setSelected((cur) => (cur?.id === selected.id ? null : cur)) }}>
                <div className="popup">
                  <b>{CATEGORIES[selected.properties.category]?.emoji} {selected.properties.name}</b>
                  <div className="muted">{CATEGORIES[selected.properties.category]?.label}</div>
                  {selected.properties.description && <p>{selected.properties.description}</p>}
                  {user.is_staff && <div className="muted">Owner: {selected.properties.owner_email}</div>}
                  <div>
                    {me ? (selDistance != null ? <>📏 <b>{fmtDistance(selDistance)}</b> from you</> : "Calculating distance…")
                        : <span className="muted">Press "My location" to see the distance.</span>}
                  </div>
                  {selected.properties.is_owner && (
                    <div className="row" style={{ marginTop: 6 }}>
                      <button className="btn small" onClick={() => { setDraft(null); setEditing(selected); }}>Edit</button>
                      <button className="btn small danger" onClick={() => deletePlace(selected)}>Delete</button>
                    </div>
                  )}
                </div>
              </Popup>
            )}

            {draft && <Marker position={[draft.lat, draft.lng]} icon={iconFor("new")} />}
            {center && mode === "nearby" && (
              <Circle center={[center.lat, center.lng]} radius={radius * 1000} pathOptions={{ color: "#2563eb", fillOpacity: 0.08 }} />
            )}
            {center && <CircleMarker center={[center.lat, center.lng]} radius={6} pathOptions={{ color: "#1d4ed8" }} />}
            {polyPts.length > 0 && (
              <>
                <Polyline positions={polyPts} pathOptions={{ color: "#7c3aed" }} />
                {polyPts.map((p, i) => <CircleMarker key={i} center={p} radius={4} pathOptions={{ color: "#7c3aed" }} />)}
              </>
            )}
            {polyDone && <Polygon positions={polyDone} pathOptions={{ color: "#7c3aed", fillOpacity: 0.12 }} />}
            {me && <CircleMarker center={[me.lat, me.lng]} radius={8} pathOptions={{ color: "#fff", fillColor: "#2563eb", fillOpacity: 1, weight: 3 }} />}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}
