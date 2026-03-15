# Docs

The official documentation for Insight Flow lives in this directory.

## Structure

- `docs.json`: Mint site configuration
- `zh/`: Chinese-first documentation set
- `en/`: English mirror of the Chinese docs
- `plans/`: design and implementation notes for larger changes

The Mint site is organized into two top-level tabs:

- `Guides`
- `API Reference`

Chinese is listed first and acts as the source structure for the English mirror.

### Development

Install the [Mint CLI](https://www.npmjs.com/package/mint) to preview documentation changes locally:

```bash
npm i -g mint
```

Run the following command at the root of the documentation site (where `docs.json` is):

```bash
cd docs
mint dev
```

Run validation before claiming the docs are ready:

```bash
mint validate
mint broken-links
```
