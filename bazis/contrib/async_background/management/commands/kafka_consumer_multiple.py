import logging
import os
import sys
import time

from django.core.management.base import BaseCommand, CommandParser

import psutil


logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 1
SHUTDOWN_POLL_INTERVAL_SEC = 0.1
SHUTDOWN_TIMEOUT_SEC = 5


class Command(BaseCommand):
    help = "Starts Kafka consumers in separate processes."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--consumers-count",
            type=int,
            default=15,
            help="Number of processes to start (default: 15).",
        )
        parser.add_argument(
            "--restart-delay-sec",
            type=float,
            default=1.0,
            help="Delay before restarting a consumer process (default: 1.0).",
        )
        parser.add_argument(
            "--max-restarts",
            type=int,
            default=None,
            help="Maximum restarts per consumer. Omit for unlimited.",
        )

    def handle(self, *args, **options) -> None:
        """Starts Kafka consumers and monitors their completion."""
        logger.info("Starting Kafka consumers...")
        consumers_count = options["consumers_count"]
        restart_delay_sec = options["restart_delay_sec"]
        max_restarts = options["max_restarts"]
        processes: dict[int, psutil.Popen] = {}

        def start_consumer_process(index: int) -> psutil.Popen:
            env = os.environ.copy()
            process = psutil.Popen(
                [str(sys.executable), "manage.py", "kafka_consumer_single"],
                env=env,
            )
            logger.info("Started consumer process %s with index %s", process.pid, index)
            return process

        try:
            for i in range(1, consumers_count + 1):
                processes[i] = start_consumer_process(i)

            restart_counts: dict[int, int] = {i: 0 for i in processes}

            while True:
                time.sleep(POLL_INTERVAL_SEC)

                for index, process in list(processes.items()):
                    if process.poll() is not None:
                        exit_code = process.returncode
                        logger.warning(
                            "Consumer process %s (index=%s) exited with code %s",
                            process.pid,
                            index,
                            exit_code,
                        )
                        restart_counts[index] += 1
                        if max_restarts is not None and restart_counts[index] > max_restarts:
                            logger.error(
                                "Consumer %s exceeded max restarts (%s).",
                                index,
                                max_restarts,
                            )
                            continue
                        time.sleep(restart_delay_sec)
                        logger.info("Restarting consumer process with index %s", index)
                        processes[index] = start_consumer_process(index)

        except KeyboardInterrupt:
            logger.warning("Received KeyboardInterrupt. Shutting down...")
            start_time = time.time()
            while (time.time() - start_time) < SHUTDOWN_TIMEOUT_SEC:
                for process in processes.values():
                    process.poll()
                time.sleep(SHUTDOWN_POLL_INTERVAL_SEC)

            for process in processes.values():
                if process.poll() is None:
                    process.terminate()
            logger.info("All consumer processes terminated.")
