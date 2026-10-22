import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
export function renderGatewayConfigs({releaseId, backendOrigin}) {
  if (!/^[a-f0-9]{64}$/.test(releaseId)) throw new Error('Invalid release ID');
  if (!/^http:\/\/[a-zA-Z0-9][a-zA-Z0-9.-]*:[0-9]{1,5}$/.test(backendOrigin) || Number(backendOrigin.split(':').at(-1)) > 65535 || Number(backendOrigin.split(':').at(-1)) === 0) throw new Error('Invalid fixed backend origin');
  function render(enabled,indexing) {
    const closed=enabled&&!indexing;
    const headers=cache=>`add_header Cache-Control "${cache}" always;
      add_header X-Content-Type-Options nosniff always;
      add_header Referrer-Policy same-origin always;
      ${closed?'add_header X-Robots-Tag "noindex,follow" always;':''}`;
    const proxy=`proxy_set_header Host $http_host;
      proxy_set_header X-Forwarded-For $remote_addr;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_set_header X-Humorpedia-Release "${releaseId}";
      proxy_set_header X-Humorpedia-Original-URI $request_uri;
      proxy_read_timeout 120s;
      proxy_intercept_errors off;`;
    return `server {
    listen 80;
    server_name _;
    server_tokens off;
    root /usr/share/nginx/html;
    index index.html;
    client_max_body_size 20m;
    ${headers('no-cache')}
    location = /config.js { ${headers('no-store')} try_files $uri =404; }
    location = /public-html-release.json { return 404; }
    location ~* ^/_internal(/|$) { return 404; }
    location = /api/page-packages/preview {
      client_max_body_size 52m; ${proxy} proxy_pass ${backendOrigin};
    }
    location ~* ^/(api|media|images|uploads)(/|$) {
      ${proxy} proxy_pass ${backendOrigin};
    }
    location = /healthz { default_type application/json; return 200 '{"status":"ok"}'; }
    ${enabled ? `location ~ ^/(people|articles)/[^/]+/?$ {
      ${headers('no-store')} ${proxy} proxy_pass ${backendOrigin};
    }
    location = /robots.txt { ${headers('no-store')} ${proxy} proxy_pass ${backendOrigin}; }
    location = /sitemap.xml { ${headers('no-store')} ${proxy} proxy_pass ${backendOrigin}; }
    location ~* ^/(admin|preview)(/|$) { ${headers('no-cache')} try_files $uri /index.html; }
    location ^~ /assets/ { ${headers('public, max-age=31536000, immutable')} try_files $uri =404; }
    location ~* \\.(js|css|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|map|json|txt|xml)$ { ${headers('no-cache')} try_files $uri =404; }
    location / { ${headers('no-cache')} try_files $uri $uri/ @legacy; }
    location @legacy {
      ${headers('no-store')}
      proxy_set_header Host $http_host;
      proxy_set_header X-Forwarded-For $remote_addr;
      proxy_set_header X-Humorpedia-Release "${releaseId}";
      proxy_set_header X-Humorpedia-Original-URI $request_uri;
      proxy_intercept_errors on;
      error_page 418 = @spa;
      rewrite ^ /_internal/public-html/dispatch break;
      proxy_pass ${backendOrigin};
    }
    location @spa { ${headers('no-cache')} try_files /index.html =404; }`
      : 'location / { try_files $uri $uri/ /index.html; }'}
}\n`;
  }
  return {disabled:render(false,false),enabled_noindex:render(true,false),enabled_index:render(true,true)};
}
export async function writeGatewayBundle(buildDir,outputDir,{backendOrigin}) {
  const manifest=JSON.parse(await readFile(path.join(buildDir,'public-html-release.json'),'utf8'));
  const variants=renderGatewayConfigs({releaseId:manifest.release_id,backendOrigin});
  await mkdir(outputDir,{recursive:true});
  await cp(buildDir,path.join(outputDir,'build'),{recursive:true,errorOnExist:true,force:false});
  const configs=path.join(outputDir,'gateway-configs');
  await mkdir(configs);
  for (const [mode,config] of Object.entries(variants)) {
    await writeFile(path.join(configs,mode+'.conf'),config);
    await writeFile(path.join(configs,mode+'.js'),'window.__PUBLIC_HTML_ENABLED__ = '+(mode!=='disabled')+';\nwindow.__BACKEND_URL__ = window.location.origin;\n');
  }
  await writeFile(path.join(configs,'release.env'),"HTML_RELEASE_ID='"+manifest.release_id+"'\nHTML_BACKEND_ORIGIN='"+backendOrigin+"'\n");
}