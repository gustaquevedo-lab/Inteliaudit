import fs from 'fs';
import path from 'path';

const src = path.resolve('../landing');
const dest = path.resolve('dist/landing');

if (!fs.existsSync(dest)) {
  fs.mkdirSync(dest, { recursive: true });
}

const files = fs.readdirSync(src);
for (const file of files) {
  if (file.endsWith('.html')) {
    fs.copyFileSync(path.join(src, file), path.join(dest, file));
  }
}
console.log('Landing pages copied to dist/landing');