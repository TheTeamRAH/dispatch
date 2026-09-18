def main() -> None:
    from .inspection import InspectionService
    from .stores import HistoryStore, TargetRegistry
    from .transport import SSHTransport
    from .tui import DispatchApp

    history = HistoryStore()
    DispatchApp(history_store=history, inspection_service=InspectionService(SSHTransport(), history), registry=TargetRegistry()).run()
