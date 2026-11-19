import L from "leaflet";

export const CATEGORIES = {
  hospital: { label: "Hospital", emoji: "🏥", color: "#e11d48" },
  school: { label: "School", emoji: "🏫", color: "#2563eb" },
  restaurant: { label: "Restaurant", emoji: "🍽️", color: "#f59e0b" },
  shop: { label: "Shop", emoji: "🛍️", color: "#16a34a" },
};

// Marker icons are cached so 10,000 markers don't create 10,000 icon objects.
const cache = {};
export function iconFor(category, highlighted = false) {
  const key = `${category}-${highlighted}`;
  if (!cache[key]) {
    const c = CATEGORIES[category] || { emoji: "📍", color: "#6b7280" };
    cache[key] = L.divIcon({
      className: "pin-wrap",
      html: `<div class="pin ${highlighted ? "hl" : ""}" style="background:${c.color}">${c.emoji}</div>`,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });
  }
  return cache[key];
}
