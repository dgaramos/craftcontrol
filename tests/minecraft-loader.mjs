import { pathToFileURL } from "node:url";
import path from "node:path";

export async function resolve(specifier, context, nextResolve) {
  if (specifier === "@minecraft/server") {
    return { url: pathToFileURL(path.resolve("tests/minecraft-server.mock.js")).href, shortCircuit: true };
  }
  return nextResolve(specifier, context);
}
