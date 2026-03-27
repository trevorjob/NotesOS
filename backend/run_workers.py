"""
NotesOS - Worker Runner
Starts all background workers concurrently in a single process.

Usage:
    python run_workers.py
    python run_workers.py --only chunking knowledge audio   # subset
"""

import argparse
import asyncio
import sys

from app.workers.chunking_worker import chunking_worker
from app.workers.transcription_worker import transcription_worker
from app.workers.fact_check_worker import start_fact_check_worker
from app.workers.grading_worker import start_grading_worker
from app.workers.knowledge_worker import knowledge_worker
from app.workers.audio_worker import audio_worker

WORKERS = {
    "chunking": chunking_worker,
    "transcription": transcription_worker,
    "fact_check": start_fact_check_worker,
    "grading": start_grading_worker,
    "knowledge": knowledge_worker,
    "audio": audio_worker,
}


async def main(names: list[str]):
    selected = {k: v for k, v in WORKERS.items() if k in names}
    if not selected:
        print(f"No workers matched. Available: {', '.join(WORKERS)}")
        sys.exit(1)

    print(f"🚀 Starting workers: {', '.join(selected)}")
    tasks = [asyncio.create_task(fn(), name=name) for name, fn in selected.items()]

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n🛑 Shutting down workers...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NotesOS background workers")
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="WORKER",
        default=list(WORKERS.keys()),
        help=f"Workers to start (default: all). Choices: {', '.join(WORKERS)}",
    )
    args = parser.parse_args()
    asyncio.run(main(args.only))
