# orchestrator.py — Spawns ResearchWorker and WriterWorker
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

from examples.multi_agent.worker_agent import WorkerAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topic",
        default="future of renewable energy",
        help="Topic to research and write about",
    )
    parser.add_argument(
        "--output",
        default="output/multi_agent_report.md",
        help="Output markdown file",
    )
    args = parser.parse_args()

    print(f"\n[Orchestrator] Spawning workers for topic: {args.topic}\n")

    # Spawn specialised workers
    researcher = WorkerAgent(role="researcher", worker_id="researcher_01")
    writer = WorkerAgent(role="writer", worker_id="writer_01")

    # Phase 1: Research
    research_task = (
        f"Research the topic '{args.topic}'. "
        "Search the web, fetch the top 3 results, "
        "and return a structured summary of key findings."
    )
    print("[Orchestrator] Routing to ResearchWorker...")
    research_output = researcher.run(research_task)
    print(f"[ResearchWorker] Done. Output length: {len(research_output)} chars\n")

    # Phase 2: Writing
    write_task = (
        f"Using the following research findings, write a polished 500-word "
        f"markdown article about '{args.topic}'. "
        f"Save it to '{args.output}'.\n\n"
        f"Research findings:\n{research_output}"
    )
    print("[Orchestrator] Routing to WriterWorker...")
    write_output = writer.run(write_task)
    print(f"[WriterWorker] Done.\n")

    print(f"[Orchestrator] Pipeline complete. Report at: {args.output}")
    print(f"[Final output]\n{write_output}")


if __name__ == "__main__":
    main()
    