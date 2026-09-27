def main() -> None:
    from .inspection import InspectionService
    from .stores import HistoryStore, TargetRegistry
    from .transport import SSHTransport
    from .tui import DispatchApp
    from .workflow_service import WorkflowService
    from .workflow_stores import WorkflowHistoryStore, WorkflowRegistry, workflow_path

    history = HistoryStore()
    workflow_history = WorkflowHistoryStore(history.path.parent / "workflow-history")
    transport = SSHTransport()
    DispatchApp(
        history_store=history,
        inspection_service=InspectionService(transport, history),
        registry=TargetRegistry(),
        workflow_registry=WorkflowRegistry(workflow_path()),
        workflow_service=WorkflowService(transport, workflow_history),
        workflow_history_store=workflow_history,
    ).run()
