import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const sourceDir = join(__dirname, "src");
const outputDir = join(__dirname, "dist");

const publicAppEnv = sanitizePublicEnv(process.env.NEXT_PUBLIC_APP_ENV, "dev");
const publicDashboardEnv = sanitizePublicEnv(
  process.env.NEXT_PUBLIC_DASHBOARD_ENV,
  "preview",
);

const htmlTemplate = await readFile(join(sourceDir, "index.html"), "utf8");
const html = htmlTemplate
  .replaceAll("{{NEXT_PUBLIC_APP_ENV}}", publicAppEnv)
  .replaceAll("{{NEXT_PUBLIC_DASHBOARD_ENV}}", publicDashboardEnv);
const css = await readFile(join(sourceDir, "styles.css"), "utf8");

await mkdir(outputDir, { recursive: true });
await writeFile(join(outputDir, "index.html"), html, "utf8");
await writeFile(join(outputDir, "styles.css"), css, "utf8");

function sanitizePublicEnv(value, fallback) {
  if (typeof value !== "string" || value.length === 0) {
    return fallback;
  }
  const trimmed = value.trim();
  if (!/^[A-Za-z0-9._-]{1,32}$/.test(trimmed)) {
    return "invalid";
  }
  return trimmed;
}
