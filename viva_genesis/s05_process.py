"""CPMProcess variant that pre-equilibrates its diffusing fields before the first update.

Addressed by string from ``multicellularity_world`` (this module imports viva_cpm, that one does not).
"""
from viva_cpm.processes.cpm_process import CPMProcess


class PreEquilibratedCPMProcess(CPMProcess):
    config_schema = {**CPMProcess.config_schema,
                     "pre_equilibrate": {"_type": "integer", "_default": 0}}

    def initialize(self, config):
        super().initialize(config)
        n = int(self.config.get("pre_equilibrate") or 0)
        if n > 0 and self.n_fields > 0:
            self.world.advance_fields(n)
