/**
 * Generates placeholder PWA icons (theme color #3D2E28) into public/icons/.
 * Run from frontend: npm run generate-pwa-icons (requires: npm install pngjs --save-dev)
 */
const fs = require("fs");
const path = require("path");

let PNG;
try {
  PNG = require("pngjs").PNG;
} catch (e) {
  console.error("Missing dependency. Run: npm install pngjs --save-dev");
  process.exit(1);
}

const SIZES = [72, 96, 128, 144, 152, 192, 384, 512];
const THEME_RGB = { r: 0x3d, g: 0x2e, b: 0x28 }; // #3D2E28 from manifest

const outDir = path.join(__dirname, "..", "public", "icons");
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

for (const size of SIZES) {
  const png = new PNG({ width: size, height: size, filterType: -1 });
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (size * y + x) << 2;
      png.data[idx] = THEME_RGB.r;
      png.data[idx + 1] = THEME_RGB.g;
      png.data[idx + 2] = THEME_RGB.b;
      png.data[idx + 3] = 255;
    }
  }
  const outPath = path.join(outDir, `icon-${size}x${size}.png`);
  png.pack().pipe(fs.createWriteStream(outPath));
  console.log("Written", outPath);
}

console.log("Done. Replace these with your app logo if desired.");
