const axios = require('axios');
const cheerio = require('cheerio');

const DEFAULT_USER_AGENT =
  'Mozilla/5.0 (compatible; scrape-cli/0.1; +https://github.com/myoneda22/job)';

function parseSelector(spec) {
  const eq = spec.indexOf('=');
  if (eq === -1) {
    throw new Error(`Invalid selector "${spec}". Expected form: field=selector[@attr]`);
  }
  const field = spec.slice(0, eq).trim();
  const rest = spec.slice(eq + 1).trim();
  if (!field) throw new Error(`Selector "${spec}" is missing a field name.`);
  if (!rest) throw new Error(`Selector "${spec}" is missing a CSS selector.`);

  const at = rest.lastIndexOf('@');
  if (at !== -1 && at < rest.length - 1) {
    return { field, selector: rest.slice(0, at).trim(), attr: rest.slice(at + 1).trim() };
  }
  return { field, selector: rest, attr: null };
}

function extractValue($scope, { selector, attr }, $) {
  const root = $scope === $ ? $.root() : $scope;
  const matches = root.find ? root.find(selector) : $(selector, $scope);

  if (matches.length === 0) return null;

  const values = matches
    .map((_, el) => {
      const node = $(el);
      if (attr === 'html') return node.html();
      if (attr) return node.attr(attr) ?? null;
      return node.text().trim();
    })
    .get()
    .filter((v) => v !== null && v !== '');

  if (values.length === 0) return null;
  return values.length === 1 ? values[0] : values;
}

async function fetchHtml(url, { timeout = 15000, userAgent = DEFAULT_USER_AGENT, headers = {} } = {}) {
  const response = await axios.get(url, {
    timeout,
    responseType: 'text',
    transformResponse: [(data) => data],
    headers: { 'User-Agent': userAgent, Accept: 'text/html,*/*', ...headers },
    validateStatus: (s) => s >= 200 && s < 400,
    maxRedirects: 5,
  });
  return response.data;
}

function extract(html, { selectors = [], each = null } = {}) {
  const $ = cheerio.load(html);
  const parsed = selectors.map(parseSelector);

  if (each) {
    return $(each)
      .map((_, el) => {
        const node = $(el);
        const item = {};
        for (const sel of parsed) {
          item[sel.field] = extractValue(node, sel, $);
        }
        return item;
      })
      .get();
  }

  const result = {};
  for (const sel of parsed) {
    result[sel.field] = extractValue($.root(), sel, $);
  }
  return result;
}

async function scrape(url, options = {}) {
  const html = await fetchHtml(url, options);
  return extract(html, options);
}

module.exports = { scrape, extract, fetchHtml, parseSelector };
