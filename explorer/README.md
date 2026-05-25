# Semantica Knowledge Explorer

A real-time visual interface for exploring knowledge graphs, decision intelligence, entity resolution, ontologies, and graph analytics built on top of the [Semantica](https://github.com/Hawksight-AI/semantica) library.

---

## Requirements

| Dependency | Minimum Version |
|---|---|
| Node.js | 18.x or higher (20.x recommended) |
| npm | 9.x or higher |
| Python | 3.8+ |
| Semantica backend | running on `http://127.0.0.1:8000` |

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

Or install from source if you have the repo:

```bash
pip install -e .
```

### 3. Start the Semantica backend

The Explorer proxies all `/api` and `/ws` requests to `http://127.0.0.1:8000`. The backend must be running before you open the UI.

```bash
# From the repo root
python -m semantica.server
```

The backend starts on port **8000** by default. Keep this terminal open.

### 4. Install frontend dependencies

Open a second terminal:

```bash
cd explorer
npm install
```

> **Note:** This project uses Vite 5 and requires **Node 18+**. If you are on Node 16 or earlier, upgrade first.

### 5. Start the dev server

```bash
npm run dev
```

Vite starts on **http://localhost:5173** by default. Open that URL in your browser.

---

## What you should see

The Explorer opens with a persistent left sidebar and six workspace tabs:

| Tab | What it shows |
|---|---|
| **Knowledge Graph** | Interactive Sigma.js canvas — nodes, edges, zoom, ForceAtlas2 layout |
| **Timeline** | Temporal event scrubber over the graph |
| **Decisions** | Causal chain viewer with outcome badges and decision filter |
| **Registry** | Live audit log of every graph mutation (add-node, add-edge, etc.) |
| **Entity Resolution** | Duplicate detection and entity merge workflow |
| **KG Overview** | Aggregate stats, community breakdown, centrality heatmap |
| **Ontology** | SKOS/OWL vocabulary hierarchy and schema summary |

---

## Project structure

```
explorer/
├── src/
│   ├── App.tsx                        # Root layout, tab routing, workspace wiring
│   ├── index.css                      # Global resets, fonts, keyframe animations
│   ├── store/
│   │   └── registryStore.ts           # Pub/sub audit registry (no external state lib)
│   └── workspaces/
│       ├── GraphWorkspace/            # Sigma.js graph canvas + inspector panel
│       ├── DecisionWorkspace/         # Causal flow diagram + decision list
│       ├── TimelineWorkspace/         # vis-timeline temporal scrubber
│       ├── ManageWorkspace/           # Registry, KG Overview, Ontology tabs
│       └── EnrichWorkspace/           # Entity resolution tab
├── index.html
├── vite.config.ts                     # Dev proxy → 127.0.0.1:8000, build → ../semantica/static
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

# Run the graph store multi-edge unit tests
npm run test:graph-store
```

---

## API & WebSocket proxy

During development, Vite forwards requests automatically — no CORS configuration needed:

| Pattern | Forwarded to |
|---|---|
| `/api/*` | `http://127.0.0.1:8000/api/*` |
| `/ws` | `ws://127.0.0.1:8000/ws` |

If you run the backend on a different port, update `server.proxy` in [vite.config.ts](vite.config.ts).

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
- Make sure the Semantica backend is running (`python -m semantica.server`) before opening the UI.
- Check the browser console for failed `/api/graph` requests — the proxy target may need updating in `vite.config.ts`.

**`npm install` fails or hangs**
- Ensure you are using **Node 18 or 20**. Node 16 and Vite 5 are incompatible.
- Delete `node_modules/` and `package-lock.json`, then re-run `npm install`.

**Port 5173 already in use**
- Vite will automatically try the next available port and print it in the terminal. Use that URL instead.

**WebSocket not connecting (real-time mutations not appearing)**
- Confirm the backend exposes a `/ws` WebSocket endpoint.
- Check browser DevTools → Network → WS tab for the connection status.

---

## Tech stack

- **React 19** + TypeScript (strict `noUnusedLocals`)
- **Vite 5** with `babel-plugin-react-compiler`
- **Sigma.js 3** + **Graphology** — graph rendering and in-memory graph store
- **ForceAtlas2** — physics-based layout worker
- **@tanstack/react-query** — data fetching for ontology and vocab tabs
- **vis-timeline** — temporal event visualization
- **lucide-react** — icon set

---

## Contributing

See the root [CONTRIBUTING.md](../CONTRIBUTING.md) and open issues on the main [Semantica repository](https://github.com/Hawksight-AI/semantica).
