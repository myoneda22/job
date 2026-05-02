const { test } = require('node:test');
const assert = require('node:assert');
const { extract, parseSelector } = require('../src/scraper');

const HTML = `
<!doctype html>
<html>
  <head><title>Example</title></head>
  <body>
    <h1>Hello</h1>
    <ul class="items">
      <li class="item"><a href="/a">First</a><span class="price">$10</span></li>
      <li class="item"><a href="/b">Second</a><span class="price">$20</span></li>
    </ul>
  </body>
</html>
`;

test('parseSelector handles field=selector', () => {
  assert.deepStrictEqual(parseSelector('title=h1'), { field: 'title', selector: 'h1', attr: null });
});

test('parseSelector handles field=selector@attr', () => {
  assert.deepStrictEqual(parseSelector('link=a@href'), {
    field: 'link',
    selector: 'a',
    attr: 'href',
  });
});

test('parseSelector rejects malformed input', () => {
  assert.throws(() => parseSelector('nofield'));
  assert.throws(() => parseSelector('=h1'));
  assert.throws(() => parseSelector('field='));
});

test('extract returns a flat object for top-level selectors', () => {
  const result = extract(HTML, { selectors: ['title=title', 'heading=h1'] });
  assert.deepStrictEqual(result, { title: 'Example', heading: 'Hello' });
});

test('extract returns array values when multiple matches', () => {
  const result = extract(HTML, { selectors: ['prices=.price'] });
  assert.deepStrictEqual(result, { prices: ['$10', '$20'] });
});

test('extract reads attributes with @attr', () => {
  const result = extract(HTML, { selectors: ['hrefs=a@href'] });
  assert.deepStrictEqual(result, { hrefs: ['/a', '/b'] });
});

test('extract iterates with each', () => {
  const result = extract(HTML, {
    each: '.item',
    selectors: ['name=a', 'href=a@href', 'price=.price'],
  });
  assert.deepStrictEqual(result, [
    { name: 'First', href: '/a', price: '$10' },
    { name: 'Second', href: '/b', price: '$20' },
  ]);
});

test('extract returns null for missing selectors', () => {
  const result = extract(HTML, { selectors: ['missing=.nope'] });
  assert.deepStrictEqual(result, { missing: null });
});
