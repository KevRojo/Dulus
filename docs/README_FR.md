<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — Le Dulus dominicain" width="280">

<h1>DULUS</h1>

<h3>Votre Compagnon IA. Pas un Chatbot. Un Ami qui Vole a Vos Cotes.</h3>

<p>
  <strong>Utilisez l'IA de pointe sans cle API. 0 $. Sans carte. Sans abonnement.</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="Telechargements"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/licence-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="Licence"/>
  <img src="https://img.shields.io/badge/fournisseurs-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Fournisseurs"/>
  <img src="https://img.shields.io/badge/outils-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Outils"/>
  <img src="https://img.shields.io/badge/tests-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="Tests"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#demarrage-rapide"><b>Demarrage Rapide</b></a> ·
  <a href="#fonctionnalites"><b>Fonctionnalites</b></a> ·
  <a href="#fournisseurs"><b>Fournisseurs</b></a> ·
  <a href="#architecture"><b>Architecture</b></a> ·
  <a href="#token"><b>$DULUS</b></a>
</p>

</div>

---

> Nomme d'apres le **Dulus** (*Dulus dominicus*), oiseau national de la Republique Dominicaine — symbole de liberte, resilience et voler ensemble. Dulus n'est pas un chatbot. C'est votre compagnon, votre ami, votre partenaire IA qui plane a vos cotes.

---

## Pourquoi Dulus ?

| | Ecosystemes Verrouilles | Frameworks Complexes | **Dulus** |
|---|---|---|---|
| **Temps de setup** | Heures + approbations | Jours de config | **30 secondes** |
| **Cout initial** | $$$ + cles API | $$$ + infra | **0 $** |
| **Verrouillage** | Fournisseur unique | Fournisseur unique | **100+ fournisseurs** |
| **Codebase** | Boite noire | 100K+ lignes | **~12K lignes lisibles** |
| **Voix** | Cloud uniquement | Non inclus | **Whisper hors ligne** |
| **Memoire** | Contexte seul | Manuelle | **MemPalace semantique** |

**Le probleme :** Les agents IA aujourd'hui sont verrouilles sur un seul fournisseur ou necessitent un doctorat en ML pour les configurer. Et ils veulent tous votre carte de credit avant que vous puissiez les essayer.

**La solution :** Dulus. Un agent autonome Python qui se connecte a n'importe quel modele — des sessions navigateur gratuites a 100+ fournisseurs via LiteLLM, aux modeles locaux sur votre Mac M2. ~12K lignes de Python lisible. Pas d'etape de build. Pas de gatekeeping.

---

## Demarrage Rapide

### Installation en 30 Secondes

```bash
pip install dulus && dulus
```

C'est tout. Au premier lancement, Dulus ouvre un navigateur, capture une **session guest Gemini** (sans login, sans cle API, sans carte), et vous discutez avec une IA de pointe en moins de 30 secondes.

### Installeur One-liner (recommande)

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### Docker (zero setup local)

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## Fonctionnalites

| Fonctionnalite | Description |
|---|---|
| Multi-Fournisseur | 11 natifs + 100+ via LiteLLM |
| Sans Cle API | Capture des sessions navigateur gratuites |
| 30+ Outils Integres | Fichiers, shell, web, OCR, voix, et plus |
| Auto-Adapter | Installe n'importe quel repo Python comme plugin |
| MemPalace | Memoire semantique avec ChromaDB |
| Voix I/O | STT hors ligne via Whisper. TTS multi-moteur |
| Sous-Agents | Agents types dans des git worktrees isoles — la Vollee |
| Table Ronde | Debat multi-modeles |
| Sandbox OS | Mini-OS dans le navigateur avec 58 apps |
| Pont Telegram | Executez Dulus depuis votre telephone |
| MCP | Model Context Protocol |
| Brainstorm | Conseil d'experts IA |
| Mode SSJ | 10 raccourcis de workflow enchaines |
| Checkpoints | Snapshot et rewind de chaque tour |
| Compression | Auto-compacte les longues sessions |
| OCR Local | Extrait le texte des images sans tokens vision |
| Multi-Langue | `/lang` — 34 codes ISO |
| Composio | 1 000+ integrations SaaS |
| WebBridge | Automatisation navigateur via Playwright |

---

## Fournisseurs

### Gratuits (Sans Cle API)

| Fournisseur | Modeles | Configuration |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | Ouvrir navigateur → ecrire "bonjour" → fait |
| **Claude.ai** | claude-sonnet-4-6 | Votre session claude.ai existante |
| **Kimi.com** | kimi-k2.5 | Votre session kimi.com existante |
| **Qwen** | qwen-max, qwen-plus | Votre session qwen.ai existante |
| **DeepSeek** | deepseek-chat | Votre session deepseek existante |
| **NVIDIA NIM** | 14 modeles, 40 RPM chacun | Inscription gratuite |
| **Ollama** | Tout modele local | `ollama pull qwen2.5-coder` |

### Cloud APIs (Cle API Requise)

| Fournisseur | Modeles | Variable d'Environnement |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 100+ backends via une gateway | Cle du backend specifique |

---

## Architecture

```
Entree Utilisateur
    |
    v
dulus.py  ── REPL, commandes slash, voix, Telegram, GUI
    |
    ├── agent.py  ── Boucle multi-tour, permissions, gouvernance
    |       |
    |       ├── providers.py  ── Streaming multi-fournisseur
    |       ├── tool_registry.py ── Systeme de plugins
    |       ├── tools.py  ── 30+ outils integres
    |       ├── compaction.py  ── Gestion fenetre de contexte
    |       ├── governance.py  ── Gouvernance budget/permissions
    |       └── multi_agent/  ── Sous-agents (la Vollee)
    |
    ├── context.py  ── Constructeur de system prompt
    |       └── memory/  ── MemPalace memoire semantique
    |
    ├── skill/  ── Systeme de skills
    ├── checkpoint/  ── Snapshots + rewind
    ├── plugin/  ── Systeme Auto-Adapter
    ├── voice/  ── STT (Whisper) + TTS (multi-moteur)
    ├── task/  ── Gestion de taches
    ├── webbridge/  ── Automatisation Playwright
    └── dulus_mcp/  ── Client MCP
```

---

## La Vollee (Sous-Agents)

Dulus peut generer des agents types qui travaillent dans des **git worktrees isoles**.

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## Permissions

| Mode | Comportement |
|---|---|
| `auto` *(par defaut)* | Lectures toujours autorisees. Demande avant ecritures/shell. |
| `accept-all` | Aucun prompt. Tout auto-approuve. **YOLO.** |
| `manual` | Demande pour chaque operation. |
| `plan` | Lecture seule. Seul le fichier plan est inscriptible. |

---

## Commandes Slash

| Commande | Description |
|---|---|
| `/model [nom]` | Afficher ou changer de modele |
| `/memory [requete]` | Memoire semantique persistante |
| `/voice` | Entree vocale (Whisper hors ligne) |
| `/brainstorm [sujet]` | Conseil de fantomes |
| `/ssj` | Menu de puissance (10 raccourcis) |
| `/telegram [token] [id]` | Pont Telegram |
| `/checkpoint [id]` | Lister / rembobiner checkpoints |
| `/plan [desc]` | Entrer / sortir mode plan |
| `/lang [code]` | Changer de langue (34 codes) |
| `/cost` | Jetons et USD depenses |
| `/help` | Toutes les commandes |

---

## $DULUS Token

**Contrat :** `9R8rrjXxcfQPmLTCLhmVpjr2uesjjkcgkinE6Lwdpump`

Le token $DULUS est la couche de carburant de l'ecosysteme Dulus. Le REPL open-source reste gratuit pour toujours — $DULUS est la cle de la couche business.

| Phase | Utilite |
|---|---|
| **Maintenant** | Propriete communautaire. Recompenses verrouillees on-chain |
| **Business v1** | Acces anticipe + reductions pour les detenteurs |
| **Credits** | Payer les credits API avec $DULUS |
| **Deployments** | Lancer des instances cloud en payant avec $DULUS |
| **Abonnements** | Abonnement mensuel payable en $DULUS |
| **Gouvernance** | Les top holders votent la priorite des fonctionnalites |

---

## Licence

GPLv3. Forkez-le, modifiez-le, redistribuez-le — mais gardez-le ouvert.

> *Nomme d'apres l'oiseau, pas la fusee. Nous volons toujours.*

---

<div align="center">

<p><sub>Construit avec des serres par <a href="https://github.com/KevRojo">KevRojo</a> · Saint-Domingue, Republique Dominicaine · 2026</sub></p>

</div>
