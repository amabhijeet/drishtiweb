const fs = require('node:fs');
fs.cpSync('public-pages', 'public', {recursive:true});
for (const path of ['site.css','map.js','vendor/leaflet','vendor/leaflet.markercluster']) {
  fs.cpSync('static/'+path,'public/static/'+path,{recursive:true});
}
