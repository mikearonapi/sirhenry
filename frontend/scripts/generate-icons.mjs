#!/usr/bin/env node
/**
 * Generate all app icon sizes from the master SVG.
 *
 * Usage:  node frontend/scripts/generate-icons.mjs
 *
 * Outputs PNG files for:
 *   - Favicon (16, 32, 48)
 *   - Apple Touch Icon (180)
 *   - Android/PWA (192, 512)
 *   - App Store / Marketing (1024)
 */

import sharp from "sharp";
import { readFileSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(__dirname, "..");
const svgPath = resolve(frontendDir, "public/henry-icon.svg");
const svgBuffer = readFileSync(svgPath);

const sizes = [
  { size: 16, output: "public/favicon-16x16.png" },
  { size: 32, output: "public/favicon-32x32.png" },
  { size: 48, output: "public/favicon-48x48.png" },
  { size: 180, output: "app/apple-icon.png" },
  { size: 192, output: "public/icon-192x192.png" },
  { size: 512, output: "public/icon-512x512.png" },
  { size: 1024, output: "public/henry-icon-1024.png" },
];

async function generate() {
  console.log("Generating icons from henry-icon.svg...\n");
  for (const { size, output } of sizes) {
    const outPath = resolve(frontendDir, output);
    mkdirSync(dirname(outPath), { recursive: true });
    await sharp(svgBuffer, { density: 300 })
      .resize(size, size)
      .png()
      .toFile(outPath);
    console.log(`  ${size}x${size} → ${output}`);
  }
  console.log("\nDone! All icon files generated.");
}

generate().catch((err) => {
  console.error("Error generating icons:", err);
  process.exit(1);
});
