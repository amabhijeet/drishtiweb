const list = document.querySelector('#list');
const search = document.querySelector('#search');
let refresh = () => {};
search?.addEventListener('input', () => {
  const q = search.value.toLowerCase();
  for (const row of list.querySelectorAll('article, tbody tr')) row.hidden = !row.textContent.toLowerCase().includes(q);
  refresh(q);
});
const canvas = document.querySelector('#map');
if (canvas && window.L) {
  const map = L.map(canvas).setView([24,82], 5);
  L.tileLayer(canvas.dataset.tiles || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    // OSM requires a referrer. Send only the site origin on tile requests.
    referrerPolicy: 'strict-origin',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  }).addTo(map);
  const markers = document.querySelector('#markers');
  if (markers) {
    const rows = JSON.parse(markers.textContent);
    const group = L.markerClusterGroup ? L.markerClusterGroup() : L.featureGroup();
    group.addTo(map);
    refresh = (q='') => {
      group.clearLayers();
      for (const r of rows.filter(r => Object.values(r).join(' ').toLowerCase().includes(q))) {
        const link = document.createElement('a');
        link.href = '/reports/'+encodeURIComponent(r.id);
        link.textContent = r.title+' · View report and gallery';
        L.marker([r.lat,r.lon]).bindPopup(link).addTo(group);
      }
      if (group.getLayers().length) map.fitBounds(group.getBounds(),{maxZoom:16,padding:[25,25]});
    };
    refresh();
  } else {
    const points = JSON.parse(document.querySelector('#track').textContent).map(p=>p.slice(0,2));
    if (points.length) {
      L.marker(points[0]).addTo(map);
      map.fitBounds(L.polyline(points).addTo(map).getBounds(),{maxZoom:17});
    }
  }
} else if (canvas) canvas.textContent = 'Map unavailable. Use the report list to view evidence.';
