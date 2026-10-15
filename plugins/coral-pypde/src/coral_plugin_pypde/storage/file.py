from pde import FileStorage


class PyPDEFileStorage:
    """Wrapper for a FileStorage and the tracker that writes into it.

    ``interrupts`` is the schedule, in simulation time, on which a snapshot is written: ``1``
    stores one field per time unit.
    """

    def __init__(self, filename: str, write_mode: str, interrupts: float):
        self.filename = filename
        self.storage = FileStorage(filename, write_mode=write_mode)
        self.tracker = self.storage.tracker(interrupts)
