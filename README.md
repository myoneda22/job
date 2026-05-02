# scrape-cli

A small generic web scraper CLI built on `axios` + `cheerio`.

## Install

```bash
npm install
```

## Usage

```
scrape <url> --select field=selector[@attr] [--select ...] [--each <selector>]
```

- `--select field=selector` extracts the text content of matched elements.
- `--select field=selector@attr` extracts an attribute (e.g. `link=a@href`). Use `@html` for inner HTML.
- `--each <selector>` iterates over matching elements and extracts the `--select` fields for each one, returning an array of objects.
- If a selector matches multiple elements (without `--each`), the field is returned as an array.

### Examples

Single page, top-level fields:

```bash
node src/index.js https://example.com \
  --select title=title \
  --select heading=h1 \
  --pretty
```

List of items, one object per match:

```bash
node src/index.js https://news.ycombinator.com \
  --each "tr.athing" \
  --select title=".titleline > a" \
  --select link=".titleline > a@href" \
  --pretty
```

### Programmatic use

```js
const { scrape, extract, fetchHtml } = require('./src/scraper');

const data = await scrape('https://example.com', {
  selectors: ['title=title', 'heading=h1'],
});
```

## Test

```bash
npm test
```
