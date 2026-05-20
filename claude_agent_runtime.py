"""RUNTIME — Load agent IDs and create sessions.

## 4 Patterns

    python claude_agent_runtime.py              ← interactive chat
    python claude_agent_runtime.py --cron       ← scheduled analysis
    python claude_agent_runtime.py --task "..." ← fire-and-forget PR
    python claude_agent_runtime.py --research "TSMC DCF" ← research + dashboard

## Model Selection

    --model opus     (default)
    --model sonnet
    --model haiku
"""
import argparse
import json
import os
import sys

import anthropic


def load_config(path: str = ".claude_agent.env") -> dict:
    cfg = {}
    if not os.path.exists(path):
        print(f"Missing {path}. Run claude_agent_setup.py first.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k] = v
    return cfg


def get_session_url(session_id: str) -> str:
    return f"https://platform.claude.com/workspaces/default/sessions/{session_id}"


# ── Pattern implementations ───────────────────────────────────────────

def run_interactive(client: anthropic.Anthropic, cfg: dict, model: str):
    """Pattern 1: Interactive chat session."""
    agent_id = cfg[f"AGENT_ID_{model.upper()}"]
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=cfg["ENVIRONMENT_ID"],
        title="Interactive Analysis",
    )
    print(f"Session: {session.id}")
    print(f"Console: {get_session_url(session.id)}")

    print("\nType your request (empty line to end multi-line, 'quit' to exit):\n")
    while True:
        lines = []
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                return
            if line == "quit":
                print("Exiting.")
                return
            if line == "":
                break
            lines.append(line)
        if not lines:
            continue

        user_text = "\n".join(lines)
        _stream_session(client, session.id, user_text)


def run_cron(client: anthropic.Anthropic, cfg: dict, model: str):
    """Pattern 2: Scheduled analysis — fire off, drain, report.

    Intended to be called by cron / Task Scheduler.
    Prints a one-line summary suitable for logging.
    """
    agent_id = cfg[f"AGENT_ID_{model.upper()}"]
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=cfg["ENVIRONMENT_ID"],
        title=f"Cron Analysis {model}",
    )

    user_text = (
        "Analyze the latest stock data in the workspace CSVs. "
        "For each stock: (1) compute MA5/MA20 crossover status, "
        "(2) MACD signal, (3) KDJ overbought/oversold, "
        "(4) whale accumulation/distribution signal. "
        "Write a one-paragraph market summary to market_summary.md "
        "and append key metrics to daily_log.csv."
    )
    text = _stream_session(client, session.id, user_text)
    print(f"[{session.id}] {text[:200]}..." if len(text) > 200 else f"[{session.id}] {text}")


def run_task(client: anthropic.Anthropic, cfg: dict, model: str, task: str):
    """Pattern 3: Fire-and-forget — single task, get result."""
    agent_id = cfg[f"AGENT_ID_{model.upper()}"]
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=cfg["ENVIRONMENT_ID"],
        title=f"Task: {task[:60]}",
    )

    text = _stream_session(client, session.id, task)
    print(f"\nResult: {text}")


def run_research(client: anthropic.Anthropic, cfg: dict, model: str, topic: str):
    """Pattern 4: Research + dashboard — in-depth analysis with visual output."""
    agent_id = cfg[f"AGENT_ID_{model.upper()}"]
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=cfg["ENVIRONMENT_ID"],
        title=f"Research: {topic[:60]}",
    )

    user_text = (
        f"Deep-dive research task: {topic}\n\n"
        "Work through this systematically:\n"
        "1. Search the web for current context and data relevant to this topic\n"
        "2. Analyze all relevant CSV data in the workspace\n"
        "3. Run technical indicators from cStocks.py as needed\n"
        "4. Generate an Excel report with charts (use the xlsx skill)\n"
        "5. Export a PDF summary with key findings (use the pdf skill)\n"
        "6. Write a concise research_note.md with methodology and conclusions\n\n"
        "Save all outputs to /mnt/session/outputs/."
    )
    text = _stream_session(client, session.id, user_text)
    print(f"\nResearch complete.\n{text}")


# ── Stream helper ─────────────────────────────────────────────────────

def _stream_session(client: anthropic.Anthropic, session_id: str, kickoff: str) -> str:
    """Open stream, send kickoff, drain to idle/terminated. Returns collected text."""
    collected: list[str] = []

    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[{
                "type": "user.message",
                "content": [{"type": "text", "text": kickoff}],
            }],
        )

        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        collected.append(block.text)
                        print(block.text, end="", flush=True)

            elif event.type == "agent.custom_tool_use":
                print(f"\n[Custom tool: {event.name}({json.dumps(event.input)})]")

            elif event.type == "session.status_idle":
                if event.stop_reason is None:
                    break
                stop_type = getattr(event.stop_reason, "type", None)
                if stop_type != "requires_action":
                    break
                # requires_action → waiting on custom tool / confirmation; continue

            elif event.type == "session.status_terminated":
                break

    return "".join(collected)


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Yuanta Managed Agent Runtime")
    parser.add_argument("--model", choices=["opus", "sonnet", "haiku"],
                        default="opus", help="Which agent model to use")
    parser.add_argument("--cron", action="store_true", help="Scheduled analysis run")
    parser.add_argument("--task", type=str, default=None, help="Fire-and-forget task")
    parser.add_argument("--research", type=str, default=None, help="Research topic")
    args = parser.parse_args()

    cfg = load_config()
    client = anthropic.Anthropic()

    if args.cron:
        run_cron(client, cfg, args.model)
    elif args.task:
        run_task(client, cfg, args.model, args.task)
    elif args.research:
        run_research(client, cfg, args.model, args.research)
    else:
        run_interactive(client, cfg, args.model)


if __name__ == "__main__":
    main()
