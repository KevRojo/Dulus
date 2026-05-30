# Security Policy

> Dulus takes security seriously. This document outlines our security practices, reporting procedures, and responsible disclosure policy.

---

## Supported Versions

| Version | Supported |
|---|---|
| 3.2.x | :white_check_mark: Current stable |
| 3.1.x | :white_check_mark: Security fixes only |
| 3.0.x | :x: End of life |
| < 3.0 | :x: Not supported |

---

## Security Model

### Permission System

Dulus operates with a tiered permission system:

| Mode | Behavior | Use Case |
|---|---|---|
| `auto` | Reads always allowed. Prompts before writes/shell. | Daily development |
| `manual` | Prompts for every operation | Sensitive environments |
| `plan` | Read-only analysis. Only plan file writable | Code review |
| `accept-all` | No prompts (dangerous) | CI/CD pipelines only |

### API Key Protection

- Keys stored in `~/.dulus/config.json` are encrypted with XOR + base64
- Environment variable bridging only sets vars that aren't already present
- No keys are ever logged or transmitted outside of API calls
- Keys can be rotated via `/config <provider>_api_key=new_key`

### Safe Execution

- **Bash whitelist:** Safe commands (`ls`, `cat`, `grep`) auto-approve in `auto` mode
- **Dangerous commands** (`rm`, `dd`, `mkfs`, etc.) always require explicit approval
- **Network isolation:** All tool execution happens locally
- **Sandbox:** Experimental browser-based OS for isolated execution

### Data Privacy

- All processing happens on your machine
- No telemetry, analytics, or tracking
- MemPalace data stays local (`~/.dulus/memory/`)
- Conversations are not sent to any third party (except your chosen AI provider)

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
/permissions plan        # For read-only analysis
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

1. **Config encryption** is XOR + base64 — protects against casual snooping but is not military-grade. Use full-disk encryption for strong protection.
2. **Browser harvest** requires Dulus to manage browser cookies. Use only on trusted machines.
3. **`accept-all` mode** is dangerous — never use it in production or with sensitive data.
4. **Sub-agents** run with the same permissions as the parent. Use governance layer to restrict.

---

## Compliance

Dulus is designed to be compliant with:
- **GDPR** — No personal data collection, all processing local
- **CCPA** — No data selling, no tracking
- **SOC 2** (future) — Audit logs, access controls planned for Enterprise tier

---

> *Security is not a feature — it is a foundation. We keep flying, securely.*
