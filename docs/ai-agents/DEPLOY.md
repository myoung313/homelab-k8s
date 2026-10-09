# Deploying AgentOS

Before you start, finish steps 0-2 of [PROXMOX-PLAN.md](PROXMOX-PLAN.md), at least the cp01 disk fix,
and make sure `kubectl` works from your workstation.

## 1. Build the runtime image

Merging this branch into `main` runs `.github/workflows/agentos-image.yml`. It validates the roster and
pushes `ghcr.io/myoung313/homelab-agentos:latest`.

Then either:
- make the package public (GitHub → your profile → Packages → `homelab-agentos` → Package settings →
  Change visibility), **or**
- keep it private and add a pull secret:
  `kubectl -n agents create secret docker-registry ghcr --docker-server=ghcr.io --docker-username=myoung313 --docker-password=<PAT with read:packages>`
  then add `imagePullSecrets: [{name: ghcr}]` to the three Deployments in `runtime.yaml`.

## 2. Namespace and secrets

```bash
kubectl apply -f namespaces/agents.yaml

cp apps/agent-platform/secrets.example.yaml apps/agent-platform/secrets.yaml   # git-ignored
openssl rand -hex 24     # run once per REPLACE_ME value; reuse the same Postgres/Redis
                         # passwords inside DATABASE_URL and REDIS_URL
$EDITOR apps/agent-platform/secrets.yaml
kubectl apply -f apps/agent-platform/secrets.yaml
```

In the [Anthropic Console](https://console.anthropic.com), create the API key and **set a monthly
spend limit**. That limit is your last line of defense against runaway spend.

## 3. Deploy

```bash
kubectl apply -k apps/agent-platform
kubectl apply -f security/network-policies/agents.yaml
kubectl apply -f networking/ingress/agents-ingress.yaml
kubectl -n agents get pods -w
```

In your DNS (pfSense or router host overrides), point `agents.home.arpa` and `n8n.home.arpa` at a node
IP (for example `192.168.1.30`).

## 4. Brief the team

The agents read shared memory. Give them the facts only you know:

```bash
kubectl -n agents exec -i statefulset/postgres -- psql -U agentos agentos <<'SQL'
INSERT INTO memory (agent, note) VALUES
 ('owner', 'target niche: <e.g. HVAC and plumbing companies with 5-50 staff>'),
 ('owner', 'service area: <city / region, or US-wide>'),
 ('owner', 'ICP: <revenue range, has a website + contact form, gets inbound calls, no online booking>'),
 ('owner', 'offer: Starter $1,500 + $400/mo; Growth $2,500 + $750/mo; Custom $4,000+'),
 ('owner', 'sender identity: <Your Name>, <Studio LLC>, <mailing address>, booking link <cal.com/...>'),
 ('owner', 'targets: $10k/month by <month>; 2 new clients per month');
SQL
```

Not sure about the niche yet? Open Mission Control, run `niche-researcher`, and decide from its report.

## 5. First run

1. Open `http://agents.home.arpa` and log in as `admin` with your `CONSOLE_PASSWORD`.
2. Under **Run an agent**, pick `trend-scout` and enter "Run your daily brief now." You should see a
   task go queued → running → done, and a new item under **Latest outputs**.
3. Try `chief-of-staff` next. Scheduled agents fire on their own from tomorrow morning.

## 6. Wire n8n (the hands)

Open `http://n8n.home.arpa` and create the owner account.

Give n8n a **least-privilege** database login for the agent tables:

```bash
kubectl -n agents exec -i statefulset/postgres -- psql -U agentos agentos <<'SQL'
CREATE ROLE n8n_actions LOGIN PASSWORD '<openssl rand -hex 24>';
GRANT SELECT ON approvals TO n8n_actions;
GRANT UPDATE (executed_at) ON approvals TO n8n_actions;
GRANT INSERT ON memory TO n8n_actions;
GRANT USAGE ON SEQUENCE memory_id_seq TO n8n_actions;
SQL
```

Then build these workflows in the n8n editor:

**A. Execute approvals** (the only path from an agent to the outside world)
1. Schedule Trigger: every 2 minutes
2. Postgres (host `postgres`, db `agentos`, user `n8n_actions`):
   `SELECT * FROM approvals WHERE status = 'approved' AND executed_at IS NULL ORDER BY id LIMIT 20`
3. Switch on `{{$json.action}}`: `send_email` / `send_email_batch` → Gmail node,
   `publish_posts` → LinkedIn/X nodes, `create_invoice` → Stripe node,
   `suppress_contact` → your do-not-contact list
4. Postgres: `UPDATE approvals SET executed_at = now() WHERE id = {{$json.id}}`

**B. Inbound replies → inbox-triage**
1. Gmail Trigger (polling, so no public URL is needed) on the outreach inbox
2. HTTP Request: `POST http://agentos-console/api/tasks`, Basic Auth `admin` / `CONSOLE_PASSWORD`,
   JSON body `{"agent": "inbox-triage", "input": "From: {{$json.from}}\nSubject: {{$json.subject}}\n\n{{$json.text}}"}`

Use the same HTTP pattern to feed `client-health` (daily metrics), `sre-watchdog` (alerts), and
`freelance-bidder` (job posts).

## Slack updates (recommended)

Agents message you in one Slack channel. You get the chief-of-staff briefing, the accountability
coach's morning plan and evening check, the weekly efficiency audit, ❗ alerts when approvals are
waiting, and 💥 alerts when a task fails. Without Slack, the same messages appear in Mission Control
under **Latest outputs**.

1. Create a free workspace at [slack.com](https://slack.com), or use one you already have. Add a channel
   such as `#agentos`.
2. Go to [api.slack.com/apps](https://api.slack.com/apps), choose **Create New App**, then **From scratch**.
   Name it "AgentOS" and pick your workspace.
3. Open **Incoming Webhooks**, switch it on, click **Add New Webhook to Workspace**, and choose `#agentos`.
   Copy the URL, which starts with `https://hooks.slack.com/services/...`. Treat it like a password,
   because anyone who has it can post to the channel.
4. On `k3s-cp01`, add the URL to `apps/agent-platform/secrets.yaml` as
   `SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/..."`, then apply it and restart:
   ```bash
   sudo kubectl apply -f apps/agent-platform/secrets.yaml
   sudo kubectl -n agents rollout restart deploy/agentos-worker
   ```
5. Test it: in Mission Control, run `accountability-coach` with "Send me today's game plan."

Each agent can send you at most 4 messages a day, so your phone won't get spammed. Approve and reject
buttons inside Slack are a possible next step; they would use Slack's Socket Mode, so nothing in the
homelab has to be exposed to the internet.

## Daily check-in

At the end of each workday, write one line in **Daily check-in** in Mission Control. For example:
"approved 15 emails, 5 bids, 3 calls, 1 meeting booked". The accountability coach compares it with the
morning plan, keeps your streak, and adjusts tomorrow's targets. The process auditor uses your
check-ins in its weekly review.

## Operating it

| I want to… | Do this |
|---|---|
| Watch the team work | `http://agents.home.arpa/office`: the dungeon map. Each department is a room, agents pick their own avatar on their first run, and you click any agent to see what it's doing. |
| Choose an agent's avatar yourself | Add `avatar: dragon` (any name from `runtime/agentos/avatars.py`) to that agent in `roster.yaml` and re-apply |
| Stop everything now | Mission Control → **Pause everything** |
| Unlock the next group of agents | Set `AGENTOS_PHASE=2` in `apps/agent-platform/kustomization.yaml`, then `kubectl apply -k apps/agent-platform` |
| Change an agent's prompt, model, budget, or schedule | Edit `apps/agent-platform/roster.yaml` and re-apply. The pods restart with the new roster automatically. |
| Raise or lower the fleet's daily cap | `GLOBAL_DAILY_BUDGET_USD` in `kustomization.yaml` |
| More throughput | `kubectl -n agents scale deploy/agentos-worker --replicas=3` |
| Turn on local models | `kubectl -n agents scale deploy/ollama --replicas=1` (needs RAM on the worker) |
| See logs | `kubectl -n agents logs deploy/agentos-worker -f` |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ImagePullBackOff` on agentos pods | The GHCR package is private and there's no pull secret (step 1) |
| Tasks end as `skipped` | An agent or global daily budget was reached (that's the guardrail working) |
| "Could not reach the Anthropic API" | DNS or egress blocked. Check `kubectl -n agents get networkpolicy` and node DNS. |
| "API key rejected" | Wrong `ANTHROPIC_API_KEY` in `agentos-secrets`. Re-apply it, then `kubectl -n agents rollout restart deploy` |
| Postgres pod `Pending` | No `local-path` storage class, or the node is out of disk (PROXMOX-PLAN step 1) |
