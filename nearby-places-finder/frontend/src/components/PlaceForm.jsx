import { useState } from "react";
import { errorMessage } from "../api";
import { CATEGORIES } from "../categories";

// Used for both "add" and "edit". `onSubmit` must throw if the server rejects the data.
export default function PlaceForm({ title, initial, submitLabel, onSubmit, onCancel }) {
  const [name, setName] = useState(initial.name || "");
  const [category, setCategory] = useState(initial.category || "hospital");
  const [description, setDescription] = useState(initial.description || "");
  const [lat, setLat] = useState(String(initial.lat ?? ""));
  const [lng, setLng] = useState(String(initial.lng ?? ""));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    const latN = Number(lat), lngN = Number(lng);
    if (!name.trim()) return setError("Name cannot be empty.");
    if (lat === "" || lng === "" || Number.isNaN(latN) || Number.isNaN(lngN)) return setError("Latitude and longitude must be numbers.");
    if (latN < -90 || latN > 90) return setError("Latitude must be between -90 and 90.");
    if (lngN < -180 || lngN > 180) return setError("Longitude must be between -180 and 180.");
    setBusy(true);
    try {
      await onSubmit({ name: name.trim(), category, description: description.trim(), lat: latN, lng: lngN });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit} noValidate>
      <h3>{title}</h3>
      {error && <div className="alert error">{error}</div>}
      <label>Name<input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
      <label>Category
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {Object.entries(CATEGORIES).map(([k, c]) => <option key={k} value={k}>{c.emoji} {c.label}</option>)}
        </select>
      </label>
      <label>Description<textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      <div className="row">
        <label>Latitude<input value={lat} onChange={(e) => setLat(e.target.value)} /></label>
        <label>Longitude<input value={lng} onChange={(e) => setLng(e.target.value)} /></label>
      </div>
      <div className="row">
        <button className="btn primary" disabled={busy}>{busy ? "Saving…" : submitLabel}</button>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
