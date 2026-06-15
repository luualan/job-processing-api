import heapq
import threading
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import crud, models


import heapq
import threading
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import crud, models


class InMemoryPriorityQueue:
    """Tiny, easy-to-explain priority queue for job IDs.

    - Uses a heap of tuples: (-priority, created_ts, job_id)
    - Higher numeric `priority` is treated as higher priority by negating it
    - For equal priority, smaller `created_ts` (older) comes first
    """

    def __init__(self):
        self._heap = []
        self._lock = threading.Lock()

    def enqueue(self, job):
        """Add a job ID to the queue.

        Stores only the job id and ordering keys (priority, created timestamp).
        """
        priority = job.priority or 0
        created_ts = getattr(job, "created_at", None)
        if created_ts is None:
            created_ts = datetime.now(timezone.utc)
        # Use negative priority so heap pops highest priority first
        entry = (-priority, created_ts.timestamp(), job.id)
        with self._lock:
            heapq.heappush(self._heap, entry)

    def claim_next_job(self, db: Session) -> Optional[models.Job]:
        """Pop and claim the next pending job.

        Skips stale entries (job missing or not PENDING) and handles races
        by using `start_job_if_pending` which atomically flips the status.
        Returns the claimed job or None if none available.
        """
        while True:
            with self._lock:
                if not self._heap:
                    return None
                _, _, job_id = heapq.heappop(self._heap)

            job = crud.get_job(db, job_id)
            if job is None:
                continue
            if job.status != models.JobStatus.PENDING:
                continue

            try:
                claimed = crud.start_job_if_pending(db, job_id)
                return claimed
            except ValueError:
                # another process claimed it first
                continue

    def clear(self):
        """Empty the queue (useful in tests)."""
        with self._lock:
            self._heap.clear()

    def peek(self):
        """Return a snapshot of queued entries without modifying the heap.

        Each entry is a dict: {job_id, priority, created_ts}.
        """
        with self._lock:
            # Return a copy to avoid exposing internal structures
            return [
                {
                    "job_id": entry[2],
                    "priority": -entry[0],
                    "created_at": datetime.fromtimestamp(entry[1], timezone.utc),
                }
                for entry in list(self._heap)
            ]


# Simple module-level queue instance
queue = InMemoryPriorityQueue()
