#!/usr/bin/env node
const { Command } = require('commander');
const { scrape } = require('./scraper');

const program = new Command();

program
  .name('scrape')
  .description('Fetch a URL and extract structured data with CSS selectors.')
  .argument('<url>', 'URL to fetch')
  .option(
    '-s, --select <field=selector[@attr]>',
    'extract a field; repeat for multiple. Use @attr for attributes (e.g. title=h1, link=a@href)',
    (value, prev) => prev.concat([value]),
    []
  )
  .option('-e, --each <selector>', 'iterate over matching elements and extract --select fields per item')
  .option('-t, --timeout <ms>', 'request timeout in milliseconds', (v) => parseInt(v, 10), 15000)
  .option('-u, --user-agent <ua>', 'custom User-Agent header')
  .option('--pretty', 'pretty-print JSON output', false)
  .action(async (url, opts) => {
    if (opts.select.length === 0) {
      console.error('Error: provide at least one --select field=selector');
      process.exit(2);
    }
    try {
      const data = await scrape(url, {
        selectors: opts.select,
        each: opts.each,
        timeout: opts.timeout,
        userAgent: opts.userAgent,
      });
      const json = opts.pretty ? JSON.stringify(data, null, 2) : JSON.stringify(data);
      process.stdout.write(json + '\n');
    } catch (err) {
      const msg = err.response
        ? `HTTP ${err.response.status} fetching ${url}`
        : err.message || String(err);
      console.error(`Error: ${msg}`);
      process.exit(1);
    }
  });

program.parseAsync(process.argv);
