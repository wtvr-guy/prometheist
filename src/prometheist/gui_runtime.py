"""Resource admission for routed local/remote workers; never borrow wrong-model credit."""
from prometheist.gui_config import job_settings
from prometheist.ollama_runtime import OllamaRuntimeProbe, OllamaRuntimeState


class RoutedRuntimeProbe:
    def capture(self):
        return OllamaRuntimeState(model="routed-models", probe_ok=False, resident=False,
                                  error="Mixed or remote routes do not receive local residency credit")


def configured_runtime_probe():
    settings = job_settings()
    if settings is None:
        return None
    from prometheist.contract_registry import STAGE_CONTRACTS
    selections = [settings.selection_for(stage) for stage, contract in STAGE_CONTRACTS.items()
                  if contract.kinds and stage.startswith("V2_")]
    local = {selection.model for selection in selections if selection.provider == "ollama"}
    if len(local) == 1 and all(selection.provider == "ollama" for selection in selections):
        return OllamaRuntimeProbe(base_url=settings.ollama_url, model=local.pop())
    return RoutedRuntimeProbe()
