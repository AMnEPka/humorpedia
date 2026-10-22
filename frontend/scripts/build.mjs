import { ESLint } from 'eslint';
import { build, resolveConfig } from 'vite';
import { writeHtmlRelease } from './html-release.mjs';

const eslint = new ESLint();
const results = await eslint.lintFiles(['src']);
const report = (await eslint.loadFormatter('stylish')).format(results);
if (report) process.stdout.write(report);
const errors = results.reduce((sum, result) => sum + result.errorCount, 0);
const warnings = results.reduce((sum, result) => sum + result.warningCount, 0);
if (errors || (process.env.CI && process.env.CI !== 'false' && warnings)) {
  throw new Error('Frontend lint failed: ' + errors + ' errors, ' + warnings + ' warnings');
}
await build();

const config = await resolveConfig({}, 'build');
await writeHtmlRelease(config.build.outDir);
