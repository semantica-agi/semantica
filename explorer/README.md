# Semantica Knowledge Explorer

A real-time visual interface for exploring knowledge graphs, decision intelligence, entity resolution, ontologies, and graph analytics built on top of the [Semantica](https://github.com/Hawksight-AI/semantica) library.

---

## Requirements

| Dependency | Minimum version |
|---|---|
| Python | 3.8+ |
| Node.js | 18.x or higher (20.x recommended) |
| npm | 9.x or higher |

Check your versions:

```bash
node --version
npm --version
python --version
```

---

## Quick Start (Local Development)

### 1. Clone the repository

```bash
git clone https://github.com/Hawksight-AI/semantica.git
cd semantica
```

### 2. Install the Semantica Python package

```bash
pip install semantica
```

Or install from source if you already have the repo:

```bash
pip install -e .
```

### 3. Start the Knowledge Explorer backend

The backend serves the REST API (`/api/*`) and WebSocket (`/ws`) endpoints. It requires a graph JSON file to load on startup.

```bash
# From the repo root
python -m semantica.explorer --graph path/to/your_graph.json
```

The server starts on **http://127.0.0.1:8000** by default. Keep this terminal open.

**CLI options:**

| Flag | Default | Description |
|---|---|---|
| `--graph` / `-g` | *(required)* | Path to the graph JSON file to load |
| `--port` / `-p` | `8000` | Port to bind the backend on |
| `--host` | `127.0.0.1` | Host to bind the backend on |
| `--no-browser` | off | Skip auto-opening the browser |

**Example with a custom port:**

```bash
python -m semantica.explorer --graph my_graph.json --port 8080 --no-browser
```

> If you use a custom port, update `server.proxy` in [vite.config.ts](vite.config.ts) to match.

### 4. Install frontend dependencies

Open a second terminal:

```bash
cd explorer
npm install
```

> This project uses Vite 6 and requires **Node 18+**. If you are on Node 16 or earlier, upgrade first.

### 5. Start the dev server

```bash
npm run dev
```

Vite starts on **http://localhost:5173** by default. Open that URL in your browser.

---

## Graph file format

The Explorer accepts a JSON file with the following shape:

```json
{
  "entities": [
    { "id": "node_1", "type": "person", "text": "Alice", "metadata": {} }
  ],
  "relationships": [
    {
      "id": "r1",
      "source": "node_1",
      "target": "node_2",
      "type": "knows",
      "weight": 1.0,
      "metadata": {}
    }
  ]
}
```

The `metadata` fields and `weight` are optional. Node `type` drives the colour scheme and provenance classification in the UI.

---

## What you should see

The Explorer opens with a persistent left sidebar and workspace tabs:

| Workspace | What it shows |
|---|---|
| **Graph Studio** | Interactive Sigma.js canvas — nodes, edges, zoom, ForceAtlas2 layout, path tracing, provenance download |
| **Timeline** | Temporal event scrubber — drag to see the graph state at any point in time |
| **Decisions** | Causal chain viewer with outcome badges, confidence scores, and decision filter |
| **Enrich** | Link prediction, entity deduplication, and semantic enrichment tools |
| **KG Overview** | Aggregate stats, community breakdown, centrality heatmap |
| **Vocabulary** | SKOS/OWL vocabulary hierarchy browser and RDF import |
| **Ontology** | Auto-generated schema summary and OWL class browser |
| **Registry** | Live audit log of every graph mutation (add-node, add-edge, merge, delete) |

---

## Project structure

```
explorer/
├── src/
│   ├── App.tsx                          # Root layout, tab routing, workspace wiring
│   ├── index.css                        # Global resets, fonts, keyframe animations
│   ├── store/
│   │   └── registryStore.ts             # Pub/sub audit registry (no external state lib)
│   └── workspaces/
│       ├── GraphWorkspace/              # Sigma.js graph canvas + inspector panel
│       ├── DecisionWorkspace/           # Causal flow diagram + decision list
│       ├── TimelineWorkspace/           # vis-timeline temporal scrubber
│       ├── VocabularyWorkspace/         # SKOS hierarchy browser + RDF import
│       ├── ManageWorkspace/             # Registry, KG Overview, Ontology tabs
│       └── EnrichWorkspace/             # Entity resolution, dedup, link prediction
├── index.html
├── vite.config.ts                       # Dev proxy → 127.0.0.1:8000, build → ../semantica/static
└── package.json
```

---

## Available scripts

Run these from inside the `explorer/` directory:

```bash
# Start the dev server with hot module replacement
npm run dev

# Type-check and build a production bundle into ../semantica/static
npm run build

# Preview the production build locally
npm run preview

# Run ESLint over all source files
npm run lint
```

---

## API & WebSocket proxy

During development, Vite forwards requests automatically — no CORS configuration needed:

| Pattern | Forwarded to |
|---|---|
| `/api/*` | `http://127.0.0.1:8000/api/*` |
| `/ws` | `ws://127.0.0.1:8000/ws` |

If you run the backend on a different port, update `server.proxy` in [vite.config.ts](vite.config.ts):

```typescript
server: {
  proxy: {
    '/api': { target: 'http://127.0.0.1:<YOUR_PORT>', changeOrigin: true },
    '/ws':  { target: 'ws://127.0.0.1:<YOUR_PORT>', ws: true },
  },
},
```

---

## Production build

```bash
cd explorer
npm run build
```

The compiled assets are written to `../semantica/static/`. The Semantica Python server serves this folder automatically at its root URL — no separate web server needed.

---

## Troubleshooting

**Blank graph / no data loads**
- Make sure `python -m semantica.explorer --graph your_file.json` is running before opening the UI.
- Check the browser console for failed `/api/graph` requests — the backend may not be running or the proxy port may not match.

**`npm install` fails or hangs**
- Ensure you are using **Node 18 or 20**. Node 16 and Vite 6 are incompatible.
- Delete `node_modules/` and `package-lock.json`, then re-run `npm install`.

**Port 5173 already in use**
- Vite will automatically try the next available port and print it in the terminal. Use that URL instead.

**Port 8000 already in use**
- Start the backend on a different port: `python -m semantica.explorer --graph file.json --port 8080`
- Then update the proxy in `vite.config.ts` to match.

**WebSocket not connecting (real-time mutations not appearing)**
- Confirm the backend is running and the `/ws` proxy target in `vite.config.ts` points to the correct port.
- Check browser DevTools → Network → WS tab for the connection status.

---

## Tech stack

- **React 19** + TypeScript
- **Vite 6** with `babel-plugin-react-compiler`
- **Sigma.js 3** + **Graphology** — graph rendering and in-memory graph store
- **ForceAtlas2** — physics-based layout worker
- **@tanstack/react-query** — data fetching for ontology and vocabulary tabs
- **vis-timeline** — temporal event visualization
- **lucide-react** — icon set

---

## Contributing

See the root [CONTRIBUTING.md](../CONTRIBUTING.md) and open issues on the main [Semantica repository](https://github.com/Hawksight-AI/semantica).
