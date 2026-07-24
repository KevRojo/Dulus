# Security Policy

> Dulus takes security seriously. This document outlines our security practices, reporting procedures, and responsible disclosure policy.

---

## Supported Versions

| Version | Supported |
|---|---|
| Latest PyPI / GitHub release | :white_check_mark: Actively supported |
| Older releases | Upgrade recommended; fixes are not guaranteed to be backported |

---

## Security Model

### Permission System

Dulus operates with a tiered permission system:

| Mode | Behavior | Use Case |
|---|---|---|
| `auto` | Reads and known-safe shell commands run freely. Writes and unsafe shell commands prompt. | Daily development |
| `manual` | Strict interactive approval mode. | Sensitive environments |
| `plan` | Read-only analysis. Only plan file writable | Code review |
| `accept-all` | No prompts. | Trusted sandboxes and controlled automation only |

### API Key Protection

- API-key fields stored in `~/.dulus/config.json` are obfuscated with XOR + base64.
- Set `DULUS_SECRET` to replace the built-in compatibility key.
- Environment variable bridging does not overwrite variables that are already present.
- Secrets are redacted from configuration and diagnostic output where those paths are handled.
- Keys can be rotated with `/config <provider>_api_key=new_key`.

This storage format is **not cryptographic secret storage**. It prevents casual
plaintext disclosure but does not protect against an attacker who can read the
configuration and application source. Use operating-system permissions, full-disk
encryption, short-lived credentials, or a separate secret manager for stronger
protection.

### Safe Execution

- **Bash whitelist:** Safe commands (`ls`, `cat`, `grep`) auto-approve in `auto` mode
- **Mutation gate:** File writes and shell commands outside the safe-command set request approval unless `accept-all` is active
- **Plan mode:** Blocks mutating tools while preserving a writable plan artifact
- **Auditability:** Tool requests and results remain visible in the active session
- **Worktree isolation:** Sub-agents can work in separate git worktrees to reduce accidental overlap

### Data Privacy

- Dulus runs locally and stores its sessions, tasks, and memory on the machine.
- Prompts and tool context are sent to the provider you select unless you use a local model.
- Plugins, MCP servers, browser-backed providers, search tools, and bridges may contact their own services; review them before enabling them.
- Memory stays under `~/.dulus/memory/` and project-local `.dulus/memory/` unless a configured integration moves that data.
- Telemetry is opt-in. When enabled, operational events exclude prompts, responses, file contents, paths, credentials, emails, and usernames.

---

## Reporting Security Vulnerabilities

### How to Report

If you discover a security vulnerability in Dulus, please report it responsibly:

1. **Do NOT** open a public issue
2. Send an email to: **security@dulus.ai**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

| Stage | Timeline |
|---|---|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 7 days |
| Fix released | Within 30 days (critical: 7 days) |
| Public disclosure | After fix is released |

### Disclosure Policy

We follow responsible disclosure:
1. Reporter submits vulnerability privately
2. We acknowledge and assess
3. We develop and test a fix
4. Fix is released
5. Public disclosure with credit to reporter

### Hall of Fame

We publicly credit security researchers who report valid vulnerabilities (with their permission).

---

## Security Best Practices for Users

### 1. Use Appropriate Permission Mode

```
/permissions auto        # Default — safe for daily use
/permissions manual      # When working with sensitive data
/plan                    # Enter read-only planning mode
```

### 2. Protect Your Config Directory

```bash
chmod 700 ~/.dulus
```

### 3. Set a Custom Encryption Key

```bash
export DULUS_SECRET="your-random-secret-here"
```

### 4. Keep Dependencies Updated

```bash
pip install --upgrade dulus
```

### 5. Review Plugin Sources

Only install plugins from trusted sources:

```
/plugin install trusted-plugin@https://github.com/trusted-org/repo
```

### 6. Audit MCP Servers

Review `.mcp.json` before connecting:

```bash
cat ~/.dulus/mcp.json
```

### 7. Disable Unused Features

```
/config tts_enabled=false
```

---

## Known Limitations

1. **Config obfuscation is reversible.** Use operating-system or external secret storage for strong protection.
2. **Browser-backed providers manage session cookies or tokens.** Use them only on trusted machines and rotate sessions after suspected exposure.
3. **`accept-all` removes the approval boundary.** Do not use it with sensitive data or on an untrusted checkout.
4. **Third-party code runs with your user permissions.** Review plugins, skills, MCP servers, hooks, and generated adapters before enabling them.
5. **Sub-agents are not a security boundary.** Worktrees isolate files, not operating-system privileges.

---

> *Security is not a feature — it is a foundation. We keep flying, securely.*
