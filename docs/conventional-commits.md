# Conventional Commit Messages

See how a minor change to your commit message style can make a difference.

```
git commit -m"<type>(<optional scope>): <description>" \
  -m"<optional body>" \
  -m"<optional footer>"
```

> **Note:** This cheatsheet is opinionated but does not violate the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Commit Message Formats

### General Commit

```
<type>(<optional scope>): <description>

<optional body>

<optional footer>
```

### Initial Commit

```
chore: init
```

### Merge Commit

```
Merge branch '<branch name>'
```

### Revert Commit

```
Revert "<reverted commit subject line>"
```

## Types

**Changes relevant to the API or functionality:**

- `feat` — Commits that add or adjust a feature
- `fix` — Commits that fix a bug

**Internal changes:**

- `refactor` — Rewrite or restructure code without changing behavior
- `perf` — Special `refactor` that improves performance
- `style` — Code style changes (whitespace, formatting) without behavior change
- `test` — Add missing tests or correct existing ones
- `docs` — Documentation only changes
- `build` — Build system, dependencies, CI/CD changes
- `ci` — CI configuration changes
- `chore` — Miscellaneous (e.g., `.gitignore`)

## Scopes

The `scope` provides additional context. It's **optional** but encouraged.

**OpenMCP scopes:**

- `server` — Server implementation
- `client` — Client implementation
- `tools` — Tool handling
- `resources` — Resource handling
- `prompts` — Prompt handling
- `types` — Type definitions
- `transports` — Transport layer
- `context` — Context management
- `auth` — Authorization

**Do not** use issue identifiers as scopes.

## Breaking Changes

Breaking changes **must** be indicated by `!` before the `:`:

```
feat(server)!: remove deprecated handler API
```

Or include a footer:

```
feat(server): new handler registration

BREAKING CHANGE: Old `register_handler()` method removed. Use decorators instead.
```

## Description

The `description` is a concise summary:

- **Mandatory**
- Use imperative, present tense: "add" not "added" or "adds"
- Think: "This commit will... add email notifications"
- **Do not** capitalize the first letter
- **Do not** end with a period

## Body

The `body` explains motivation and contrasts with previous behavior:

- **Optional**
- Use imperative, present tense
- Include context that helps reviewers

## Footer

The `footer` contains references and breaking change details:

- **Optional** (except for breaking changes)
- Reference issues: `Closes #123`, `Fixes #456`
- Breaking changes **must** start with `BREAKING CHANGE:`

## Versioning Impact

Your commits determine the next version:

| Commit Type | Version Bump |
|-------------|--------------|
| `feat` | Minor (0.X.0) |
| `fix` | Patch (0.0.X) |
| `perf` | Patch (0.0.X) |
| Breaking change (`!`) | Major (X.0.0) |
| Others | No release |

## Examples

```
feat: add email notifications on new messages
```

```
feat(tools): add progress reporting callback

Allows long-running tools to report incremental progress.

Closes #42
```

```
feat(server)!: require Python 3.9+

BREAKING CHANGE: Python 3.8 is no longer supported due to
typing syntax requirements.
```

```
fix(client): prevent connection leak on timeout

The connection was not being closed when a timeout occurred,
leading to resource exhaustion under load.
```

```
fix: add missing parameter validation

The error occurred because inputs weren't validated
before processing.
```

```
perf(resources): reduce memory usage with streaming

Use generators instead of loading full resources into memory.
```

```
refactor: simplify tool registration logic
```

```
docs: add examples for resource templates
```

```
build: update dependencies
```

## Fixing Non-Conventional Commits

If you've made commits that don't follow the convention:

```bash
# Interactive rebase to edit commit messages
git rebase -i HEAD~<number-of-commits>

# Change 'pick' to 'reword' for commits to fix
# Save and edit each message to follow the convention
```

For squash-merge PRs (our default), only the **PR title** needs to follow the convention—maintainers ensure it's correct before merging.

## References

- https://www.conventionalcommits.org/
- https://github.com/googleapis/release-please
