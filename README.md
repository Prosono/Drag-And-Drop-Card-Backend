# Drag-And-Drop-Card Backend

Backend for the **Drag And Drop Card** — a Home Assistant integration that securely stores and serves drag‑and‑drop card configurations.

> Repo: `Prosono/Drag-And-Drop-Card-Backend` • License: MIT • Language: Python

---

## ✨ What it does

- Persists UI configurations for the companion **Drag And Drop Card**.
- Exposes a simple backend inside Home Assistant so the card can **save**, **load**, and **delete** its layouts/configs.
- Uses Home Assistant’s standards (config entries, services, storage helpers) so everything lives neatly within your HA setup.

---

## 📦 Installation

### Option A — HACS (recommended)

1. In Home Assistant, open **HACS → Integrations → 3‑dot menu → Custom repositories**.
2. Add the repository: `https://github.com/Prosono/Drag-And-Drop-Card-Backend` as type **Integration**.
3. Find **Drag-And-Drop-Card Backend** in HACS and click **Download**.
4. Go into "**Settings**" then "**Devices and Services**" And Click "**Add Integration**"
5. Search for "**Drag And Drop Card Backend**" and select it. 
4. Restart Home Assistant after the installation is complete.

### Option B — Manual

1. Copy the folder `custom_components/drag_and_drop_card_backend` from this repo
   into your Home Assistant config directory at:
   `config/custom_components/drag_and_drop_card_backend/`.
2. Restart Home Assistant.

> Your HA config directory is typically `~/.homeassistant` or `/config` (if using HA OS / Supervised).


---

## 🧰 Usage

The backend is designed to be used by the front-end **Drag And Drop Card**. Typical flows:

- **Save a layout** from the card → backend persists it.
- **Load a layout** on dashboard render → backend returns it.
- **Delete a layout** → backend removes it.

### Discovering services

The integration is designed so that you do not have to do any manual operations for saving / retreiving saved dashboards. 

## 📁 Files & Structure

```
custom_components/drag_and_drop_card_backend/
  ├── __init__.py
  ├── manifest.json
  ├── config_flow.py        # UI-based setup
  ├── services.yaml         # Service schemas (if present)
  ├── helpers/              # Storage / model helpers (if present)
  └── ...
```

> File list may vary by release, but the integration follows standard HA component conventions.

---

## 🧪 Development

### Local dev with HA

1. Create a Home Assistant dev instance (e.g., with HA Container or a test HA OS VM).
2. Mount/link the component to `/config/custom_components/drag_and_drop_card_backend`.
3. Enable **Advanced Mode** in your HA user profile for extra dev tools.
4. Watch the **Logs** (Settings → System → Logs) while reloading the integration.

### Linting / typing (suggested)

```bash
ruff check .
ruff format .
mypy custom_components/drag_and_drop_card_backend
```

### Versioning & releases

- Follow semantic versioning.
- Use GitHub Releases and update `manifest.json` version accordingly.

---

## 📝 FAQ

**Where are layouts stored?**  
Inside Home Assistant’s storage (e.g., `.storage`), handled by the integration. You normally don’t need to manage these files manually.

**Can I back up the data?**  
Yes — use HA’s built-in **Backups** (Snapshots) to capture everything.

**Do I need the front-end card?**  
This backend is meant to be paired with the Drag And Drop Card. On its own, it won’t render UI — it just stores and serves configs.

---

## 🔒 Privacy & Security

- Data is stored locally within your Home Assistant instance.
- No cloud sync is performed by the backend unless you add it yourself via HA add-ons or external automations.

---

## 📄 License

MIT © Prosono

---

## 🙌 Contributing

1. Fork the repo & create a feature branch.
2. Make your changes with docs/notes.
3. Open a pull request describing the change and testing steps.

---

## 🔗 Related

- Front-end card: *Drag And Drop Card* (pair this backend with the card component).
- This backend repo: https://github.com/Prosono/Drag-And-Drop-Card-Backend
