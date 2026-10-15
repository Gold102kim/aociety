// A local acceptance artifact, not the full game or an externally released build.
const base = require('../package.json').build;
module.exports = {
  ...base,
  files: [...base.files, '!dist/models/**/*', 'dist/models/README.md', '!dist/.vite/**/*'],
  win: { ...base.win, artifactName: 'EchoVerse-Representative-local-${version}-${arch}.${ext}' },
};
