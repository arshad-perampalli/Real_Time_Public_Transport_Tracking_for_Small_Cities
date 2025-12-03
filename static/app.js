const map = L.map('map').setView([37.7749, -122.4194], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap'
}).addTo(map);

const markers = {};
let currentRoutePolyline = null;
let routes = [];

async function fetchRoutes(){
  try{
    const res = await fetch('/api/routes');
    routes = await res.json();
    const sel = document.getElementById('routeSelect');
    sel.innerHTML = '<option value="">(all)</option>';
    routes.forEach(r=>{
      const opt = document.createElement('option');
      opt.value = r.id; opt.textContent = r.name;
      sel.appendChild(opt);
    });
  }catch(e){console.error(e)}
}

function drawRouteById(id){
  if(currentRoutePolyline){map.removeLayer(currentRoutePolyline); currentRoutePolyline=null}
  if(!id) return;
  const r = routes.find(x=>x.id===id);
  if(!r) return;
  const latlngs = r.coords.map(c=>[c[0],c[1]]);
  currentRoutePolyline = L.polyline(latlngs,{color:'blue'}).addTo(map);
  map.fitBounds(currentRoutePolyline.getBounds(),{padding:[20,20]});
}

function renderList(vehicles){
  const list = document.getElementById('vehicleList');
  list.innerHTML = '';
  vehicles.forEach(v=>{
    const id = v.device_id || 'unknown';
    const lat = parseFloat(v.latitude);
    const lon = parseFloat(v.longitude);
    const li = document.createElement('li');
    if(Number.isFinite(lat) && Number.isFinite(lon)){
      li.textContent = `${id} — ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
    } else {
      li.textContent = `${id} — (no fix)`;
    }
    list.appendChild(li);
  });
}

function updateMarkers(vehicles){
  vehicles.forEach(v=>{
    const id = v.device_id || 'unknown';
    const lat = parseFloat(v.latitude);
    const lon = parseFloat(v.longitude);
    if(Number.isFinite(lat) && Number.isFinite(lon)){
      if(!markers[id]){
        markers[id] = L.marker([lat,lon]).addTo(map).bindPopup(id);
      } else {
        markers[id].setLatLng([lat,lon]);
      }
    }
  });
}

async function fetchVehicles(){
  try{
    const res = await fetch('/api/vehicles');
    const vehicles = await res.json();
    renderList(vehicles);
    updateMarkers(vehicles);
  }catch(e){console.error(e)}
}

function initSSE(){
  try {
    const es = new EventSource('/api/stream');
    es.onmessage = (evt)=>{
      try {
        const changed = JSON.parse(evt.data);
        // Refresh entire list after changes; could optimize later
        fetchVehicles();
        updateMarkers(changed);
      } catch(err){ console.error(err); }
    };
    es.onerror = ()=>{
      console.warn('SSE error; falling back to polling');
      es.close();
      startPolling();
    };
  } catch(e){
    console.warn('SSE init failed, fallback to polling');
    startPolling();
  }
}

let pollingHandle = null;
function startPolling(){
  if(pollingHandle) return;
  pollingHandle = setInterval(fetchVehicles, 3000);
}

document.getElementById('routeSelect').addEventListener('change', (e)=>{
  drawRouteById(e.target.value);
});
document.getElementById('refreshBtn').addEventListener('click', ()=>{fetchVehicles();});

// init
fetchRoutes().then(()=>{fetchVehicles(); initSSE();});
