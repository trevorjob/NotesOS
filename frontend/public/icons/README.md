# PWA Icons

Place PWA icons here for installability and home screen. The manifest expects:

- `icon-72x72.png` through `icon-512x512.png` (see `manifest.json`)

**Quick setup:** From the `frontend` folder run:

```bash
npm run generate-pwa-icons
```

This generates placeholder icons (solid theme color). Replace them with your app logo by editing `scripts/generate-pwa-icons.js` to use a source image, or add your own PNGs (72, 96, 128, 144, 152, 192, 384, 512) and name them as above.

**Alternative:** Use [PWA Asset Generator](https://www.pwabuilder.com/imageGenerator) with a 512×512 logo to generate all sizes.
