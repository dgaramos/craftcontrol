import fs from "node:fs";
import path from "node:path";

const [projectDirectory, dataDirectory, worldName] = process.argv.slice(2);
if (!projectDirectory || !dataDirectory || !worldName) {
  throw new Error("usage: node install.mjs PROJECT_DIRECTORY DATA_DIRECTORY WORLD_NAME");
}
const source = path.join(projectDirectory, "behavior_pack");
const destination = path.join(dataDirectory, "behavior_packs", "craftcontrol-telemetry");
const legacyDestination = path.join(dataDirectory, "behavior_packs", "minecraft-bedrock-telemetry");
const worldFile = path.join(dataDirectory, "worlds", worldName, "world_behavior_packs.json");
const manifestPath = path.join(source, "manifest.json");
if (!fs.existsSync(manifestPath)) throw new Error(`pack not found: ${source}`);
if (!fs.existsSync(path.dirname(worldFile))) throw new Error(`world not found: ${path.dirname(worldFile)}`);
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const packId = manifest?.header?.uuid;
const packVersion = manifest?.header?.version;
if (packId !== "8c916948-76c6-4aa5-91e0-97671dfd3830") throw new Error("unexpected telemetry pack UUID");
if (!Array.isArray(packVersion) || packVersion.length !== 3 || !packVersion.every(Number.isInteger)) throw new Error("invalid telemetry pack version");

fs.mkdirSync(destination, { recursive: true });
fs.cpSync(source, destination, { recursive: true, force: true });
for (const entry of fs.readdirSync(destination, { recursive: true, withFileTypes: true })) {
  const entryPath = path.join(entry.parentPath || entry.path, entry.name);
  fs.chmodSync(entryPath, entry.isDirectory() ? 0o755 : 0o644);
}
fs.chmodSync(destination, 0o755);
const packs = fs.existsSync(worldFile) ? JSON.parse(fs.readFileSync(worldFile, "utf8")) : [];
const backup = `${worldFile}.backup-${new Date().toISOString().replaceAll(":", "-")}`;
if (fs.existsSync(worldFile)) fs.copyFileSync(worldFile, backup);
const entry = { pack_id: packId, version: packVersion };
const updated = packs.filter((pack) => pack.pack_id !== entry.pack_id);
updated.push(entry);
fs.writeFileSync(worldFile, `${JSON.stringify(updated, null, 2)}\n`, "utf8");
if (legacyDestination !== destination && fs.existsSync(legacyDestination)) fs.rmSync(legacyDestination, { recursive: true, force: true });
console.log(`Installed pack at ${destination}`);
console.log(`Updated ${worldFile}`);
if (fs.existsSync(backup)) console.log(`Backup: ${backup}`);
