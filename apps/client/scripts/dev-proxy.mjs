#!/usr/bin/env node
/**
 * Local dev server: serves apps/client/static/ and proxies /api/* to a remote backend.
 *
 * Usage:
 *   node apps/client/scripts/dev-proxy.mjs [backend-url]
 *
 * Example (homelab):
 *   node apps/client/scripts/dev-proxy.mjs http://192.168.15.50:8080
 *
 * Serves on http://localhost:3333
 */
import http from "http";
import https from "https";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const BACKEND = process.argv[2] || "http://192.168.15.50:8080";
const PORT = parseInt(process.env.PORT || "3333", 10);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATIC_ROOT = path.resolve(__dirname, "../static");

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
  let urlPath = req.url.split("?")[0];
  // SPA fallback: non-asset paths → index.html
  const ext = path.extname(urlPath);
  const filePath = ext
    ? path.join(STATIC_ROOT, urlPath)
    : path.join(STATIC_ROOT, "index.html");

  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (!ext) {
        // try index.html at the requested path level
        fs.readFile(path.join(STATIC_ROOT, "index.html"), (err2, d2) => {
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
    const mime = MIME[ext] || "application/octet-stream";
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
