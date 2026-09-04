#!/usr/bin/env node
/**
 * Local dev server — serves the frontend statically and proxies /api/* to a
 * running CraftControl backend (local, homelab, or any reachable host).
 *
 * Configuration (env vars take precedence over CLI args):
 *   CRAFTCONTROL_BACKEND   Backend base URL   (default: http://localhost:8082)
 *   PORT                   Local listen port  (default: 3333)
 *
 * Usage:
 *   node scripts/dev-proxy.mjs [backend-url]
 *   npm run dev                              # uses .env if present
 *   CRAFTCONTROL_BACKEND=http://192.168.15.50:8082 npm run dev
 *
 * Copy .env.example → .env and fill in your backend URL; the server picks it
 * up automatically (no dotenv dependency needed — export vars in your shell or
 * use `local-env set CRAFTCONTROL_BACKEND <url>` from the dotfiles toolchain).
 */
import http from "http";
import https from "https";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const BACKEND = process.env.CRAFTCONTROL_BACKEND || process.argv[2] || "http://localhost:8082";
const PORT = parseInt(process.env.PORT || "3333", 10);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATIC_ROOT = path.resolve(__dirname, "../static");
const TEMPLATES_ROOT = path.resolve(__dirname, "../templates");

const MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".ico": "image/x-icon",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
};

function proxy(req, res) {
  const backendUrl = new URL(req.url, BACKEND);
  const options = {
    hostname: backendUrl.hostname,
    port: backendUrl.port || (backendUrl.protocol === "https:" ? 443 : 80),
    path: backendUrl.pathname + backendUrl.search,
    method: req.method,
    headers: { ...req.headers, host: backendUrl.host },
  };
  const proto = backendUrl.protocol === "https:" ? https : http;
  const upstream = proto.request(options, (upRes) => {
    res.writeHead(upRes.statusCode, upRes.headers);
    upRes.pipe(res);
  });
  upstream.on("error", (err) => {
    console.error("[proxy error]", err.message);
    res.writeHead(502);
    res.end("Bad Gateway");
  });
  req.pipe(upstream);
}

function serveStatic(req, res) {
  let urlPath = req.url.split("?")[0].replace(/^\/static\//, "/");
  // SPA fallback: non-asset paths → index.html
  const ext = path.extname(urlPath);
  const filePath = ext
    ? path.join(STATIC_ROOT, urlPath)
    : path.join(TEMPLATES_ROOT, "index.html");

  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (!ext) {
        fs.readFile(path.join(TEMPLATES_ROOT, "index.html"), (err2, d2) => {
          if (err2) { res.writeHead(404); res.end("Not found"); return; }
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(d2);
        });
      } else {
        res.writeHead(404);
        res.end("Not found");
      }
      return;
    }
    const mime = MIME[ext] || (filePath.endsWith(".html") ? "text/html" : "application/octet-stream");
    res.writeHead(200, { "Content-Type": mime });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith("/api/") || req.url === "/metrics") {
    proxy(req, res);
  } else {
    serveStatic(req, res);
  }
});

server.listen(PORT, () => {
  console.log(`Dev proxy running at http://localhost:${PORT}`);
  console.log(`  Static: ${STATIC_ROOT}`);
  console.log(`  Backend: ${BACKEND}`);
});
