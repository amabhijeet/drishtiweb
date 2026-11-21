const fs = require('node:fs');
for (const name of ['leaflet', 'leaflet.markercluster']) {
  fs.mkdirSync('static/vendor', {recursive:true});
  fs.cpSync('node_modules/'+name+'/dist', 'static/vendor/'+name, {recursive:true});
}
