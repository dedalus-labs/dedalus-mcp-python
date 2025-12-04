# Contributing to Dedalus MCP

Thanks for your interest in contributing! This guide will help you get started.

## Your First Pull Request

Never made a PR before? Welcome! Here's how to contribute step-by-step.

### 1. Fork the repository

Click the **Fork** button on the [Dedalus MCP repo](https://github.com/dedalus-labs/openmcp-python). This creates your own copy.

### 2. Clone your fork

```bash
git clone https://github.com/YOUR-USERNAME/openmcp-python.git
cd openmcp-python
```

### 3. Set up the project

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### 4. Create a branch

```bash
git checkout -b fix/my-first-contribution
```

Pick a name that describes your change: `fix/typo-in-readme`, `feat/add-timeout-option`, `docs/clarify-setup`.

### 5. Make your changes

Edit the code, then run the checks:

```bash
uv run ruff check .        # Lint
uv run ruff format .       # Format
uv run pytest              # Test
```

### 6. Commit with a conventional message

```bash
git add .
git commit -m "fix: correct typo in error message"
```

The commit type (`fix:`, `feat:`, `docs:`) matters—it determines the version bump. See [conventional commits](docs/conventional-commits.md).

### 7. Push to your fork

```bash
git push origin fix/my-first-contribution
```

### 8. Open a Pull Request

Go to your fork on GitHub. You'll see a banner to **Compare & pull request**. Click it!

- **Base repository**: `dedalus-labs/openmcp-python`, branch `main`
- **Head repository**: your fork, your branch
- Write a clear title (this becomes the commit message when we merge)
- Describe what you changed and why

### 9. Wait for review

CI will run automatically. A maintainer will review your PR and may suggest changes. Don't worry—this is normal and collaborative!

### 🎉 Congratulations!

Once merged, you're officially a contributor. Your name appears in the git history, and if your change is a `feat:` or `fix:`, it'll be in the next release changelog. Thank you for contributing!

---

## Trunk-Based Development

All development happens on `main`. There's no `dev` or `staging` branch—PRs go directly to `main`.

**Tips:**

- **Short-lived branches**: Aim to merge within days, not weeks. Long-lived branches accumulate merge conflicts.
- **Small PRs are better**: Easier to review, faster to merge, lower risk.
- **Work-in-progress is fine**: Use feature flags or don't expose unfinished work in the public API.
- **`main` is always shippable**: Don't merge broken code. If something slips through, we revert quickly.

See [RELEASE.md](RELEASE.md) for how your commits become releases.

## Code Standards

```bash
uv run ruff check .           # Lint
uv run ruff format --check .  # Format check
uv run mypy src/openmcp       # Type check
uv run pytest                 # Test
```

All must pass. See the [style guide](docs/style/README.md).

## AI Disclosure

If you use AI tools (Copilot, Claude, Cursor), mention it in your PR. You must understand code you submit.

## Adding Support for New MCP Versions

When a new MCP protocol version is released, Dedalus MCP must be updated. Contributors can help by:

1. **Update `FEATURE_REGISTRY`** in `src/openmcp/versioning.py`
2. **Add version tests** in `tests/protocol_versions/{version}/`
3. **Copy the schema** to `tests/protocol_versions/{version}/schema.json`

See [versioning.md](docs/openmcp/versioning.md) for details.

## Links

| Resource | Description |
|----------|-------------|
| [RELEASE.md](RELEASE.md) | How releases work |
| [Style Guide](docs/style/README.md) | Python conventions |
| [Conventional Commits](docs/conventional-commits.md) | Commit message format |
| [GLOSSARY.md](GLOSSARY.md) | MCP terminology |
| [SECURITY.md](SECURITY.md) | Reporting vulnerabilities |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
